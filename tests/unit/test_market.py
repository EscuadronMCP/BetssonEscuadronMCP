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
    monkeypatch.delenv(account.username_env, raising=False)
    monkeypatch.delenv(account.password_env, raising=False)
    with pytest.raises(MissingCredentialsError) as error:
        account.resolve()
    assert error.value.variables == [account.username_env, account.password_env]


def test_credentials_are_never_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    account = load_market("es").accounts.funded
    monkeypatch.setenv(account.username_env, "usuario-secreto")
    monkeypatch.setenv(account.password_env, "clave-secreta")
    credentials = account.resolve()
    assert "secret" not in repr(credentials)
    assert "secreta" not in str(credentials)
    assert credentials.password.get_secret_value() == "clave-secreta"
