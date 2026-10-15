import pytest

from betsson_validator.config.provider import load_provider


def test_pragmaticplay_config_has_no_game_specific_screen_data() -> None:
    provider = load_provider("pragmaticplay")
    assert provider.filter_label == "Pragmatic Play"
    assert provider.network_witness == "pragmatic"
    assert not hasattr(provider, "screen")


def test_unknown_provider_lists_available() -> None:
    with pytest.raises(ValueError, match="pragmaticplay"):
        load_provider("netent")
