"""Secciones visuales del informe: resumen, testigos, dinero, movimiento, eventos y capturas.

Cada función recibe datos ya observados y devuelve HTML escapado; no decide veredictos (eso es
de la evaluación), solo los muestra con toda la información disponible. El estado siempre lleva
icono y texto además del color.
"""

from collections.abc import Sequence
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from betsson_validator.domain.checks import DESCRIPTIONS, Check, Scenario
from betsson_validator.domain.run import ScenarioRun
from betsson_validator.domain.verdict import Outcome, Status
from betsson_validator.perception.motion import MotionThresholds, detect_spin_lifecycle
from betsson_validator.report.charts import motion_chart
from betsson_validator.report.observed import Observed, amount, currency

WITNESSES = (
    "pantalla del juego",
    "movimiento de los rodillos",
    "cabecera de Betsson",
    "servidor del juego",
    "eventos del juego",
)
_OUTCOME_CELL = {
    Outcome.CONFIRMS: ("ok", "✓", "confirma"),
    Outcome.CONTRADICTS: ("ko", "✗", "contradice"),
    Outcome.UNAVAILABLE: ("na", "—", "no disponible"),
}
_CAPTIONS = {
    "saldo_betsson_antes": "Saldo de Betsson antes",
    "apuesta_minima": "Juego listo, apuesta mínima",
    "girando": "Durante el giro",
    "despues_de_girar": "Tras la tirada",
    "saldo_betsson_despues": "Saldo de Betsson después",
    "fallo_pantalla": "Pantalla al fallar",
}


def money(value: Decimal | None, code: str | None = "EUR") -> str:
    if value is None:
        return "—"
    text = f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    return f"{text} €" if code in {None, "EUR"} else f"{text} {code}"


# --- Panel de resumen ---------------------------------------------------------------------------


def dashboard(runs: Sequence[ScenarioRun], overall: Status, code_version: str) -> str:
    checks = [result for run in runs for result in run.results]
    expected = sum(len(run.results) + len(run.missing_checks()) for run in runs)
    passed = sum(result.status is Status.PASS for result in checks)
    longest = max(((run.finished_at - run.started_at).total_seconds() for run in runs), default=0)
    ai_notes = [note for run in runs for note in run.notes if "IA" in note]
    tiles = (
        ("Resultado global", _badge(overall), ""),
        ("Comprobaciones superadas", f"{passed} de {expected}", "cada una con varios testigos"),
        (
            "Escenarios",
            f"{sum(run.status is Status.PASS for run in runs)} de {len(runs)} en PASS",
            ", ".join(sorted({run.game for run in runs})),
        ),
        ("Duración", f"{longest:.0f} s", "escenarios en paralelo"),
        (
            "Uso de IA",
            "0 llamadas" if not ai_notes else f"{len(ai_notes)} aviso(s)",
            "perfil aprendido, ejecución local" if not ai_notes else "ver notas del escenario",
        ),
        ("Versión del código", escape(code_version[:7]), "SHA de la ejecución"),
    )
    cells = "".join(
        f'<div class="kpi"><div class="kpi-label">{escape(label)}</div>'
        f'<div class="kpi-value">{value}</div><div class="kpi-note">{escape(note)}</div></div>'
        for label, value, note in tiles
    )
    return f'<div class="kpis">{cells}</div>'


def _badge(status: Status) -> str:
    icon = "✓" if status is Status.PASS else "✗"
    return f'<span class="badge {status.value.lower()}">{icon} {status.value}</span>'


# --- Cuadrícula de testigos ---------------------------------------------------------------------


