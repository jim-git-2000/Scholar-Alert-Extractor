from pathlib import Path

import pytest

from scholar_alerts.config import ConfigError, load_settings, load_source_rules


def test_load_source_rules_has_only_expected_senders():
    rules = load_source_rules(Path("config/sources.yaml"))
    all_senders = {sender for rule in rules.values() for sender in rule.from_exact}
    assert all_senders == {
        "scholaralerts-noreply@google.com",
        "no-reply@ieee.org",
        "no-reply@xplore.ieee.org",
    }


def test_settings_validate_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("IMAP_USERNAME", "user@163.com")
    monkeypatch.setenv("IMAP_PASSWORD", "client-token")
    monkeypatch.setenv("TARGET_FOLDER", "论文提醒")
    monkeypatch.setenv("OUTPUT_FILE", str(tmp_path / "papers.xlsx"))
    settings = load_settings(env_file=tmp_path / "missing.env")
    settings.validate_credentials()
    assert settings.output_file == tmp_path / "papers.xlsx"


def test_missing_credentials_are_reported(monkeypatch, tmp_path):
    for name in ("IMAP_USERNAME", "IMAP_PASSWORD", "TARGET_FOLDER"):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings(env_file=tmp_path / "missing.env")
    with pytest.raises(ConfigError, match="IMAP_USERNAME.*IMAP_PASSWORD.*TARGET_FOLDER"):
        settings.validate_credentials()
