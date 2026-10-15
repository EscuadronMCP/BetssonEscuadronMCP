"""Incorpora un juego nuevo: la IA aprende su pantalla y el resultado se valida antes de guardarse.

No gira nunca. Validaciones (todas obligatorias):
1. Con las etiquetas aprendidas, el OCR lee crédito y apuesta.
2. El crédito leído coincide con el saldo de la cabecera de Betsson (la IA no lo ha inventado).
3. Pulsar el botón aprendido de bajar apuesta hace que la apuesta leída baje de verdad.
Si el modelo barato no lo consigue, se repite una vez con el de respaldo.
"""

import re
import time
from dataclasses import dataclass
from decimal import Decimal

from betsson_validator.browser import browser_context
from betsson_validator.casino.betsson import BetssonCasino
from betsson_validator.evidence import EvidenceRecorder
from betsson_validator.game.player import GameError, Image, ScreenGame, ScreenModel
from betsson_validator.perception.learner import DEFAULT_MODEL, FALLBACK_MODEL
from betsson_validator.perception.motion import motion_score
from betsson_validator.profiles import GameProfile
from betsson_validator.runner import RunContext
from betsson_validator.security import audit_and_quarantine, scrub_trace

_LOADING_TIMEOUT_S = 150
_STILL_SCORE = 0.01
_STILL_SAMPLES = 3
_MIN_LOADING_S = 15
_MAX_LOADING_S = 45


class LearningError(RuntimeError):
    pass


@dataclass(frozen=True)
class LearnResult:
    profile_path: str
    model: str
    checks: tuple[str, ...]


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
            for model_name in (DEFAULT_MODEL, FALLBACK_MODEL):
                profile = GameProfile(ctx.provider.id, ctx.game, "", "", "")
                model = ScreenModel(profile, ctx.reader, ctx.market.currency, ctx.learner)
                game = ScreenGame(
                    page=casino.page,
                    handle=handle,
                    model=model,
                    evidence=files,
                    message_pattern=re.compile(ctx.market.ui.insufficient_funds_pattern),
                    dismiss_labels=ctx.market.ui.dismiss_labels,
                )
                try:
                    checks = _learn_and_validate(game, model, model_name, balance.amount)
                except (GameError, LearningError) as error:
                    last_error = str(error)
                    continue
                profile.learned_with = model_name
                path = profile.save(ctx.profiles_dir)
                return LearnResult(str(path), model_name, checks)
            raise LearningError(f"El perfil aprendido no superó la validación: {last_error}")
    finally:
        scrub_trace(evidence_dir / "trace.zip", secrets)
        audit_and_quarantine(evidence_dir, secrets)


def _learn_and_validate(
    game: ScreenGame, model: ScreenModel, model_name: str, betsson_balance: Decimal
) -> tuple[str, ...]:
    if model.learner is None:
        raise LearningError("No hay IA de visión configurada.")
    image = _wait_until_loaded(game)
    analysis = model.learner.analyze(image, model=model_name)
    model.apply(analysis, image)
    if analysis.is_intro_screen and analysis.continue_button is not None:
        point = model.locate("continue", image)
        if point is None:
            raise LearningError("No se reencuentra el botón de continuar propuesto.")
        game.click(point)
        game.page.wait_for_timeout(3000)
        image = _wait_until_loaded(game)
        analysis = model.learner.analyze(image, model=model_name)
        model.apply(analysis, image)

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
    checks = [
        f"crédito {hud.credit.money} = saldo de Betsson",
        f"apuesta leída {hud.bet.money}",
    ]
    for control in ("spin", "bet_down"):
        if model.locate(control, image) is None:
            raise LearningError(f"No se reencuentra el control '{control}' propuesto.")
    before = hud.bet.money.amount
    game.click(model.locate_or_learn("bet_down", image))
    game.page.wait_for_timeout(800)
    after_hud, _ = model.read(game.capture())
    if after_hud.bet is None or after_hud.bet.money.amount >= before:
        raise LearningError("Pulsar el botón aprendido de bajar apuesta no bajó la apuesta.")
    checks.append(f"bajar apuesta: {before} → {after_hud.bet.money.amount}")
    return tuple(checks)


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
