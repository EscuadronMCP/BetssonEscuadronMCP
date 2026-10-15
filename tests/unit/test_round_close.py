"""La lectura final espera a que el servidor y los eventos cierren la ronda.

15/10: una tirada con premio en cascada se leyó antes del cobro (servidor na=c, sin
gameRoundEnded) y dio un FAIL falso. Ahora se espera al cierre antes de leer.
"""

from decimal import Decimal
from typing import Any, cast

from betsson_validator.runner import _wait_round_closed, _Witnesses
from betsson_validator.scenarios.evidence import GameEventsSummary, NetworkSummary


class _Page:
    def __init__(self) -> None:
        self.waits = 0

    def evaluate(self, _script: str) -> list[object]:
        return []

    def wait_for_timeout(self, _ms: float) -> None:
        self.waits += 1


class _Casino:
    def __init__(self) -> None:
        self.page = _Page()


class _Network:
    """El servidor liquida la ronda tras unas cuantas consultas (cobro del premio)."""

    def __init__(self, settle_after: int) -> None:
        self.calls, self.settle_after = 0, settle_after

    def summarize(self, _mark: int, evidence: str) -> NetworkSummary:
        self.calls += 1
        return NetworkSummary(
            spin_requested=True,
            settled=self.calls > self.settle_after,
            wager_accepted=Decimal("0.20"),
            observed_calls=3,
            evidence=evidence,
        )


def test_waits_until_the_server_settles_the_round() -> None:
    casino = _Casino()
    witnesses = _Witnesses(network=cast(Any, _Network(settle_after=3)), events=None)
    assert _wait_round_closed(cast(Any, casino), witnesses, 0, 0) is True
    assert casino.page.waits == 3


def test_a_rejected_spin_does_not_keep_the_reading_waiting() -> None:
    class Rejected(_Network):
        def summarize(self, _mark: int, evidence: str) -> NetworkSummary:
            return NetworkSummary(spin_requested=True, observed_calls=2, evidence=evidence)

    casino = _Casino()
    witnesses = _Witnesses(network=cast(Any, Rejected(0)), events=None)
    assert _wait_round_closed(cast(Any, casino), witnesses, 0, 0) is True
    assert casino.page.waits == 0


def test_an_open_round_in_events_is_waited_for() -> None:
    class Events:
        def __init__(self) -> None:
            self.calls = 0

        def loading_finished(self, _events: object) -> bool:
            return True

        def summarize(self, _events: object, evidence: str) -> GameEventsSummary:
            self.calls += 1
            return GameEventsSummary(
                received=True, round_started=True, round_ended=self.calls > 2, evidence=evidence
            )

    casino = _Casino()
    witnesses = _Witnesses(network=None, events=cast(Any, Events()))
    assert _wait_round_closed(cast(Any, casino), witnesses, 0, 0) is True
    assert casino.page.waits == 2


def test_without_witnesses_there_is_nothing_to_wait_for() -> None:
    assert _wait_round_closed(cast(Any, _Casino()), _Witnesses(None, None), 0, 0) is None
