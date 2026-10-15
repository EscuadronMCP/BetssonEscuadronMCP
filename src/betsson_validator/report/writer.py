"""Informe de resultados en JSON (para máquinas) y HTML autocontenido (para personas)."""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

from betsson_validator.domain.checks import DESCRIPTIONS, SCENARIO_TITLES, Check, Scenario
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import CheckResult, Outcome, Status
from betsson_validator.report.observed import Observed, load_observed
from betsson_validator.report.sections import (
    dashboard,
    demo_section,
    events_timeline,
    gallery,
    motion_section,
    narrative,
    observed_values,
    stages_timeline,
    witness_grid,
)

_OUTCOME_LABELS = {
    Outcome.CONFIRMS: "confirma",
    Outcome.CONTRADICTS: "contradice",
    Outcome.UNAVAILABLE: "no disponible",
}


@dataclass(frozen=True)
class RunInfo:
    """Procedencia de la ejecución: qué código y qué escenarios se pidieron."""

    code_version: str = "desconocida"
    requested: tuple[Scenario, ...] = tuple(Scenario)
    run_id: str | None = None

    @property
    def partial(self) -> bool:
        return set(self.requested) != set(Scenario)


def write_report(
    runs: Sequence[ScenarioRun], out_dir: Path, info: RunInfo | None = None
) -> tuple[Path, Path]:
    info = info or RunInfo(requested=tuple(run.scenario for run in runs))
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    html_path = out_dir / "index.html"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "code_version": info.code_version,
        "run_id": info.run_id,
        "requested_scenarios": [scenario.value for scenario in info.requested],
        "partial_scope": info.partial,
        "status": overall_status(runs, info).value,
        "runs": [{**run.model_dump(mode="json"), "status": run.status.value} for run in runs],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(runs, out_dir, info), encoding="utf-8")
    return json_path, html_path


def _scope(info: RunInfo) -> str:
    titles = ", ".join(SCENARIO_TITLES[scenario] for scenario in info.requested)
    note = " (alcance parcial: no se pidieron todos los escenarios)" if info.partial else ""
    run = f" · ejecución {info.run_id}" if info.run_id else ""
    return f"Código {info.code_version[:12]}{run} · escenarios solicitados: {titles}{note}"


