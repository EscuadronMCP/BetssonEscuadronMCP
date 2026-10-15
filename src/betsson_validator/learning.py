"""Incorpora un juego nuevo: la IA aprende su pantalla y el resultado se valida antes de guardarse.

No gira nunca. Validaciones (todas obligatorias):
1. Con las etiquetas aprendidas, el OCR lee crédito y apuesta.
2. El crédito leído coincide con el saldo de la cabecera de Betsson (la IA no lo ha inventado).
3. Pulsar el botón aprendido de bajar apuesta hace que la apuesta leída baje de verdad.
Si el modelo barato no lo consigue, se repite una vez con el de respaldo.
"""

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from betsson_validator.browser import browser_context
from betsson_validator.casino.betsson import BetssonCasino
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.game.player import (
    GameError,
    Image,
    ScreenGame,
    ScreenModel,
    control_template,
)
from betsson_validator.perception.learner import DEFAULT_MODEL, FALLBACK_MODEL, ScreenAnalysis
from betsson_validator.perception.motion import motion_score
from betsson_validator.profiles import GameProfile
from betsson_validator.runner import RunContext
from betsson_validator.security import audit_and_quarantine, scrub_trace

_LOADING_TIMEOUT_S = 150
_STILL_SCORE = 0.01
_STILL_SAMPLES = 3
_MIN_LOADING_S = 15
_MAX_LOADING_S = 45
_BET_PRESSES = 3
_SCREEN_CHANGED = 0.3  # fracción de píxeles: la pantalla de bienvenida desapareció


class LearningError(RuntimeError):
    pass


@dataclass(frozen=True)
class LearnResult:
    profile_path: str
    model: str
    checks: tuple[str, ...]
    ai_cost_usd: float


def learn_game(ctx: RunContext) -> LearnResult:
    if ctx.learner is None:
        raise LearningError("Falta ANTHROPIC_API_KEY: el aprendizaje necesita la IA de visión.")
    evidence_dir = ctx.out_dir / "aprendizaje"
    files = EvidenceRecorder(evidence_dir)
    credentials = ctx.market.accounts.funded.resolve()
    secrets = (credentials.email.get_secret_value(), credentials.password.get_secret_value())
    try:
        with browser_context(ctx.settings, evidence_dir) as context:
            casino = BetssonCasino(
                context.new_page(), ctx.market, typing_delay_ms=ctx.settings.slow_typing_ms
            )
            casino.open()
            casino.login(credentials)
            balance = casino.read_balance()
            handle = casino.launch_game(ctx.provider, ctx.game)
            last_error = "sin intentos"
            # Controles que ya demostraron funcionar al pulsarlos: se conservan entre intentos.
            proven: dict[str, Image] = {}
            for model_name in (DEFAULT_MODEL, FALLBACK_MODEL):
                profile = GameProfile(ctx.provider.id, ctx.game, "", "", "")
                model = ScreenModel(
                    profile,
                    ctx.reader,
                    ctx.market.currency,
                    ctx.learner,
                    win_candidates=ctx.market.ui.win_label_candidates,
                )
                game = ScreenGame(
                    page=casino.page,
                    handle=handle,
                    model=model,
                    evidence=files,
                    message_pattern=re.compile(ctx.market.ui.insufficient_funds_pattern),
                    dismiss_labels=ctx.market.ui.dismiss_labels,
                )
                try:
                    checks = _learn_and_validate(game, model, model_name, balance.amount, proven)
                except (GameError, LearningError) as error:
                    last_error = str(error)
                    continue
                profile.templates.update(proven)
                profile.learned_with = model_name
                path = profile.save(ctx.profiles_dir)
                return LearnResult(str(path), model_name, checks, ctx.learner.cost_usd)
            raise LearningError(f"El perfil aprendido no superó la validación: {last_error}")
    finally:
        scrub_trace(evidence_dir / "trace.zip", secrets)
        audit_and_quarantine(evidence_dir, secrets)


