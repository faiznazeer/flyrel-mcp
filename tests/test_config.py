import os

import pytest

from flyrel.config import Settings


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch):
    for name in os.environ:
        if name.startswith(("FLYREL_", "BROKERBRIDGE_")):
            monkeypatch.delenv(name)


@pytest.mark.parametrize("prefix", ["FLYREL_", "BROKERBRIDGE_"])
@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_configuration_names_preserve_broker_mapping(tmp_path, monkeypatch, prefix, source):
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
            monkeypatch.setenv(prefix + name, value)
    else:
        env_file.write_text("".join(f"{prefix}{name}={value}\n" for name, value in values.items()))
    settings = Settings(_env_file=env_file)

    assert settings.state_dir == tmp_path / "custom-state"
    assert settings.kite_api_key.get_secret_value() == values["KITE_API_KEY"]
    assert settings.kite_access_token.get_secret_value() == values["KITE_ACCESS_TOKEN"]
    assert settings.alpaca_api_key.get_secret_value() == values["ALPACA_API_KEY"]
    assert settings.alpaca_secret_key.get_secret_value() == values["ALPACA_SECRET_KEY"]
    assert settings.alpaca_paper is False
    assert settings.alpaca_feed == "sip"


@pytest.mark.parametrize("source", ["environment", "dotenv"])
def test_flyrel_names_take_precedence_within_source(tmp_path, monkeypatch, source):
    values = {"BROKERBRIDGE_ALPACA_PAPER": "false", "FLYREL_ALPACA_PAPER": "true"}
    env_file = tmp_path / ".env"
    if source == "environment":
        for name, value in values.items():
            monkeypatch.setenv(name, value)
    else:
        env_file.write_text("".join(f"{name}={value}\n" for name, value in values.items()))
    assert Settings(_env_file=env_file).alpaca_paper is True


@pytest.mark.parametrize("env_prefix", ["FLYREL_", "BROKERBRIDGE_"])
def test_environment_overrides_dotenv_across_names(tmp_path, monkeypatch, env_prefix):
    dotenv_prefix = "BROKERBRIDGE_" if env_prefix == "FLYREL_" else "FLYREL_"
    env_file = tmp_path / ".env"
    env_file.write_text(f"{dotenv_prefix}ALPACA_PAPER=true\n")
    monkeypatch.setenv(f"{env_prefix}ALPACA_PAPER", "false")
    assert Settings(_env_file=env_file).alpaca_paper is False


def test_settings_accept_python_field_names(tmp_path):
    settings = Settings(_env_file=None, state_dir=tmp_path, alpaca_paper=False)
    assert settings.state_dir == tmp_path
    assert settings.alpaca_paper is False
