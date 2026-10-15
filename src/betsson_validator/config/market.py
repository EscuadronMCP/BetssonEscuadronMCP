"""Configuración por mercado. Añadir un mercado es añadir un YAML en config/markets/."""

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr

DEFAULT_MARKETS_DIR = Path(__file__).resolve().parents[3] / "config" / "markets"


class Credentials(BaseModel):
    model_config = ConfigDict(frozen=True)

    email: SecretStr
    password: SecretStr


class AccountEnv(BaseModel):
    """Nombres de las variables de entorno que guardan una cuenta; nunca los valores."""

    model_config = ConfigDict(frozen=True)

    email_env: str
    password_env: str

    def resolve(self) -> Credentials:
        missing = [name for name in (self.email_env, self.password_env) if not os.getenv(name)]
        if missing:
            raise MissingCredentialsError(missing)
        return Credentials(
            email=SecretStr(os.environ[self.email_env]),
            password=SecretStr(os.environ[self.password_env]),
        )


class MarketAccounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    funded: AccountEnv
    no_balance: AccountEnv

    def secrets(self) -> tuple[str, ...]:
        """Valores de las credenciales disponibles, para buscarlos en las evidencias."""
        names = (
            self.funded.email_env,
            self.funded.password_env,
            self.no_balance.email_env,
            self.no_balance.password_env,
        )
        return tuple(value for name in names if (value := os.getenv(name)))

    def ensure_distinct(self) -> None:
        """Los dos escenarios necesitan cuentas distintas: con la misma, uno gastaría el saldo
        del otro y el escenario 2 giraría con dinero real."""
        funded, empty = os.getenv(self.funded.email_env), os.getenv(self.no_balance.email_env)
        if funded and empty and funded.strip().lower() == empty.strip().lower():
            raise SameAccountError(
                f"{self.funded.email_env} y {self.no_balance.email_env} son la misma cuenta."
            )


class MarketUi(BaseModel):
    """Textos visibles de la web del mercado: cambian con el idioma, no con el código."""

    model_config = ConfigDict(frozen=True)

    login_button: str
    # Botón de la cabecera con el saldo del jugador (expresión regular, formato del mercado).
    balance_pattern: str
    passkey_dismiss: str
    filters_button: str
    results_button: str
    clear_filters_button: str
    session_warning_text: str
    session_limits_text: str
    session_duration: str
    session_loss_limit: str
    session_loss_input_placeholder: str
    session_loss_limit_fallback: str
    insufficient_funds_pattern: str
    dismiss_labels: tuple[str, ...]
    win_label_candidates: tuple[str, ...]


class MarketConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    base_url: HttpUrl
    language: str = Field(min_length=2, max_length=2)
    currency: str = Field(min_length=3, max_length=3)
    # Lo que ve un jugador local: idioma del navegador y zona horaria.
    locale: str = "es-ES"
    timezone: str = "Europe/Madrid"
    accounts: MarketAccounts
    ui: MarketUi


class SameAccountError(RuntimeError):
    pass


class MissingCredentialsError(RuntimeError):
    def __init__(self, variables: list[str]) -> None:
        super().__init__(f"Faltan variables de entorno de credenciales: {', '.join(variables)}")
        self.variables = variables


def load_market(market_id: str, markets_dir: Path = DEFAULT_MARKETS_DIR) -> MarketConfig:
    path = markets_dir / f"{market_id}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in markets_dir.glob("*.yaml"))
        raise ValueError(f"Mercado desconocido '{market_id}'. Disponibles: {available}")
    with path.open(encoding="utf-8") as file:
        return MarketConfig.model_validate(yaml.safe_load(file))
