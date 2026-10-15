"""Fallo intencionado para demostrar cómo detecta y documenta el validador un fallo real.

Se aplica a lo observado justo antes de evaluar, solo cuando se pide expresamente
(`run --inject-fault <escenario>`), y queda anunciado en el informe. Simula el fallo de
integración que más importa a Betsson: que el saldo no cuadre tras la tirada.
"""

from dataclasses import dataclass, replace
from decimal import Decimal

from betsson_validator.domain.money import Money
from betsson_validator.scenarios.evidence import RunEvidence

_DRIFT = Decimal("0.01")


@dataclass(frozen=True)
class InjectedFault:
    description: str

    def apply(self, evidence: RunEvidence) -> RunEvidence:
        after = evidence.betsson_after
        if after is None:
            return evidence
        drift = Money(amount=_DRIFT, currency=after.currency)
        return replace(evidence, betsson_after=after + drift)


DEMO_FAILURE = InjectedFault(
    "Prueba que falla a propósito: se vuelve a evaluar este escenario con lo observado de verdad, "
    f"pero sumando {_DRIFT} € al saldo final de Betsson, como si Betsson abonara mal la tirada. "
    "El validador debe detectarlo y marcar FAIL. No apuesta más ni cuenta para el resultado."
)

BETSSON_BALANCE_DRIFT = InjectedFault(
    "FALLO INTENCIONADO (demostración): al saldo final de Betsson leído se le sumó "
    f"{_DRIFT} € antes de evaluar, como si Betsson abonara mal la tirada. Las capturas "
    "muestran el saldo real; el validador debe marcar FAIL por discrepancia."
)
