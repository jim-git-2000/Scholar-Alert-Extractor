# Scholar Alert Extractor

一个本地运行的 Python 3.12 工具。它通过 IMAP 无痕读取网易 163 邮箱指定文件夹中的未读邮件，处理 Google Scholar 搜索快讯、IEEE Xplore Author Alert 和 IEEE `New Matches Available for Your Search` 搜索提醒，去重后维护 `output/papers.xlsx`。项目不会发送、移动或删除邮件，不访问正文链接，也不调用外部 API 或大语言模型。

## 支持的发件人

仅精确匹配以下地址：

- `scholaralerts-noreply@google.com`
- `no-reply@ieee.org`
- `no-reply@xplore.ieee.org`

IEEE 发件地址匹配后，还必须由 Author Alert、`New Matches Available for Your Search` 主题或 IEEE Xplore Document 链接确认内容。普通 IEEE 系统邮件不会被处理。

## 安装

推荐使用 `uv`：

```bash
uv sync --extra dev
```

也可以使用 Python 3.12 虚拟环境：

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

复制配置模板：

```bash
cp .env.example .env
```

编辑 `.env`。`IMAP_PASSWORD` 必须填写网易邮箱客户端授权码，而不是网页登录密码。`.env` 已被 Git 忽略。

## 首次运行

先列出文件夹并将准确名称填入 `TARGET_FOLDER`：

```bash
python -m scholar_alerts folders
```

然后依次执行：

```bash
python -m scholar_alerts test-connection
python -m scholar_alerts scan
python -m scholar_alerts process --dry-run --limit 3
python -m scholar_alerts process --limit 10
python -m scholar_alerts status
```

也可以使用安装后的 `scholar-alerts` 命令替代 `python -m scholar_alerts`。

## 安全与事务语义

- `scan` 只读取邮件头，不读取完整正文，不修改 flags。
- `process --dry-run` 使用 `BODY.PEEK[]` 解析邮件，但不写 Excel、不修改 flags。
- 正式处理按接收日期从旧到新执行，每封邮件独立提交。
- 获取完整邮件前后都会检查 flags；若无痕读取意外产生 `\Seen`，当前邮件立即失败。
- 只有来源、MIME、专用解析、完整性检查、去重、Excel 临时文件验证、原子替换和最终验证全部成功，才添加并验证 `\Seen`。
- Excel 写入失败时原邮件保持未读。Excel 已提交但标记已读失败时保留结果，下次运行依靠去重避免新增重复行。

## Excel

默认输出为 `output/papers.xlsx`，工作表名为 `Papers`。固定列为：

```text
title, authors, year, publication, doi, ieee_document_id,
paper_url, pdf_url, snippet, sources, alert_names,
first_seen_at, last_seen_at, seen_count, dedup_key
```

去重依次使用 DOI、IEEE Document ID、规范化论文 URL、标题与年份、标题与第一作者。同标题但年份不同的记录不会仅凭作者相同而合并。重复论文会补全空字段，但不会覆盖已有非空字段；来源、快讯名称、最后发现时间和出现次数会更新。

## 配置

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `IMAP_HOST` | `imap.163.com` | IMAP 主机 |
| `IMAP_PORT` | `993` | SSL 端口 |
| `IMAP_USERNAME` | 空 | 邮箱账号 |
| `IMAP_PASSWORD` | 空 | 客户端授权码 |
| `TARGET_FOLDER` | 空 | 只处理这个文件夹 |
| `OUTPUT_FILE` | `output/papers.xlsx` | 唯一 Excel 输出 |
| `IMAP_TIMEOUT_SECONDS` | `30` | 网络超时 |
| `MAX_EMAILS_PER_RUN` | `100` | 单次上限 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

来源规则保存在 `config/sources.yaml`。应继续使用精确发件人列表，不要改成 `endswith("@ieee.org")` 一类宽泛匹配。

## 测试与检查

```bash
pytest
ruff check .
```

测试覆盖来源精确匹配、MIME 解码与清理、HTML/纯文本解析、多论文模板、跨来源去重、同标题不同年份、Excel 原子更新、IMAP `BODY.PEEK[]`、失败保持未读、成功后标记已读和 dry-run 无副作用。

真实邮件模板验证需要把脱敏 `.eml` 样本加入 `tests/fixtures/` 后扩展相应解析测试。不要提交真实邮箱地址、Message-ID、正文中的个人信息或授权码。

## 已知限制

第一版不读取附件，不访问外部网页补全元数据，不执行模糊标题匹配，也不自动关联预印本与正式版本。邮件模板发生显著变化且只解析出部分条目时，整封邮件会保持未读并报告 `partial_parse` 或 `zero_valid_papers`，需更新解析器和夹具后再处理。