def render_html(runs: Sequence[ScenarioRun], out_dir: Path, info: RunInfo | None = None) -> str:
    info = info or RunInfo(requested=tuple(run.scenario for run in runs))
    overall = overall_status(runs, info)
    sections = "\n".join(_render_run(run, out_dir) for run in runs)
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe de validación — Betsson</title>
<style>{_CSS}</style>
</head>
<body>
<main>
<header class="top">
<h1>Informe de validación de juegos</h1>
<p class="meta">Betsson · {escape(", ".join(sorted({run.market for run in runs})))} ·
generado {escape(datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))} · {escape(_scope(info))}</p>
</header>
{dashboard(runs, overall, info.code_version)}
{_plain_summary(runs)}
{sections}
</main>
</body>
</html>
"""


def render_markdown(
    runs: Sequence[ScenarioRun], info: RunInfo | None = None, out_dir: Path | None = None
) -> str:
    """Resumen para la página de la ejecución en GitHub Actions.

    Con `out_dir`, cada escenario lleva además su frase en lenguaje llano (lo observado).
    """
    info = info or RunInfo(requested=tuple(run.scenario for run in runs))
    overall = overall_status(runs, info)
    checks = [result for run in runs for result in run.results]
    passed = sum(result.status is Status.PASS for result in checks)
    expected = sum(len(run.results) + len(run.missing_checks()) for run in runs)
    lines = [
        f"## {'✅' if overall is Status.PASS else '❌'} Validación de juegos: {overall.value}",
        "",
        f"**{passed} de {expected} comprobaciones superadas** · {_scope(info)}",
        "",
    ]
    for run in runs:
        observed = load_observed(out_dir / run.scenario.value) if out_dir else None
        icon = "✅" if run.status is Status.PASS else "❌"
        story = f": {narrative(observed, run.scenario, run.game)}" if observed else ""
        lines.append(f"- {icon} **{SCENARIO_TITLES[run.scenario]}**{story}")
        if run.demo is not None:
            found = "FAIL detectado, como se esperaba" if run.demo.detected else "NO detectado"
            first = f" — {run.demo.results[0].reason}" if run.demo.results else ""
            lines.append(
                f"- 🧪 **Prueba que falla a propósito** (no cuenta en el resultado): {found}{first}"
            )
    lines += [
        "",
        "| Escenario | Mercado | Juego | Comprobación | Resultado | Motivo |",
        "|---|---|---|---|---|---|",
    ]
    for run in runs:
        title = SCENARIO_TITLES[run.scenario]
        if run.injected_fault:
            lines.append(
                f"| {title} | {run.market} | {run.game} | Aviso | — | {run.injected_fault} |"
            )
        if run.error:
            lines.append(
                f"| {title} | {run.market} | {run.game} | Ejecución | FAIL | {run.error} |"
            )
        for result in run.results:
            reason = result.reason.replace("|", "/")
            lines.append(
                f"| {title} | {run.market} | {run.game} | {_describe_check(result.check)} "
                f"| {result.status.value} | {reason} |"
            )
        lines.extend(
            f"| {title} | {run.market} | {run.game} | {DESCRIPTIONS[c]} | FAIL | No evaluada |"
            for c in run.missing_checks()
        )
    return "\n".join(lines) + "\n"


def _plain_summary(runs: Sequence[ScenarioRun]) -> str:
    """Resumen en lenguaje llano para quien no conoce el proyecto."""
    results = [result for run in runs for result in run.results]
    passed = sum(result.status is Status.PASS for result in results)
    expected = sum(len(run.results) + len(run.missing_checks()) for run in runs)
    games = ", ".join(sorted({run.game for run in runs}))
    return (
        '<div class="plain">'
        f"<p><b>{passed} de {expected} comprobaciones superadas</b> en {escape(games)}. "
        "Cada comprobación la confirman varios <b>testigos independientes</b>: lo que ve el "
        "jugador en la pantalla del juego y en la web de Betsson, lo que registra el servidor del "
        "juego y lo que el juego comunica a la web.</p>"
        "<p><b>PASS</b> (verde) = la pantalla lo confirma y ningún testigo lo contradice. "
        "<b>FAIL</b> (rojo) = no se pudo ver en pantalla o algún testigo contradice lo que ve el "
        "jugador; el motivo aparece en cada fila.</p></div>"
    )


def _render_run(run: ScenarioRun, out_dir: Path) -> str:
    rows = "\n".join(_render_result_row(result, out_dir) for result in run.results)
    missing = "".join(
        f"<tr><td>{escape(DESCRIPTIONS[c])}</td><td>{_badge(Status.FAIL)}</td>"
        "<td>No se llegó a evaluar.</td><td></td></tr>"
        for c in run.missing_checks()
    )
    error = f'<p class="error">Error: {escape(run.error)}</p>' if run.error else ""
    if run.injected_fault:
        error = f'<p class="fault">⚠️ {escape(run.injected_fault)}</p>' + error
    if run.notes:
        error += "".join(f'<p class="meta">Nota: {escape(note)}</p>' for note in run.notes)
    if run.quarantined:
        error += (
            '<p class="error">Evidencias retiradas por seguridad (contenían secretos): '
            f"{escape(', '.join(run.quarantined))}</p>"
        )
    folder = out_dir / run.scenario.value
    observed = load_observed(folder)
    duration = (run.finished_at - run.started_at).total_seconds()
    panels = [
        ("Capturas de lo que vio el jugador", gallery(folder, out_dir)),
        ("Qué dijo cada testigo", witness_grid(run)),
        (
            "Valores observados por cada testigo",
            observed_values(observed, run.scenario) if observed else "",
        ),
        ("Movimiento de los rodillos", motion_section(observed) if observed else ""),
        ("Cronología de la ejecución", stages_timeline(observed) if observed else ""),
    ]
    body = "".join(
        f'<div class="panel"><h3>{escape(title)}</h3>{content}</div>'
        for title, content in panels
        if content
    )
    story = (
        f'<p class="story">{escape(narrative(observed, run.scenario, run.game))}</p>'
        if observed
        else ""
    )
    body += demo_section(run)
    timeline = events_timeline(observed) if observed else ""
    if timeline:
        body += (
            '<details class="panel"><summary><h3>Eventos que el juego envió a la web</h3>'
            f"</summary>{timeline}</details>"
        )
    return f"""<section>
