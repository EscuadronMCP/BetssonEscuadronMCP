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

    @property
    def status(self) -> Status:
        """PASS solo si no hubo error y todas las comprobaciones del escenario pasaron."""
        if self.error is not None:
            return Status.FAIL
        by_check = {result.check: result for result in self.results}
        required = SCENARIO_CHECKS[self.scenario]
        if any(check.value not in by_check for check in required):
            return Status.FAIL
        if all(by_check[check.value].status is Status.PASS for check in required):
            return Status.PASS
        return Status.FAIL

    def missing_checks(self) -> tuple[Check, ...]:
        evaluated = {result.check for result in self.results}
        return tuple(c for c in SCENARIO_CHECKS[self.scenario] if c.value not in evaluated)
