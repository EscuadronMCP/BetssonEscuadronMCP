"""Tests con el tráfico real de una tirada en Sweet Bonanza 2500 (15/10), recortado y sin tokens."""

from decimal import Decimal

import pytest

from betsson_validator.providers.pragmatic.network import (
    GameServiceCall,
    NoSpinObservedError,
    balance_from_init,
    redact,
    summarize_round,
)

INIT = GameServiceCall.from_bodies(
    "action=doInit&symbol=vs20swbon2500_cv114&index=1&counter=1",
    "balance=64.70&balance_cash=64.70&c=0.10&l=20&na=s&defc=0.10",
)
SPIN_WITH_TUMBLE = GameServiceCall.from_bodies(
    "action=doSpin&c=0.01&l=20&bl=0&index=2&counter=3",
    "balance=64.50&c=0.01&l=20&tw=0.15&w=0.15&na=s&rs_p=0&rs_c=1",
)
TUMBLE_CONTINUATION = GameServiceCall.from_bodies(
    "action=doSpin&c=0.01&l=20&bl=0&index=3&counter=5",
    "balance=64.50&c=0.01&l=20&tw=0.15&w=0.00&na=c&rs_win=0.00",
)
COLLECT = GameServiceCall.from_bodies(
    "action=doCollect&index=4&counter=7", "balance=64.65&balance_cash=64.65&na=s"
)
LOSING_SPIN = GameServiceCall.from_bodies(
    "action=doSpin&c=0.01&l=20&bl=0", "balance=64.50&c=0.01&l=20&tw=0.00&w=0.00&na=s"
)


def test_real_winning_round_with_tumble_reconciles() -> None:
    calls = [INIT, SPIN_WITH_TUMBLE, TUMBLE_CONTINUATION, COLLECT]
    spin = summarize_round(calls)
    assert balance_from_init(calls[:1]) == Decimal("64.70")
    assert spin.wager_requested == Decimal("0.20")
    assert spin.wager_accepted == Decimal("0.20")
    assert spin.balance_after == Decimal("64.65")
    assert spin.declared_win == Decimal("0.15")
    assert spin.settled
    assert spin.calls == 3


def test_round_is_not_settled_until_collect() -> None:
    spin = summarize_round([INIT, SPIN_WITH_TUMBLE, TUMBLE_CONTINUATION])
    assert not spin.settled


def test_first_tumble_response_is_not_settled_even_with_na_s() -> None:
    assert not summarize_round([SPIN_WITH_TUMBLE]).settled


def test_losing_spin_is_settled_immediately() -> None:
    spin = summarize_round([INIT, LOSING_SPIN])
    assert spin.settled
    assert spin.declared_win == Decimal("0.00")


def test_no_spin_is_reported() -> None:
    with pytest.raises(NoSpinObservedError):
        summarize_round([INIT])


def test_redact_hides_session_tokens() -> None:
    raw = "action=doInit&mgckey=AUTHTOKEN@9a96~stylename@btsn~SESSION@1d10-ab&token=62a9"
    clean = redact(raw)
    assert "9a96" not in clean
    assert "1d10" not in clean
    assert "62a9" not in clean
    assert "action=doInit" in clean


def test_rejected_spin_request_is_not_an_accepted_wager() -> None:
    error = GameServiceCall.from_bodies("action=doSpin&c=0.01&l=20", "frozen=Internal+server+error")
    spin = summarize_round([INIT, error])
    assert spin.wager_requested == Decimal("0.20")
    assert spin.wager_accepted is None
    assert spin.balance_after is None
    assert not spin.settled


def test_malformed_amounts_are_ignored_not_crashing() -> None:
    weird = GameServiceCall.from_bodies(
        "action=doSpin&c=NaN&l=20", "balance=Infinity&c=0.01&l=20&tw=abc&na=s"
    )
    spin = summarize_round([weird])
    assert spin.wager_requested is None
    assert spin.balance_after is None
    assert spin.declared_win is None


def test_game_service_traffic_is_attributed_to_the_game_frame() -> None:
    """Auditoría R02 (NET-001/002): el texto "gameService" en la URL no basta."""
    from types import SimpleNamespace  # noqa: PLC0415
    from typing import Any, cast  # noqa: PLC0415

    from betsson_validator.providers.pragmatic.recorder import _foreign_reason  # noqa: PLC0415

    casino = SimpleNamespace(parent_frame=None, url="https://www.betsson.es/casino")
    game = SimpleNamespace(parent_frame=casino, url="https://a.proveedor.net/gs2c/playGame.do")
    other = SimpleNamespace(parent_frame=casino, url="https://anuncios.example/frame")

    def response(frame: object, url: str) -> Any:
        return cast(Any, SimpleNamespace(request=SimpleNamespace(frame=frame), url=url))

    blank = SimpleNamespace(parent_frame=game, url="about:blank")
    server = "https://b.proveedor.net/gs2c/ge/v4/gameService"
    assert _foreign_reason(response(game, server)) is None
    assert _foreign_reason(response(blank, server)) is None  # hereda el sitio del juego
    assert _foreign_reason(response(casino, server)) is not None
    assert _foreign_reason(response(other, server)) is not None


def test_http_error_is_not_proof_of_a_rejected_wager() -> None:
    """Auditoría R03-04: un 503 con HTML no es una llamada legible del juego."""
    from types import SimpleNamespace  # noqa: PLC0415
    from typing import Any, cast  # noqa: PLC0415

    from betsson_validator.providers.pragmatic.recorder import GameServiceRecorder  # noqa: PLC0415

    class Context:
        def on(self, _event: str, _handler: object) -> None:
            return None

    recorder = GameServiceRecorder(cast(Any, Context()))
    frame = SimpleNamespace(
        parent_frame=SimpleNamespace(parent_frame=None, url="https://c.es"),
        url="https://a.proveedor.net/gs2c/playGame.do",
    )

    def response(ok: bool, body: str) -> Any:
        request = SimpleNamespace(frame=frame, post_data="action=doSpin&c=0.01&l=20")
        return cast(
            Any,
            SimpleNamespace(
                url="https://a.proveedor.net/gs2c/ge/v4/gameService",
                ok=ok,
                request=request,
                text=lambda: body,
            ),
        )

    recorder._on_response(response(False, "<html>503</html>"))
    recorder._on_response(response(True, ""))
    recorder._on_response(response(True, "<html>no es el esquema</html>"))
    summary = recorder.summarize(0, "")
    assert summary.observed_calls == 0
    assert summary.unreadable == 3
    assert not summary.reliable
