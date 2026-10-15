"""Regla del veredicto por testigos independientes (decisión 001).

La pantalla es obligatoria: sin una lectura visual que confirme el hecho no hay PASS.
Cualquier testigo disponible que lo contradiga convierte el resultado en FAIL por discrepancia.
"""

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class WitnessKind(StrEnum):
    VISUAL = "visual"
    CORROBORATING = "corroborating"


class Outcome(StrEnum):
    CONFIRMS = "confirms"
    CONTRADICTS = "contradicts"
    UNAVAILABLE = "unavailable"


class Status(StrEnum):
    PASS = "PASS"  # noqa: S105 (estado del veredicto, no una contraseña)
    FAIL = "FAIL"


class Testimony(BaseModel):
    """Lo que un testigo concreto dice sobre una comprobación."""

    __test__: ClassVar[bool] = False  # evita que pytest lo confunda con una clase de tests
    model_config = ConfigDict(frozen=True)

    witness: str
    kind: WitnessKind
    outcome: Outcome
    detail: str
    evidence: tuple[str, ...] = ()


class CheckResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    check: str
    status: Status
    reason: str
    testimonies: tuple[Testimony, ...]

    @property
    def unavailable_witnesses(self) -> tuple[str, ...]:
        return tuple(t.witness for t in self.testimonies if t.outcome is Outcome.UNAVAILABLE)


def evaluate(check: str, testimonies: tuple[Testimony, ...]) -> CheckResult:
    visual = [t for t in testimonies if t.kind is WitnessKind.VISUAL]
    corroborating = [t for t in testimonies if t.kind is WitnessKind.CORROBORATING]

    def result(status: Status, reason: str) -> CheckResult:
        return CheckResult(check=check, status=status, reason=reason, testimonies=testimonies)

    visual_contradictions = [t for t in visual if t.outcome is Outcome.CONTRADICTS]
    if visual_contradictions:
        return result(
            Status.FAIL, _describe("Lo que ve el jugador lo contradice:", visual_contradictions)
        )

    if not any(t.outcome is Outcome.CONFIRMS for t in visual):
        return result(Status.FAIL, "La pantalla no confirma el hecho: sin lectura visual válida.")

    contradictions = [t for t in corroborating if t.outcome is Outcome.CONTRADICTS]
    if contradictions:
        return result(
            Status.FAIL, _describe("Discrepancia entre lo que ve el jugador y", contradictions)
        )

    missing = [t.witness for t in corroborating if t.outcome is Outcome.UNAVAILABLE]
    if missing:
        return result(
            Status.PASS,
            f"Confirmado en pantalla; sin contradicciones. Testigos no disponibles: "
            f"{', '.join(missing)}.",
        )
    return result(Status.PASS, "Confirmado en pantalla y por todos los testigos.")


def withdraw_evidence(result: CheckResult, removed: set[str]) -> CheckResult:
    """Un testimonio que confirmaba con una evidencia retirada por seguridad deja de probar nada.

    Solo se degradan confirmaciones: una contradicción nunca se oculta.
    """

    def degrade(t: Testimony) -> Testimony:
        if t.outcome is not Outcome.CONFIRMS or not removed.intersection(t.evidence):
            return t
        return t.model_copy(
            update={
                "outcome": Outcome.UNAVAILABLE,
                "detail": f"{t.detail} (evidencia retirada por seguridad)",
            }
        )

    testimonies = tuple(degrade(t) for t in result.testimonies)
    return result if testimonies == result.testimonies else evaluate(result.check, testimonies)


def _describe(prefix: str, testimonies: list[Testimony]) -> str:
    details = "; ".join(f"{t.witness}: {t.detail}" for t in testimonies)
    return f"{prefix} {details}."
