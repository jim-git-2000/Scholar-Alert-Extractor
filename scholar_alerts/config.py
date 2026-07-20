from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ConfigError(ValueError):
    """Configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class SourceRule:
    name: str
    enabled: bool
    from_exact: tuple[str, ...]
    subject_patterns: tuple[str, ...] = ()
    required_link_patterns: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Settings:
    imap_host: str
    imap_port: int
    imap_username: str
    imap_password: str
    target_folder: str
    output_file: Path
    imap_timeout_seconds: int
    max_emails_per_run: int
    log_level: str
    source_rules: dict[str, SourceRule]

    def validate_credentials(self, *, require_folder: bool = True) -> None:
        missing = []
        for name, value in (
            ("IMAP_HOST", self.imap_host),
            ("IMAP_USERNAME", self.imap_username),
            ("IMAP_PASSWORD", self.imap_password),
        ):
            if not value:
                missing.append(name)
        if require_folder and not self.target_folder:
            missing.append("TARGET_FOLDER")
        if missing:
            raise ConfigError(f"缺少必要配置: {', '.join(missing)}")


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是整数") from exc
    if value <= 0:
        raise ConfigError(f"{name} 必须大于 0")
    return value


def load_source_rules(path: Path | None = None) -> dict[str, SourceRule]:
    config_path = path or PROJECT_ROOT / "config" / "sources.yaml"
    try:
        raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"无法读取来源配置 {config_path}: {exc}") from exc
    sources = raw.get("sources")
    if not isinstance(sources, dict):
        raise ConfigError("sources.yaml 必须包含 sources 映射")
    rules: dict[str, SourceRule] = {}
    for name, value in sources.items():
        if not isinstance(value, dict):
            raise ConfigError(f"来源 {name} 的配置必须是映射")
        senders = tuple(str(item).strip().lower() for item in value.get("from_exact", []))
        if not senders:
            raise ConfigError(f"来源 {name} 缺少 from_exact")
        rules[name] = SourceRule(
            name=name,
            enabled=bool(value.get("enabled", True)),
            from_exact=senders,
            subject_patterns=tuple(str(item) for item in value.get("subject_patterns", [])),
            required_link_patterns=tuple(
                str(item) for item in value.get("required_link_patterns", [])
            ),
        )
    return rules


def load_settings(
    env_file: Path | None = None, source_config: Path | None = None
) -> Settings:
    load_dotenv(env_file or PROJECT_ROOT / ".env", override=False)
    output_raw = os.getenv("OUTPUT_FILE", "output/papers.xlsx")
    output_path = Path(output_raw).expanduser()
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    return Settings(
        imap_host=os.getenv("IMAP_HOST", "imap.163.com").strip(),
        imap_port=_positive_int("IMAP_PORT", 993),
        imap_username=os.getenv("IMAP_USERNAME", "").strip(),
        imap_password=os.getenv("IMAP_PASSWORD", ""),
        target_folder=os.getenv("TARGET_FOLDER", "").strip(),
        output_file=output_path,
        imap_timeout_seconds=_positive_int("IMAP_TIMEOUT_SECONDS", 30),
        max_emails_per_run=_positive_int("MAX_EMAILS_PER_RUN", 100),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        source_rules=load_source_rules(source_config),
    )