<h2>{escape(SCENARIO_TITLES[run.scenario])} {_badge(run.status)}</h2>
<p class="chips"><span>Mercado <b>{escape(run.market)}</b></span>
<span>Proveedor <b>{escape(run.provider)}</b></span><span>Juego <b>{escape(run.game)}</b></span>
<span>Duración <b>{duration:.0f} s</b></span>{_profile_chip(observed)}
<span>{escape(run.started_at.strftime("%Y-%m-%d %H:%M:%S UTC"))}</span></p>
{story}
{error}
{body}
<div class="panel"><h3>Detalle de cada comprobación</h3>
<div class="scroll"><table>
<thead><tr><th>Comprobación</th><th>Resultado</th><th>Motivo</th><th>Testigos</th></tr></thead>
<tbody>
{rows}
{missing}
</tbody>
</table></div></div>
{_render_media(run, out_dir)}
</section>"""


_MEDIA = (
    ("fallo_pantalla.jpg", "Captura de la pantalla al fallar"),
    ("video/*.webm", "Vídeo de la ejecución"),
    ("trace.zip", "Traza de Playwright (se abre arrastrándola a trace.playwright.dev)"),
    ("eventos_del_juego.json", "Eventos del juego (postMessage)"),
    ("trafico_juego_sin_tokens.json", "Tráfico del juego (sin tokens)"),
    ("resumen_observado.json", "Resumen de lo observado"),
    ("accesibilidad.json", "Sonda de accesibilidad (diagnóstico)"),
)


def _render_media(run: ScenarioRun, out_dir: Path) -> str:
    """Enlaces a las evidencias completas del escenario (vídeo, traza, eventos, tráfico)."""
    folder = out_dir / run.scenario.value
    links = []
    for pattern, label in _MEDIA:
        for path in sorted(folder.glob(pattern)):
            href = _href(path.relative_to(out_dir))
            links.append(f'<a href="{href}">{escape(label)}</a>')
    return f'<p class="meta">Evidencias: {" · ".join(links)}</p>' if links else ""


def _render_result_row(result: CheckResult, out_dir: Path) -> str:
    description = _describe_check(result.check)
    witnesses = "".join(
        f"<li><b>{escape(t.witness)}</b> ({_OUTCOME_LABELS[t.outcome]}): {escape(t.detail)}"
        f"{_render_evidence(t.evidence, out_dir)}</li>"
        for t in result.testimonies
    )
    return (
        f"<tr><td>{escape(description)}</td><td>{_badge(result.status)}</td>"
        f"<td>{escape(result.reason)}</td><td><ul>{witnesses}</ul></td></tr>"
    )


def _render_evidence(paths: tuple[str, ...], out_dir: Path) -> str:
    links = []
    for raw in paths:
        path = Path(raw)
        if not path.is_file():  # p. ej. retirada por contener un secreto: nunca un enlace roto
            links.append(f'<span class="missing">{escape(path.name)}: no disponible</span>')
            continue
        href = _href(path.relative_to(out_dir) if path.is_relative_to(out_dir) else path)
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            links.append(f'<a href="{href}"><img src="{href}" alt="evidencia"></a>')
        else:
            links.append(f'<a href="{href}">{escape(path.name)}</a>')
    return f'<div class="evidence">{"".join(links)}</div>' if links else ""


def _profile_chip(observed: Observed | None) -> str:
    profile = observed.get("profile") if observed else None
    if not isinstance(profile, dict) or not profile.get("learned_with"):
        return ""
    when = str(profile.get("learned_at") or "")[:10]
    return (
        f"<span>Perfil aprendido con <b>{escape(str(profile['learned_with']))}</b>"
        f"{escape(' el ' + when) if when else ''}</span>"
    )


def _href(path: Path) -> str:
    """URL relativa: "/" también en Windows y espacios, "#" o acentos codificados."""
    return escape(quote(path.as_posix(), safe="/"))


def _describe_check(check_id: str) -> str:
    try:
        return DESCRIPTIONS[Check(check_id)]
    except ValueError:
        return check_id


def overall_status(runs: Sequence[ScenarioRun], info: RunInfo) -> Status:
    """PASS solo si se ejecutaron todos los escenarios pedidos y todos pasaron."""
    executed = {run.scenario for run in runs}
    if not runs or not set(info.requested) <= executed:
        return Status.FAIL
    return Status.PASS if all(run.status is Status.PASS for run in runs) else Status.FAIL


def _badge(status: Status) -> str:
    icon = "✓" if status is Status.PASS else "✗"
    return f'<span class="badge {status.value.lower()}">{icon} {status.value}</span>'


_CSS = """
:root { --bg:#f6f7f9; --card:#fff; --fg:#1b1b1f; --muted:#5f6068; --line:#e3e3e8;
  --accent:#2457d6; --pass:#1a7f37; --pass-bg:#e7f5ec; --fail:#c62828; --fail-bg:#fdecec;
  --na:#5f6068; --na-bg:#f0f0f3; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111114; --card:#1a1a1f; --fg:#ececf1; --muted:#a2a2ad; --line:#2c2c33;
    --accent:#7aa2ff; --pass:#3fb950; --pass-bg:#12301c; --fail:#ff6b6b; --fail-bg:#3a1717;
    --na:#a2a2ad; --na-bg:#25252b; }
}
body { margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width:1180px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:26px; margin:0 0 4px; }
h2 { font-size:20px; margin:36px 0 6px; display:flex; flex-wrap:wrap; gap:10px;
  align-items:center; }