def witness_grid(run: ScenarioRun) -> str:
    """Comprobaciones por testigos: qué dijo cada uno de cada hecho."""
    if not run.results:
        return ""
    names = [
        w for w in WITNESSES if any(t.witness == w for r in run.results for t in r.testimonies)
    ]
    head = "".join(f"<th>{escape(name[:1].upper() + name[1:])}</th>" for name in names)
    rows = []
    for result in run.results:
        by_witness = {t.witness: t for t in result.testimonies}
        cells = []
        for name in names:
            testimony = by_witness.get(name)
            if testimony is None:
                cells.append('<td class="cell none" title="no interviene">·</td>')
                continue
            css, icon, label = _OUTCOME_CELL[testimony.outcome]
            cells.append(
                f'<td class="cell {css}" title="{escape(testimony.detail)}">{icon} {label}</td>'
            )
        rows.append(
            f"<tr><th class='check'>{escape(_describe(result.check))}</th>"
            f"<td>{_badge(result.status)}</td>{''.join(cells)}</tr>"
        )
    return (
        '<div class="scroll"><table class="grid"><thead><tr><th>Comprobación</th>'
        f"<th>Resultado</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        '<p class="hint">Pasa el ratón por una celda para ver lo que dijo ese testigo.</p>'
    )


def _describe(check_id: str) -> str:
    try:
        return DESCRIPTIONS[Check(check_id)]
    except ValueError:
        return check_id


# --- Valores observados y regla del dinero ------------------------------------------------------


def observed_values(observed: Observed, scenario: Scenario) -> str:
    """Valores que dio cada testigo; una fila en la que no coinciden se marca como discrepancia."""
    get = observed.get
    rows: list[tuple[str, list[Decimal | None]]] = [
        (
            "Saldo antes",
            [
                amount(get("screen_before", "credit")),
                amount(get("betsson_before")),
                amount(get("network", "balance_before")),
                amount(get("events", "balance_before")),
            ],
        ),
        (
            "Apuesta",
            [
                amount(get("screen_before", "bet")),
                None,
                amount(get("network", "wager_accepted")),
                amount(get("events", "bet")),
            ],
        ),
        (
            "Premio",
            [
                amount(get("screen_after", "win")) or Decimal("0"),
                None,
                amount(get("network", "declared_win")),
                amount(get("events", "win")),
            ],
        ),
        (
            "Saldo después",
            [
                amount(get("screen_after", "credit")),
                amount(get("betsson_after")),
                amount(get("network", "balance_after")),
                amount(get("events", "balance_after")),
            ],
        ),
    ]
    if scenario is Scenario.INSUFFICIENT_BALANCE:
        rows = [row for row in rows if row[0] != "Premio"]
    code = currency(get("betsson_before")) or "EUR"
    body = "".join(_value_row(label, values, code) for label, values in rows)
    head = "".join(
        f"<th>{name}</th>"
        for name in ("Pantalla del juego", "Cabecera de Betsson", "Servidor", "Eventos")
    )
    return (
        f'<div class="scroll"><table class="values"><thead><tr><th>Hecho</th>{head}<th></th>'
        f"</tr></thead><tbody>{body}{_text_rows(observed)}</tbody></table></div>"
        f"{_money_rule(observed, scenario, code)}"
    )


def _value_row(label: str, values: list[Decimal | None], code: str) -> str:
    known = {value for value in values if value is not None}
    agree = len(known) <= 1
    flag = (
        '<td class="cell ok">✓ coinciden</td>'
        if agree and known
        else '<td class="cell ko">✗ discrepancia</td>'
        if not agree
        else '<td class="cell na">— sin datos</td>'
    )
    cells = "".join(f"<td>{money(value, code)}</td>" for value in values)
    return f"<tr><th>{escape(label)}</th>{cells}{flag}</tr>"


def _text_rows(observed: Observed) -> str:
    get = observed.get
    seen = ", ".join(get("screen_before", "currencies_seen") or []) or "—"
    event_currencies = ", ".join(get("events", "currencies") or []) or "—"
    languages = ", ".join(get("events", "languages") or []) or "—"
    header_currency = currency(get("betsson_before")) or "—"
    rows = [
        ("Divisa", seen, header_currency, "—", event_currencies),
        ("Idioma", "—", "—", "—", languages),
    ]
    return "".join(
        f"<tr><th>{escape(label)}</th>{''.join(f'<td>{escape(str(v))}</td>' for v in values)}"
        "<td></td></tr>"
        for label, *values in rows
    )


