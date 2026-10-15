import pytest

from betsson_validator.config.market import MissingCredentialsError, load_market


def test_es_market_matches_challenge() -> None:
    market = load_market("es")
    assert str(market.base_url) == "https://www.betsson.es/"
    assert market.language == "es"
    assert market.currency == "EUR"


def test_unknown_market_lists_available() -> None:
    with pytest.raises(ValueError, match="es"):
        load_market("xx")


def test_missing_credentials_name_variables_not_values(monkeypatch: pytest.MonkeyPatch) -> None:
    account = load_market("es").accounts.funded
    monkeypatch.delenv(account.email_env, raising=False)
    monkeypatch.delenv(account.password_env, raising=False)
    with pytest.raises(MissingCredentialsError) as error:
        account.resolve()
    assert error.value.variables == [account.email_env, account.password_env]


def test_credentials_are_never_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    account = load_market("es").accounts.funded
    monkeypatch.setenv(account.email_env, "jugador@example.com")
    monkeypatch.setenv(account.password_env, "clave-secreta")
    credentials = account.resolve()
    assert "jugador@example.com" not in repr(credentials)
    assert "secreta" not in str(credentials)
    assert credentials.password.get_secret_value() == "clave-secreta"


def test_both_scenarios_cannot_share_an_account(monkeypatch: pytest.MonkeyPatch) -> None:
    from betsson_validator.config.market import SameAccountError  # noqa: PLC0415

    market = load_market("es")
    monkeypatch.setenv(market.accounts.funded.email_env, "Cuenta@Example.com")
    monkeypatch.setenv(market.accounts.no_balance.email_env, "cuenta@example.com ")
    with pytest.raises(SameAccountError):
        market.accounts.ensure_distinct()
    monkeypatch.setenv(market.accounts.no_balance.email_env, "otra@example.com")
    market.accounts.ensure_distinct()
    assert "otra@example.com" in market.accounts.secrets()
