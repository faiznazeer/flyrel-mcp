import pytest

from flyrel.config import Settings


@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_configuration_preserves_broker_mapping(tmp_path, monkeypatch, source):
    values = {
        "STATE_DIR": str(tmp_path / "custom-state"),
        "KITE_API_KEY": "synthetic-kite-key",
        "KITE_ACCESS_TOKEN": "synthetic-kite-token",
        "ALPACA_API_KEY": "synthetic-alpaca-key",
        "ALPACA_SECRET_KEY": "synthetic-alpaca-secret",
        "ALPACA_PAPER": "false",
        "ALPACA_FEED": "sip",
    }
    env_file = tmp_path / ".env"
    if source == "environment":
        for name, value in values.items():
            monkeypatch.setenv("FLYREL_" + name, value)
    else:
        env_file.write_text("".join(f"FLYREL_{name}={value}\n" for name, value in values.items()))
    settings = Settings(_env_file=env_file)

    assert settings.state_dir == tmp_path / "custom-state"
    assert settings.kite_api_key.get_secret_value() == values["KITE_API_KEY"]
    assert settings.kite_access_token.get_secret_value() == values["KITE_ACCESS_TOKEN"]
    assert settings.alpaca_api_key.get_secret_value() == values["ALPACA_API_KEY"]
    assert settings.alpaca_secret_key.get_secret_value() == values["ALPACA_SECRET_KEY"]
    assert settings.alpaca_paper is False
    assert settings.alpaca_feed == "sip"


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("FLYREL_ALPACA_PAPER=true\n")
    monkeypatch.setenv("FLYREL_ALPACA_PAPER", "false")
    assert Settings(_env_file=env_file).alpaca_paper is False


def test_settings_accept_python_field_names(tmp_path):
    settings = Settings(_env_file=None, state_dir=tmp_path, alpaca_paper=False)
    assert settings.state_dir == tmp_path
    assert settings.alpaca_paper is False