h3 { font-size:15px; margin:0 0 10px; }
.meta, .hint, .muted { color:var(--muted); }
.meta { margin:4px 0; } .hint { font-size:13px; margin:6px 0 0; }
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:12px;
  margin:18px 0; }
.kpi, .panel, .plain { background:var(--card); border:1px solid var(--line); border-radius:12px; }
.kpi { padding:12px 14px; }
.kpi-label { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }
.kpi-value { font-size:22px; font-weight:700; margin:4px 0 2px; }
.kpi-note { color:var(--muted); font-size:12px; }
.panel { padding:14px 16px; margin:12px 0; }
.plain { padding:4px 16px; margin:12px 0; }
details.panel summary { cursor:pointer; } details.panel summary h3 { display:inline; }
.chips { display:flex; flex-wrap:wrap; gap:8px; margin:6px 0 10px; }
.chips span { background:var(--card); border:1px solid var(--line); border-radius:999px;
  padding:2px 10px; font-size:13px; color:var(--muted); }
.chips b { color:var(--fg); }
table { width:100%; border-collapse:collapse; }
th, td { text-align:left; vertical-align:top; padding:8px; border-bottom:1px solid var(--line); }
.scroll { overflow-x:auto; }
.grid th, .grid td, .values th, .values td { white-space:nowrap; }
.grid th.check { white-space:normal; min-width:220px; font-weight:500; }
.cell { font-weight:600; font-size:13px; border-radius:6px; }
.grid td.cell { border:2px solid var(--card); }
.cell.ok { color:var(--pass); background:var(--pass-bg); }
.cell.ko { color:var(--fail); background:var(--fail-bg); }
.cell.na { color:var(--na); background:var(--na-bg); }
.cell.none { color:var(--muted); text-align:center; }
.cell small { display:block; font-weight:500; font-size:11px; opacity:.8; }
.badge { display:inline-block; padding:1px 10px; border-radius:999px; font-weight:700;
  font-size:13px; color:#fff; white-space:nowrap; }
.badge.pass { background:var(--pass); } .badge.fail { background:var(--fail); }
.equation { display:flex; flex-wrap:wrap; align-items:baseline; gap:8px; margin-top:12px;
  padding:10px 14px; border-radius:10px; font-size:17px; }
.equation.ok { background:var(--pass-bg); } .equation.ko { background:var(--fail-bg); }
.equation i { color:var(--muted); font-style:normal; }
.equation b { margin-left:auto; } .equation.ok b { color:var(--pass); }
.equation.ko b { color:var(--fail); }
.equation small { color:var(--muted); width:100%; order:9; font-size:12px; }
.panel.demo { border:2px dashed var(--fail); }
.panel.demo p.cell { display:inline-block; padding:4px 10px; }
.reasons li { margin:4px 0; }
.gallery { display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:12px; }
.gallery figure { margin:0; }
.gallery img { width:100%; border-radius:8px; border:1px solid var(--line); display:block; }
.gallery figcaption { font-size:12px; color:var(--muted); margin-top:4px; }
.chart { width:100%; height:auto; max-height:260px; }
.chart .gridline { stroke:var(--line); stroke-width:1; }
.chart .axis { fill:var(--muted); font-size:11px; }
.chart .threshold { stroke:var(--muted); stroke-width:1; stroke-dasharray:4 4; }
.chart .line { fill:none; stroke:var(--accent); stroke-width:2; stroke-linejoin:round; }
.chart .dot { fill:var(--accent); stroke:var(--card); stroke-width:2; }
.chart .mark { stroke:var(--fg); stroke-width:1; opacity:.35; }
.timeline { margin:8px 0 0; padding-left:22px; columns:2; font-size:13px; }
.timeline .when { color:var(--muted); font-variant-numeric:tabular-nums; }
.error { color:var(--fail); }
.fault { border:2px dashed var(--fail); border-radius:8px; padding:8px 12px; font-weight:600; }
.evidence img { max-width:180px; margin:4px 4px 0 0; border:1px solid var(--line);
  border-radius:4px; }
.missing { color:var(--muted); font-size:13px; margin-right:8px; }
ul { margin:0; padding-left:18px; }
a { color:var(--accent); }
.story { font-size:16px; background:var(--card); border:1px solid var(--line);
  border-left:4px solid var(--accent); border-radius:0 12px 12px 0; padding:10px 14px; }
.stages { display:flex; height:22px; border-radius:6px; overflow:hidden; gap:2px;
  background:var(--card); }
.stages .seg { background:var(--accent); opacity:.8; min-width:2px; }
.stages .seg:nth-child(even) { opacity:.45; }
.message { margin:12px 0 0; padding:12px 16px; border-left:4px solid var(--accent);
  background:var(--na-bg); border-radius:0 10px 10px 0; font-size:17px; }
.message small { display:block; color:var(--muted); font-size:12px; margin-top:6px; }
@media (max-width:700px) { .timeline { columns:1; } }
@media print {
  body { background:#fff; font-size:12px; } main { padding:0; }
  .panel, .kpi, figure, tr { break-inside:avoid; }
  .scroll { overflow:visible; }
  .grid th, .grid td, .values th, .values td { white-space:normal; font-size:10.5px; padding:5px; }
  .grid th.check { min-width:0; }
  .evidence img { max-width:140px; }
}
"""