def _learn_and_validate(
    game: ScreenGame,
    model: ScreenModel,
    model_name: str,
    betsson_balance: Decimal,
    proven: dict[str, Image],
) -> tuple[str, ...]:
    if model.learner is None:
        raise LearningError("No hay IA de visión configurada.")
    image = _wait_until_loaded(game)
    analysis = _analyze(game, model, image, model_name, "pantalla_inicial")
    # Sin etiquetas de crédito ni apuesta no puede ser la pantalla de juego, diga lo que diga el
    # modelo: es la de bienvenida y su botón principal solo sirve para continuar.
    no_hud = analysis.credit_label is None and analysis.bet_label is None
    if analysis.is_intro_screen or no_hud:
        box = analysis.continue_button
        if box is None and _hud_hidden(model, image):
            box = analysis.spin_button
        if box is None:
            raise LearningError("Pantalla de bienvenida sin botón para continuar.")
        x, y, w, h = box.as_tuple()
        height, width = image.shape[:2]
        game.click(((x + w / 2) / width, (y + h / 2) / height))
        model.profile.templates.pop("spin", None)  # era el de continuar, no el de girar
        game.page.wait_for_timeout(3000)
        if motion_score(image, game.capture()) > _SCREEN_CHANGED:
            proven["continue"] = control_template(image, (x, y, w, h))
        image = _wait_until_loaded(game)
        analysis = _analyze(game, model, image, model_name, "pantalla_de_juego")

    hud, _ = model.read(image)
    if hud.credit is None or hud.bet is None:
        raise LearningError(
            f"Con las etiquetas aprendidas ({model.profile.credit_label!r}, "
            f"{model.profile.bet_label!r}) no se leen crédito y apuesta."
        )
    if hud.credit.money.amount != betsson_balance:
        raise LearningError(
            f"El crédito leído ({hud.credit.money}) no coincide con el saldo de Betsson."
        )
    # Lectura validada (el crédito coincide con Betsson): se recuerda dónde está cada valor.
    model.remember_hud_positions(hud, image)
    checks = [
        f"crédito {hud.credit.money} = saldo de Betsson",
        f"apuesta leída {hud.bet.money}",
    ]
    for control in ("spin", "bet_down", "bet_up"):
        if model.locate(control, image) is None:
            raise LearningError(f"No se reencuentra el control '{control}' propuesto.")
    # Cada botón de apuesta se valida por su efecto: "+" la sube y "-" la baja. Así funciona
    # aunque la apuesta ya esté en el mínimo y la deja como estaba.
    start = hud.bet.money.amount
    raised = _press_until(game, model, "bet_up", lambda amount: amount > start)
    checks.append(f"subir apuesta: {start} → {raised}")
    lowered = _press_until(game, model, "bet_down", lambda amount: amount < raised)
    checks.append(f"bajar apuesta: {raised} → {lowered}")
    return tuple(checks)


def _press_until(
    game: ScreenGame, model: ScreenModel, control: str, done: Callable[[Decimal], bool]
) -> Decimal:
    """Pulsa un control hasta 3 veces (algunos juegos abren antes un panel) y lee el efecto."""
    for press in range(1, _BET_PRESSES + 1):
        game.click(model.locate_or_learn(control, game.capture()))
        game.page.wait_for_timeout(800)
        after = game.capture()
        game.evidence.save_image(f"{control}_{press}", after)
        hud, _ = model.read(after)
        if hud.bet is not None and done(hud.bet.money.amount):
            return hud.bet.money.amount
    raise LearningError(f"Pulsar el control aprendido '{control}' no cambió la apuesta.")


def _hud_hidden(model: ScreenModel, image: Image) -> bool:
    """El OCR no ve ningún importe del marcador: es seguro que no es la pantalla de juego."""
    hud, _ = model.read(image)
    return hud.credit is None and hud.bet is None and hud.win is None


def _analyze(
    game: ScreenGame, model: ScreenModel, image: Image, model_name: str, name: str
) -> ScreenAnalysis:
    """Analiza con la IA, aplica el resultado y guarda captura + respuesta como evidencia."""
    if model.learner is None:
        raise LearningError("No hay IA de visión configurada.")
    game.evidence.save_image(name, image)
    analysis = model.learner.analyze(image, model=model_name)
    game.evidence.save_json(f"{name}_{model_name}", analysis.model_dump())
    model.apply(analysis, image)
    return analysis


def _wait_until_loaded(game: ScreenGame) -> Image:
    """Espera a que la pantalla deje de cambiar (fin de la carga) antes de gastar en la IA."""
    start = time.monotonic()
    previous = game.capture()
    still = 0
    while time.monotonic() - start < _LOADING_TIMEOUT_S:
        game.page.wait_for_timeout(1000)
        current = game.capture()
        moving = previous.shape != current.shape or motion_score(previous, current) >= _STILL_SCORE
        still = 0 if moving else still + 1
        previous = current
        elapsed = time.monotonic() - start
        if (still >= _STILL_SAMPLES and elapsed > _MIN_LOADING_S) or elapsed > _MAX_LOADING_S:
            return current  # quieta, o con animaciones de fondo que nunca se detienen
    raise LearningError("El juego no terminó de cargar a tiempo.")