def _message_box(observed: Observed) -> str:
    """El mensaje que vio el jugador, tal cual lo leyó el OCR, con el idioma del juego."""
    message = observed.get("screen_after", "message")
    notice = observed.get("screen_after", "notice")
    languages = ", ".join(observed.get("events", "languages") or []) or "no comunicado"
    if not message and not notice:
        return '<div class="equation ko">✗ No apareció ningún mensaje en pantalla</div>'
    return (
        f'<blockquote class="message">«{escape(str(message or notice))}»'
        f"<small>Mensaje leído en la pantalla del juego · idioma comunicado por el juego: "
        f"{escape(languages)}</small></blockquote>"
    )


def _money_rule(observed: Observed, scenario: Scenario, code: str) -> str:
    get = observed.get
    if scenario is Scenario.INSUFFICIENT_BALANCE:
        before, after = amount(get("betsson_before")), amount(get("betsson_after"))
        same = before is not None and before == after
        return (
            f"{_message_box(observed)}"
            f'<div class="equation {"ok" if same else "ko"}">Saldo de Betsson: '
            f"{money(before, code)} → {money(after, code)} "
            f"<b>{'✓ sin cambios' if same else '✗ ha cambiado'}</b></div>"
        )
    before, after = amount(get("betsson_before")), amount(get("betsson_after"))
    bet = amount(get("screen_before", "bet"))
    win = amount(get("screen_after", "win")) or Decimal("0")
    if before is None or after is None or bet is None:
        return ""
    expected = before - bet + win
    ok = expected == after
    return (
        f'<div class="equation {"ok" if ok else "ko"}">'
        f"<span>{money(before, code)}</span> <i>−</i> <span>{money(bet, code)}</span> "  # noqa: RUF001
        f"<i>+</i> <span>{money(win, code)}</span> <i>=</i> <span>{money(expected, code)}</span>"
        f"<small>saldo antes − apuesta + premio</small>"  # noqa: RUF001
        f"<b>{'✓' if ok else '✗'} Betsson muestra {money(after, code)}</b></div>"
    )


# --- Movimiento, eventos y capturas -------------------------------------------------------------


def motion_section(observed: Observed) -> str:
    scores = [float(s) for s in (observed.get("motion_scores") or []) if isinstance(s, int | float)]
    raw = observed.get("motion_thresholds") or {}
    if not scores or not isinstance(raw, dict):
        return ""
    try:
        thresholds = MotionThresholds(**raw)
    except TypeError:
        return ""
    lifecycle = detect_spin_lifecycle(scores, thresholds)
    verdict = (
        "el juego se movió y volvió al reposo"
        if lifecycle.completed
        else "el giro empezó pero no terminó"
        if lifecycle.started
        else "sin giro: el juego no se movió"
    )
    chart = motion_chart(
        scores, thresholds.start, thresholds.still, lifecycle.start_index, lifecycle.end_index
    )
    return (
        f"{chart}"
        f'<p class="hint">Fracción de la zona de rodillos que cambia entre capturas consecutivas: '
        f"{escape(verdict)} ({len(scores)} capturas, pico {lifecycle.peak_score:.2f}).</p>"
    )


def events_timeline(observed: Observed) -> str:
    events = observed.events
    if not events:
        return ""
    first = next((e.get("t") for e in events if isinstance(e.get("t"), int | float)), None)
    items = []
    for event in events:
        raw = event.get("data")
        data: dict[str, Any] = raw if isinstance(raw, dict) else {}
        name = str(data.get("name") or data.get("event") or "?")
        offset = event.get("t")
        when = (
            f"+{(offset - first) / 1000:.1f} s"
            if isinstance(offset, int | float) and first is not None
            else ""
        )
        details = [
            f"{label} {data[key]}"
            for key, label in (("betAmount", "apuesta"), ("winAmount", "premio"))
            if key in data
        ]
        items.append(
            f'<li><span class="when">{escape(when)}</span> <b>{escape(name)}</b> '
            f'<span class="muted">{escape(" · ".join(details))}</span></li>'
        )
    return f'<ol class="timeline">{"".join(items)}</ol>'


