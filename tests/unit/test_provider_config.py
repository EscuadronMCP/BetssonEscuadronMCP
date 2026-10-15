import pytest

from betsson_validator.config.provider import load_provider


def test_pragmaticplay_profile_loads() -> None:
    provider = load_provider("pragmaticplay")
    assert provider.filter_label == "Pragmatic Play"
    assert provider.screen.labels.credit == "CRÉDITO"
    assert provider.screen.controls.spin == (0.778, 0.905)
    assert provider.screen.insufficient_funds_regex.search("Fondos insuficientes para realizar")


def test_unknown_provider_lists_available() -> None:
    with pytest.raises(ValueError, match="pragmaticplay"):
        load_provider("netent")
