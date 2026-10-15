from datetime import datetime

from pydantic import BaseModel, ConfigDict

from betsson_validator.domain.checks import SCENARIO_CHECKS, Check, Scenario
from betsson_validator.domain.verdict import CheckResult, Status


class ScenarioRun(BaseModel):
    """Resultado de ejecutar un escenario en un mercado con un juego concreto."""

    model_config = ConfigDict(frozen=True)

    scenario: Scenario
    market: str
    provider: str
    game: str
    started_at: datetime
    finished_at: datetime
    results: tuple[CheckResult, ...]
    error: str | None = None
    # Evidencias retiradas por contener secretos que no se pudieron limpiar.
    quarantined: tuple[str, ...] = ()
    # Hechos relevantes de la ejecución (p. ej. el perfil se reaprendió con IA).
    notes: tuple[str, ...] = ()
    # Fallo introducido a propósito para una demostración (nunca en una validación real).
    injected_fault: str | None = None

    @property
    def status(self) -> Status:
        """PASS solo si no hubo error, se evaluaron todas las comprobaciones del escenario y
        ninguna falló (un resultado repetido en PASS no puede ocultar uno en FAIL)."""
        if self.error is not None or self.missing_checks():
            return Status.FAIL
        if any(result.status is not Status.PASS for result in self.results):
            return Status.FAIL
        return Status.PASS

    def missing_checks(self) -> tuple[Check, ...]:
        evaluated = {result.check for result in self.results}
        return tuple(c for c in SCENARIO_CHECKS[self.scenario] if c.value not in evaluated)