def gallery(folder: Path, out_dir: Path) -> str:
    figures = []
    for path in sorted(folder.glob("*.jpg")):
        key = path.stem.split("_", 1)[1] if path.stem[:2].isdigit() else path.stem
        caption = _CAPTIONS.get(key, key.replace("_", " "))
        href = escape(quote(path.relative_to(out_dir).as_posix(), safe="/"))
        figures.append(
            f'<figure><a href="{href}"><img src="{href}" alt="{escape(caption)}"></a>'
            f"<figcaption>{escape(caption)}</figcaption></figure>"
        )
    return f'<div class="gallery">{"".join(figures)}</div>' if figures else ""


# --- Cronología y resumen en lenguaje llano -----------------------------------------------------


def stages_timeline(observed: Observed) -> str:
    """Barra de tiempos: cuánto duró cada etapa, de abrir la web al saldo final."""
    stages = [
        (str(stage.get("name", "")), float(stage["s"]))
        for stage in observed.get("stages") or []
        if isinstance(stage, dict) and isinstance(stage.get("s"), int | float)
    ]
    if not stages:
        return ""
    total = stages[-1][1] or 1.0
    previous = 0.0
    segments, items = [], []
    for name, end in stages:
        length = max(end - previous, 0.0)
        segments.append(
            f'<span class="seg" style="width:{100 * length / total:.2f}%" '
            f'title="{escape(name)}: {length:.1f} s"></span>'
        )
        items.append(
            f"<li><b>{escape(name)}</b> <span class='muted'>{length:.1f} s "
            f"(acumulado {end:.1f} s)</span></li>"
        )
        previous = end
    return (
        f'<div class="stages">{"".join(segments)}</div><ol class="timeline">{"".join(items)}</ol>'
    )


def narrative(observed: Observed, scenario: Scenario, game: str) -> str:
    """Lo que pasó, en una frase, para quien no conoce el proyecto."""
    get = observed.get
    code = currency(get("betsson_before")) or "EUR"
    bet = amount(get("screen_before", "bet"))
    credit_before, credit_after = (
        amount(get("screen_before", "credit")),
        amount(get("screen_after", "credit")),
    )
    betsson_before, betsson_after = amount(get("betsson_before")), amount(get("betsson_after"))
    if scenario is Scenario.INSUFFICIENT_BALANCE:
        message = get("screen_after", "message")
        shown = f"mostró «{message}»" if message else "no mostró ningún mensaje"
        unchanged = credit_before == credit_after and betsson_before == betsson_after
        return (
            f"Con {money(credit_before, code)} de crédito y una apuesta de {money(bet, code)}, "
            f"se pulsó girar en {game}: el juego {shown}. "
            f"{'Ningún saldo cambió.' if unchanged else 'Algún saldo cambió.'}"
        )
    win = amount(get("screen_after", "win")) or Decimal("0")
    spun = bool(get("motion", "completed"))
    result = f"pagó {money(win, code)}" if win else "no hubo premio"
    rule = (
        betsson_before is not None
        and bet is not None
        and betsson_after == betsson_before - bet + win
    )
    return (
        f"Se apostaron {money(bet, code)} en {game}. "
        f"{'El juego giró y ' + result if spun else 'El juego no llegó a girar'}. "
        f"El crédito del juego pasó de {money(credit_before, code)} a {money(credit_after, code)} "
        f"y el saldo de Betsson de {money(betsson_before, code)} a {money(betsson_after, code)}: "
        f"{'cuadra con la regla del reto.' if rule else 'NO cuadra con la regla del reto.'}"
    )
