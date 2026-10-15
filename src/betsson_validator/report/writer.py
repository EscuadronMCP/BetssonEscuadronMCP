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
        "status": _overall(runs, info).value,
        "runs": [{**run.model_dump(mode="json"), "status": run.status.value} for run in runs],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(runs, out_dir, info), encoding="utf-8")
    return json_path, html_path


def _scope(info: RunInfo) -> str:
    titles = ", ".join(SCENARIO_TITLES[scenario] for scenario in info.requested)
    note = " (alcance parcial: no se pidieron todos los escenarios)" if info.partial else ""
    return f"Código {info.code_version[:12]} · escenarios solicitados: {titles}{note}"


def render_html(runs: Sequence[ScenarioRun], out_dir: Path, info: RunInfo | None = None) -> str:
    info = info or RunInfo(requested=tuple(run.scenario for run in runs))
    overall = _overall(runs, info)
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
<h1>Informe de validación de juegos</h1>
<p class="summary">Resultado global: {_badge(overall)} · {len(runs)} escenario(s) ·
generado {escape(datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"))}</p>
<p class="meta">{escape(_scope(info))}</p>
{_plain_summary(runs)}
{sections}
</main>
</body>
</html>
"""


def render_markdown(runs: Sequence[ScenarioRun], info: RunInfo | None = None) -> str:
    """Resumen para la página de la ejecución en GitHub Actions."""
    info = info or RunInfo(requested=tuple(run.scenario for run in runs))
    lines = [
        f"## Validación de juegos: {_overall(runs, info).value}",
        "",
        _scope(info),
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
    return f"""<section>
<h2>{escape(SCENARIO_TITLES[run.scenario])} {_badge(run.status)}</h2>
<p class="meta">Mercado <b>{escape(run.market)}</b> · proveedor <b>{escape(run.provider)}</b> ·
juego <b>{escape(run.game)}</b> · {escape(run.started_at.isoformat())} →
{escape(run.finished_at.isoformat())}</p>
{error}
{_render_media(run, out_dir)}
<table>
<thead><tr><th>Comprobación</th><th>Resultado</th><th>Motivo</th><th>Testigos</th></tr></thead>
<tbody>
{rows}
{missing}
</tbody>
</table>
</section>"""


_MEDIA = (
    ("fallo_pantalla.jpg", "Captura de la pantalla al fallar"),
    ("video/*.webm", "Vídeo de la ejecución"),
    ("trace.zip", "Traza de Playwright"),
    ("eventos_del_juego.json", "Eventos del juego (postMessage)"),
    ("trafico_juego_sin_tokens.json", "Tráfico del juego (sin tokens)"),
    ("resumen_observado.json", "Resumen de lo observado"),
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


def _href(path: Path) -> str:
    """URL relativa: "/" también en Windows y espacios, "#" o acentos codificados."""
    return escape(quote(path.as_posix(), safe="/"))


def _describe_check(check_id: str) -> str:
    try:
        return DESCRIPTIONS[Check(check_id)]
    except ValueError:
        return check_id


def _overall(runs: Sequence[ScenarioRun], info: RunInfo) -> Status:
    """PASS solo si se ejecutaron todos los escenarios pedidos y todos pasaron."""
    executed = {run.scenario for run in runs}
    if not runs or not set(info.requested) <= executed:
        return Status.FAIL
    return Status.PASS if all(run.status is Status.PASS for run in runs) else Status.FAIL


def _badge(status: Status) -> str:
    return f'<span class="badge {status.value.lower()}">{status.value}</span>'


_CSS = """
:root { --bg:#fff; --fg:#1b1b1f; --muted:#5f6068; --line:#e3e3e8;
  --pass:#1a7f37; --fail:#c62828; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#151518; --fg:#ececf1; --muted:#a2a2ad; --line:#2c2c33;
    --pass:#3fb950; --fail:#ff6b6b; }
}
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; }
main { max-width:1100px; margin:0 auto; padding:24px 16px; }
h1 { font-size:24px; margin:0 0 8px; } h2 { font-size:18px; margin:32px 0 4px; }
.summary, .meta { color:var(--muted); margin:4px 0; }
table { width:100%; border-collapse:collapse; margin-top:12px; }
th, td { text-align:left; vertical-align:top; padding:8px; border-bottom:1px solid var(--line); }
ul { margin:0; padding-left:18px; }
.badge { display:inline-block; padding:1px 8px; border-radius:10px; font-weight:600; color:#fff; }
.badge.pass { background:var(--pass); } .badge.fail { background:var(--fail); }
.error { color:var(--fail); }
.fault { border:2px dashed var(--fail); border-radius:8px; padding:8px 12px; font-weight:600; }
.plain { border:1px solid var(--line); border-radius:8px; padding:4px 14px; margin:12px 0; }
.evidence img { max-width:220px; margin:4px 4px 0 0; border:1px solid var(--line); }
.missing { color:var(--muted); font-size:13px; margin-right:8px; }
@media (max-width:700px) {
  table, thead, tbody, tr, th, td { display:block; } thead { display:none; }
}
"""
