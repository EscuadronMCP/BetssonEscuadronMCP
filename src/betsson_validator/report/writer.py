"""Informe de resultados en JSON (para máquinas) y HTML autocontenido (para personas)."""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from html import escape
from pathlib import Path

from betsson_validator.domain.checks import DESCRIPTIONS, SCENARIO_TITLES, Check
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import CheckResult, Outcome, Status

_OUTCOME_LABELS = {
    Outcome.CONFIRMS: "confirma",
    Outcome.CONTRADICTS: "contradice",
    Outcome.UNAVAILABLE: "no disponible",
}


def write_report(runs: Sequence[ScenarioRun], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "report.json"
    html_path = out_dir / "index.html"
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": _overall(runs).value,
        "runs": [{**run.model_dump(mode="json"), "status": run.status.value} for run in runs],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(runs, out_dir), encoding="utf-8")
    return json_path, html_path


def render_html(runs: Sequence[ScenarioRun], out_dir: Path) -> str:
    overall = _overall(runs)
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
{sections}
</main>
</body>
</html>
"""


def render_markdown(runs: Sequence[ScenarioRun]) -> str:
    """Resumen para la página de la ejecución en GitHub Actions."""
    lines = [
        f"## Validación de juegos: {_overall(runs).value}",
        "",
        "| Escenario | Mercado | Juego | Comprobación | Resultado | Motivo |",
        "|---|---|---|---|---|---|",
    ]
    for run in runs:
        title = SCENARIO_TITLES[run.scenario]
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


def _render_run(run: ScenarioRun, out_dir: Path) -> str:
    rows = "\n".join(_render_result_row(result, out_dir) for result in run.results)
    missing = "".join(
        f"<tr><td>{escape(DESCRIPTIONS[c])}</td><td>{_badge(Status.FAIL)}</td>"
        "<td>No se llegó a evaluar.</td><td></td></tr>"
        for c in run.missing_checks()
    )
    error = f'<p class="error">Error: {escape(run.error)}</p>' if run.error else ""
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
<table>
<thead><tr><th>Comprobación</th><th>Resultado</th><th>Motivo</th><th>Testigos</th></tr></thead>
<tbody>
{rows}
{missing}
</tbody>
</table>
</section>"""


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
        href = path.relative_to(out_dir) if path.is_relative_to(out_dir) else path
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            links.append(
                f'<a href="{escape(str(href))}"><img src="{escape(str(href))}" alt="evidencia"></a>'
            )
        else:
            links.append(f'<a href="{escape(str(href))}">{escape(path.name)}</a>')
    return f'<div class="evidence">{"".join(links)}</div>' if links else ""


def _describe_check(check_id: str) -> str:
    try:
        return DESCRIPTIONS[Check(check_id)]
    except ValueError:
        return check_id


def _overall(runs: Sequence[ScenarioRun]) -> Status:
    if runs and all(run.status is Status.PASS for run in runs):
        return Status.PASS
    return Status.FAIL


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
.evidence img { max-width:220px; margin:4px 4px 0 0; border:1px solid var(--line); }
@media (max-width:700px) {
  table, thead, tbody, tr, th, td { display:block; } thead { display:none; }
}
"""
