from __future__ import annotations

import logging
from typing import Annotated

import typer

from scholar_alerts.config import ConfigError, Settings, load_settings
from scholar_alerts.excel_store import ExcelStore, ExcelStoreError
from scholar_alerts.imap_client import ImapMailClient, ImapOperationError
from scholar_alerts.logging_config import configure_logging
from scholar_alerts.processor import MessageProcessor, read_last_run
from scholar_alerts.source_detector import detect_source

app = typer.Typer(
    help="无痕读取 Google Scholar 与 IEEE Author Alert，并维护本地 Excel。",
    no_args_is_help=True,
)
LOGGER = logging.getLogger(__name__)


def _settings(*, require_folder: bool = True) -> Settings:
    try:
        settings = load_settings()
        settings.validate_credentials(require_folder=require_folder)
        configure_logging(settings.log_level)
        return settings
    except ConfigError as exc:
        typer.echo(f"配置错误: {exc}", err=True)
        raise typer.Exit(code=2) from exc


@app.command("folders")
def folders() -> None:
    """列出所有 IMAP 文件夹；不读取邮件。"""
    settings = _settings(require_folder=False)
    try:
        with ImapMailClient(settings) as mail:
            for folder_name in mail.list_folders():
                typer.echo(folder_name)
    except ImapOperationError as exc:
        typer.echo(f"连接失败: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("test-connection")
def test_connection() -> None:
    """验证登录、目标文件夹存在并可只读选择。"""
    settings = _settings()
    try:
        with ImapMailClient(settings) as mail:
            mail.select_folder(readonly=True)
        typer.echo(f"连接成功；目标文件夹 {settings.target_folder!r} 可只读访问。")
    except ImapOperationError as exc:
        typer.echo(f"连接测试失败: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("scan")
def scan() -> None:
    """仅读取未读邮件头并显示初步来源；不读取正文、不修改 flags。"""
    settings = _settings()
    try:
        with ImapMailClient(settings) as mail:
            mail.select_folder(readonly=True)
            summaries = mail.unread_summaries(limit=settings.max_emails_per_run)
        if not summaries:
            typer.echo("目标文件夹没有未读邮件。")
            return
        for item in summaries:
            detection = detect_source(item.sender, item.subject, None, settings.source_rules)
            source = detection.source or detection.reason or "unknown"
            typer.echo(
                f"UID={item.uid} | {item.received_at:%Y-%m-%d %H:%M:%S} | "
                f"From={item.sender} | Source={source} | Subject={item.subject}"
            )
    except ImapOperationError as exc:
        typer.echo(f"扫描失败: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("process")
def process(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="仅解析和预览去重，不写 Excel、不修改邮件 flags。"
        ),
    ] = False,
    limit: Annotated[
        int | None, typer.Option("--limit", min=1, help="本次最多处理的未读邮件数。")
    ] = None,
) -> None:
    """按日期从旧到新事务式处理未读提醒邮件。"""
    settings = _settings()
    if limit is not None and limit > settings.max_emails_per_run:
        typer.echo(
            f"--limit 超过 MAX_EMAILS_PER_RUN，已限制为 {settings.max_emails_per_run}。",
            err=True,
        )
    try:
        with ImapMailClient(settings) as mail:
            mail.select_folder(readonly=dry_run)
            results = MessageProcessor(settings).process_mailbox(mail, dry_run=dry_run, limit=limit)
    except ImapOperationError as exc:
        typer.echo(f"处理前连接失败: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if not results:
        typer.echo("目标文件夹没有未读邮件。")
        return
    for item in results:
        if dry_run and not item.error:
            status = "预览完成"
        else:
            status = "成功" if item.marked_seen else "失败"
        typer.echo(
            f"UID={item.uid} | {status} | Source={item.source or '-'} | "
            f"识别={item.detected} 新增={item.added} 重复={item.duplicates} "
            f"解析失败={item.failed} 错误={item.error or '-'}"
        )
    errors = sum(item.error is not None for item in results)
    typer.echo(
        f"汇总：邮件={len(results)} 新增={sum(item.added for item in results)} "
        f"重复={sum(item.duplicates for item in results)} 错误={errors}"
    )
    if errors:
        raise typer.Exit(code=1)


@app.command("status")
def status() -> None:
    """显示待处理数量、Excel 总数和最近一次正式运行结果。"""
    settings = _settings()
    try:
        with ImapMailClient(settings) as mail:
            mail.select_folder(readonly=True)
            summaries = mail.unread_summaries()
        google_senders = set(settings.source_rules["google_scholar"].from_exact)
        ieee_senders = set(settings.source_rules["ieee_author_alert"].from_exact)
        google_count = sum(item.sender in google_senders for item in summaries)
        ieee_count = sum(item.sender in ieee_senders for item in summaries)
        total_papers = ExcelStore(settings.output_file).count()
        last_run = read_last_run(settings.output_file.parent / ".last_run.json")
    except (ImapOperationError, ExcelStoreError) as exc:
        typer.echo(f"读取状态失败: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    errors = last_run.get("errors", [])
    latest_error = errors[-1] if isinstance(errors, list) and errors else "无"
    typer.echo(f"目标文件夹未读数量: {len(summaries)}")
    typer.echo(f"Google Scholar 待处理数量: {google_count}")
    typer.echo(f"IEEE 待处理数量: {ieee_count}")
    typer.echo(f"Excel 中论文总数: {total_papers}")
    typer.echo(f"最近运行新增数量: {last_run.get('added', 0)}")
    typer.echo(f"最近运行重复数量: {last_run.get('duplicates', 0)}")
    typer.echo(f"最近错误: {latest_error}")


if __name__ == "__main__":
    app()
