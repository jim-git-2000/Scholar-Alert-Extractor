import logging

from scholar_alerts.logging_config import (
    close_logging,
    configure_logging,
    record_cli_output,
)


def test_internal_and_cli_output_append_to_one_fixed_log(tmp_path):
    log_file = tmp_path / "output" / "scholar_alerts.log"
    try:
        configure_logging(
            "WARNING",
            log_file=log_file,
            command=["python", "-m", "scholar_alerts", "scan"],
        )
        logging.getLogger("scholar_alerts.test").warning("internal-warning uid=42")
        record_cli_output("UID=42 | 预览完成")
        close_logging()

        configure_logging(
            "INFO",
            log_file=log_file,
            command=["python", "-m", "scholar_alerts", "status"],
        )
        record_cli_output("Excel 中论文总数: 10")
        close_logging()

        content = log_file.read_text(encoding="utf-8")
        assert "RUN_START command=python -m scholar_alerts scan" in content
        assert "internal-warning uid=42" in content
        assert "UID=42 | 预览完成" in content
        assert "RUN_START command=python -m scholar_alerts status" in content
        assert "Excel 中论文总数: 10" in content
    finally:
        close_logging()
