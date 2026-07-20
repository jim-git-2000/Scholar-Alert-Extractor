# Scholar Alert Extractor 开发计划

## 1. 项目目标

开发一个本地运行的 Python 工具，连接网易 163 邮箱指定 IMAP 文件夹，仅处理以下三类发件地址：

* `scholaralerts-noreply@google.com`
* `no-reply@ieee.org`
* `no-reply@xplore.ieee.org`

工具完成以下任务：

1. 查找指定文件夹中的未读邮件。
2. 无痕读取邮件，不因读取而改变未读状态。
3. 识别 Google Scholar 搜索快讯和 IEEE Xplore Author Alert。
4. 从邮件中提取论文信息。
5. 对同一邮件、不同邮件和不同来源中的论文进行去重。
6. 将去重后的论文维护在一个 Excel 文件中。
7. 邮件处理成功后，将原邮件标记为已读。
8. 不发送邮件、不移动邮件、不删除邮件。
9. 不调用 OpenAI 或其他大语言模型。
10. 不访问邮件中的外部链接，不下载论文。

---

## 2. 最终处理流程

```text
连接 163 IMAP
    ↓
进入指定文件夹
    ↓
搜索 UNSEEN 邮件
    ↓
按 UID 无痕读取
    ↓
解析 From、Subject 和 MIME 正文
    ↓
识别 Google Scholar 或 IEEE Author Alert
    ↓
调用对应专用解析器
    ↓
提取论文条目
    ↓
邮件内部去重
    ↓
与 papers.xlsx 中已有论文去重
    ↓
新增论文或补全重复论文记录
    ↓
原子写入并验证 Excel
    ↓
将当前邮件标记为已读
```

任何关键步骤失败时，原邮件保持未读。

---

## 3. 技术选型

### 运行环境

* Python 3.12

### 核心依赖

* `imapclient`：IMAP 连接、文件夹、UID 和邮件状态操作
* `beautifulsoup4`：HTML 邮件解析
* `openpyxl`：Excel 读取和写入
* `python-dotenv`：环境变量加载
* `typer`：命令行界面
* `PyYAML`：来源配置
* `pytest`：测试
* `ruff`：格式化和静态检查

### Python 标准库

* `email`
* `email.utils`
* `html`
* `unicodedata`
* `urllib.parse`
* `re`
* `hashlib`
* `pathlib`
* `tempfile`
* `os`
* `datetime`
* `logging`

不引入数据库。

---

## 4. 项目结构

```text
scholar-alert-extractor/
├── scholar_alerts/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── logging_config.py
│   ├── imap_client.py
│   ├── mime_parser.py
│   ├── source_detector.py
│   ├── models.py
│   ├── normalizers.py
│   ├── dedup.py
│   ├── excel_store.py
│   ├── processor.py
│   └── parsers/
│       ├── __init__.py
│       ├── base.py
│       ├── google_scholar.py
│       └── ieee_author_alert.py
├── config/
│   └── sources.yaml
├── output/
├── tests/
│   ├── fixtures/
│   │   ├── google_scholar/
│   │   └── ieee/
│   ├── test_source_detector.py
│   ├── test_google_scholar_parser.py
│   ├── test_ieee_parser.py
│   ├── test_normalizers.py
│   ├── test_dedup.py
│   ├── test_excel_store.py
│   ├── test_imap_client.py
│   └── test_processor.py
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## 5. 配置设计

### 5.1 环境变量

`.env.example`：

```env
IMAP_HOST=imap.163.com
IMAP_PORT=993
IMAP_USERNAME=
IMAP_PASSWORD=
TARGET_FOLDER=
OUTPUT_FILE=output/papers.xlsx
IMAP_TIMEOUT_SECONDS=30
MAX_EMAILS_PER_RUN=100
LOG_LEVEL=INFO
```

规则：

* `IMAP_PASSWORD` 使用网易邮箱客户端授权码。
* 不使用网页登录密码。
* `.env` 必须加入 `.gitignore`。
* 日志中不得输出授权码或完整环境变量。

### 5.2 邮件来源配置

`config/sources.yaml`：

```yaml
sources:
  google_scholar:
    enabled: true
    from_exact:
      - scholaralerts-noreply@google.com

  ieee_author_alert:
    enabled: true
    from_exact:
      - no-reply@ieee.org
      - no-reply@xplore.ieee.org
    subject_patterns:
      - "IEEE Xplore Author Alert"
      - "Author Alert"
      - "New Content from"
    required_link_patterns:
      - "ieeexplore.ieee.org/document/"
```

发件人地址通过 `email.utils.parseaddr()` 提取后转为小写，再进行精确匹配。

禁止使用宽泛规则，例如：

```python
sender.endswith("@ieee.org")
```

---

## 6. 数据模型

定义 `Paper`：

```python
@dataclass
class Paper:
    title: str
    authors: list[str]
    year: int | None
    publication: str | None
    doi: str | None
    ieee_document_id: str | None
    paper_url: str | None
    pdf_url: str | None
    snippet: str | None
    source: str
    alert_name: str | None
    received_at: datetime
    message_id: str | None
    email_uid: int
```

定义解析结果：

```python
@dataclass
class ParseResult:
    papers: list[Paper]
    source: str
    parser_name: str
    detected_items: int
    parsed_items: int
    failed_items: int
    warnings: list[str]
```

如果解析器认为邮件中存在多个论文条目，但只成功解析部分条目，则整封邮件不标记已读。

---

## 7. IMAP 模块开发

### 7.1 文件夹功能

实现：

```bash
python -m scholar_alerts folders
```

功能：

* 登录 163 邮箱。
* 调用 IMAP LIST。
* 列出所有文件夹。
* 正确显示中文名称。
* 不读取邮件。
* 不改变邮件状态。

### 7.2 连接测试

实现：

```bash
python -m scholar_alerts test-connection
```

验证：

* IMAP 登录成功。
* `TARGET_FOLDER` 存在。
* 可以只读选择文件夹。
* 不读取正文。
* 不修改任何 flags。

### 7.3 未读邮件扫描

实现：

```bash
python -m scholar_alerts scan
```

输出：

* UID
* 发件人
* 主题
* 接收日期
* 初步识别来源

不读取完整正文，不修改邮件状态。

### 7.4 邮件读取

要求：

* 使用 IMAP UID。
* 搜索 `UNSEEN`。
* 使用 `BODY.PEEK[]` 或等价的无痕读取方式。
* 读取后重新检查 FLAGS。
* 如果读取导致意外出现 `\Seen`，停止当前邮件处理并记录严重错误。
* 按接收日期从旧到新处理。

---

## 8. MIME 解析模块

需要支持：

* `multipart/alternative`
* `multipart/mixed`
* `text/html`
* `text/plain`
* quoted-printable
* base64
* UTF-8
* GBK
* charset 缺失或错误

处理优先级：

1. `text/html`
2. `text/plain`

HTML 清理：

* 删除 `script`
* 删除 `style`
* 删除 `iframe`
* 删除 `form`
* 删除 `noscript`
* 删除不可见元素
* 忽略跟踪像素

不处理附件。

不发起网络请求。

---

## 9. 来源识别模块

### 9.1 Google Scholar

必要条件：

```text
From == scholaralerts-noreply@google.com
```

识别后调用 Google Scholar 专用解析器。

邮件中最终必须提取到至少一篇有效论文，或者明确确认邮件内所有论文均为重复论文，才可标记已读。

### 9.2 IEEE Xplore Author Alert

必要条件：

```text
From == no-reply@ieee.org
或
From == no-reply@xplore.ieee.org
```

并至少满足以下一项：

* 主题符合 Author Alert 模式。
* 正文包含 `ieeexplore.ieee.org/document/`。
* IEEE 解析器识别出结构完整的论文条目。

发件人匹配但内容不匹配时：

* 不写 Excel。
* 不标记已读。
* 日志记录 `sender_matched_but_content_unmatched`。

---

## 10. Google Scholar 解析器

文件：

```text
scholar_alerts/parsers/google_scholar.py
```

提取字段：

* title
* authors
* year
* publication
* paper_url
* pdf_url
* snippet
* alert_name

解析策略：

1. 优先解析 HTML。
2. 查找可能代表论文标题的链接。
3. 基于 DOM 层级和相邻内容识别论文区块。
4. 提取标题下方的作者和出版信息。
5. 提取结果摘要。
6. 提取搜索快讯名称或搜索关键词。
7. 解码 Google 跳转 URL。
8. 识别独立 PDF 链接。
9. 忽略非论文链接。

需要忽略的典型链接文本：

* Cited by
* Related articles
* All versions
* Cached
* Create alert
* Cancel alert
* My profile
* Settings
* Help
* Unsubscribe

解析器不能依赖单一 CSS 类名，应结合：

* 链接文本
* 链接位置
* 相邻文本
* DOM 区块
* 重复结构
* 链接目标

---

## 11. IEEE Xplore Author Alert 解析器

文件：

```text
scholar_alerts/parsers/ieee_author_alert.py
```

提取字段：

* title
* authors
* year
* publication
* doi
* ieee_document_id
* paper_url
* pdf_url
* snippet
* alert_name

解析策略：

1. 查找 `ieeexplore.ieee.org/document/<数字>` 链接。
2. 从 URL 提取 IEEE Document ID。
3. 按 Document ID 聚合同一论文的多个链接。
4. 从相邻 HTML 区块提取论文标题。
5. 提取作者。
6. 提取出版物名称。
7. 提取年份。
8. 提取 DOI。
9. 识别 PDF 链接。
10. 从邮件标题或顶部说明中提取被关注作者姓名。
11. 忽略管理提醒、退订、隐私政策和登录链接。

IEEE URL 统一格式：

```text
https://ieeexplore.ieee.org/document/<document_id>
```

---

## 12. 标准化模块

实现以下函数：

```python
normalize_title()
normalize_doi()
normalize_url()
normalize_ieee_document_id()
normalize_author()
extract_first_author()
```

### 标题标准化

* Unicode NFKC
* HTML 实体解码
* 转小写
* 统一各类连字符
* 删除标点
* 连续空白压缩
* 去除首尾空白

### DOI 标准化

移除：

* `doi:`
* `https://doi.org/`
* `http://doi.org/`
* `http://dx.doi.org/`

然后：

* 转小写
* 去除首尾空格
* 去除末尾句号等无关标点

### URL 标准化

* scheme 和 host 转小写
* 删除 fragment
* 删除 `utm_*`
* 删除常见跟踪参数
* 删除无意义末尾斜杠
* 解码 Google 跳转链接
* IEEE 链接统一为标准 Document URL

---

## 13. 去重策略

去重范围：

* 同一邮件内部
* 不同 Google Scholar 邮件
* 不同 IEEE 邮件
* Google Scholar 与 IEEE 之间
* 不同程序运行之间

判断顺序：

1. 标准化 DOI 相同
2. IEEE Document ID 相同
3. 规范化 paper URL 相同
4. 标准化标题和年份相同
5. 标准化标题和第一作者相同

不使用：

* 模糊标题匹配
* 编辑距离
* 向量相似度
* LLM 判断

避免将以下情况错误合并：

* 同标题但不同年份
* 会议版本与期刊扩展版本
* 预印本与正式版本
* 标题相似但内容不同的论文

`dedup_key` 生成顺序：

```text
doi:<normalized_doi>
ieee:<document_id>
url:<normalized_url>
title-year:<normalized_title>:<year>
title-author:<normalized_title>:<normalized_first_author>
```

---

## 14. Excel 设计

唯一输出文件：

```text
output/papers.xlsx
```

工作表：

```text
Papers
```

固定列：

1. `title`
2. `authors`
3. `year`
4. `publication`
5. `doi`
6. `ieee_document_id`
7. `paper_url`
8. `pdf_url`
9. `snippet`
10. `sources`
11. `alert_names`
12. `first_seen_at`
13. `last_seen_at`
14. `seen_count`
15. `dedup_key`

### 格式要求

* 冻结第一行
* 自动筛选
* 合理列宽
* 长文本自动换行
* URL 设置为超链接
* 日期格式为 `yyyy-mm-dd hh:mm:ss`
* 新论文追加到末尾
* 不改变固定列顺序
* 不覆盖用户手动修改的非空内容

### 新论文

新增一行：

* `first_seen_at` 设置为当前处理时间
* `last_seen_at` 设置为当前处理时间
* `seen_count` 设置为 1

### 重复论文

不新增行，更新：

* `sources`
* `alert_names`
* `last_seen_at`
* `seen_count`

可补充已有空字段：

* DOI
* IEEE Document ID
* publication
* year
* authors
* paper_url
* pdf_url
* snippet

不得用空值覆盖已有非空字段。

---

## 15. Excel 原子写入

每处理一封邮件，采用以下顺序：

1. 读取正式 Excel。
2. 在内存中应用新增和更新。
3. 保存到同目录临时文件。
4. 重新打开临时文件。
5. 验证：

   * 工作表存在
   * 表头正确
   * 行数合理
   * 新增或更新内容存在
6. 使用 `os.replace()` 原子替换正式文件。
7. 重新打开正式文件进行最终验证。
8. 验证通过后标记邮件已读。

如果 Excel 被占用：

* 输出明确错误。
* 不修改原文件。
* 不标记邮件已读。

---

## 16. 邮件标记已读规则

只有以下全部成功后，才添加 `\Seen`：

* 来源识别成功
* MIME 解析成功
* 专用解析器执行完成
* 论文条目完整提取
* 去重完成
* Excel 写入成功
* 临时文件验证成功
* 正式文件替换成功
* 正式文件最终验证成功

以下情况保持未读：

* 未提取到论文
* 邮件结构异常
* 只解析出部分论文
* Excel 保存失败
* Excel 被占用
* 文件验证失败
* 未识别来源
* 未处理异常

一封邮件中的论文全部是重复项时：

* 更新已有记录的 `last_seen_at`、`seen_count`、来源和快讯名称。
* 保存成功后标记该邮件已读。

标记方法：

```text
UID STORE <uid> +FLAGS (\Seen)
```

标记后重新读取 FLAGS 验证。

如果 Excel 已成功写入，但标记已读失败：

* 保留 Excel 结果。
* 输出错误。
* 下次运行依靠去重机制避免重复新增。
* 再次尝试标记已读。

---

## 17. 命令行设计

### 列出文件夹

```bash
python -m scholar_alerts folders
```

### 测试连接

```bash
python -m scholar_alerts test-connection
```

### 扫描未读邮件

```bash
python -m scholar_alerts scan
```

### 模拟处理

```bash
python -m scholar_alerts process --dry-run
```

支持：

```bash
python -m scholar_alerts process --dry-run --limit 3
```

dry-run 输出：

* UID
* 发件人
* 主题
* 来源
* 识别论文数
* 新增论文数
* 重复论文数
* 解析失败条目数

dry-run 不写 Excel，不修改邮件 flags。

### 正式处理

```bash
python -m scholar_alerts process
```

支持：

```bash
python -m scholar_alerts process --limit 10
```

### 状态查看

```bash
python -m scholar_alerts status
```

输出：

* 目标文件夹未读数量
* Google Scholar 待处理数量
* IEEE 待处理数量
* Excel 中论文总数
* 最近运行新增数量
* 最近运行重复数量
* 最近错误

---

## 18. 日志设计

允许记录：

* UID
* 邮件来源
* 脱敏后的发件人
* 主题
* 论文提取数量
* 新增数量
* 重复数量
* 错误类型

禁止记录：

* 邮箱授权码
* 完整邮件正文
* 完整环境变量
* 用户收件地址
* 敏感邮件头

建议错误代码：

```text
folder_not_found
imap_login_failed
message_fetch_failed
message_became_seen_during_fetch
source_unmatched
sender_matched_but_content_unmatched
mime_parse_failed
parser_structure_changed
partial_parse
zero_valid_papers
excel_locked
excel_save_failed
excel_validation_failed
mark_seen_failed
```

---

## 19. 测试计划

### 阶段一：基础模块测试

* 配置加载
* 发件人精确匹配
* From 显示名称解析
* 标题标准化
* DOI 标准化
* URL 标准化
* IEEE Document ID 提取

### 阶段二：Google Scholar 解析测试

* 单篇论文
* 多篇论文
* HTML 邮件
* 纯文本邮件
* PDF 链接
* Google 跳转链接
* 快讯名称
* 忽略 Cited by
* 忽略 Related articles
* 忽略 All versions
* CSS 类名变化

### 阶段三：IEEE 解析测试

* `no-reply@ieee.org`
* `no-reply@xplore.ieee.org`
* 单篇论文
* 多篇论文
* IEEE Document ID
* DOI
* 出版物
* 作者
* Author Alert 作者姓名
* 同一 Document ID 多链接合并
* 忽略管理和退订链接

### 阶段四：去重测试

* DOI 重复
* IEEE Document ID 重复
* URL 重复
* 标题和年份重复
* 标题和第一作者重复
* Google Scholar 与 IEEE 跨来源重复
* 同一邮件内部重复
* 同标题不同年份不合并
* 相似标题不合并

### 阶段五：Excel 测试

* 首次创建
* 固定表头
* 新增论文
* 更新重复论文
* 字段补全
* 不覆盖非空字段
* 超链接
* 原子替换
* 临时文件验证
* 文件被占用

### 阶段六：IMAP 状态测试

* 使用 UID
* BODY.PEEK 不设置已读
* 解析失败保持未读
* Excel 失败保持未读
* 全部重复仍标记已读
* 成功处理后添加 `\Seen`
* 标记失败后重复运行不重复新增
* dry-run 不改变状态

---

## 20. 实施阶段

### 第一阶段：项目骨架和配置

交付：

* 项目目录
* `pyproject.toml`
* `.env.example`
* `sources.yaml`
* 配置加载
* CLI 基础结构
* 日志配置

验收：

```bash
python -m scholar_alerts --help
ruff check .
```

### 第二阶段：IMAP 和 MIME

交付：

* 文件夹列表
* 连接测试
* 未读扫描
* UID 无痕读取
* MIME 解析

验收：

```bash
python -m scholar_alerts folders
python -m scholar_alerts test-connection
python -m scholar_alerts scan
```

读取邮件后未读状态不得变化。

### 第三阶段：Google Scholar 解析器

交付：

* 来源识别
* Google Scholar HTML 解析
* 纯文本回退
* 测试 fixtures
* 单元测试

验收：

* 多篇论文可全部提取。
* 非论文链接不会形成论文记录。
* 结构异常时不会标记邮件已读。

### 第四阶段：IEEE Author Alert 解析器

交付：

* 两个 IEEE 发件地址精确匹配
* Author Alert 内容验证
* IEEE Document ID 提取
* DOI、标题、作者和出版物提取
* 测试 fixtures

验收：

* 两个发件地址均能正确处理。
* 普通 IEEE 系统邮件不会被误处理。

### 第五阶段：去重和 Excel

交付：

* 标准化函数
* 去重索引
* Excel 创建和追加
* 重复记录更新
* 跨来源去重
* 原子写入

验收：

* 相同论文只保留一行。
* Google Scholar 与 IEEE 来源可以合并。
* 重复出现时 `seen_count` 正确增加。

### 第六阶段：状态控制

交付：

* 每封邮件事务式处理
* 成功后标记已读
* 失败保持未读
* 标记失败恢复逻辑
* dry-run

验收：

* Excel 未成功保存时绝不标记已读。
* 全部为重复论文时可以标记已读。
* dry-run 不修改文件和邮件状态。

### 第七阶段：真实邮件验证

使用用户提供的脱敏 `.eml` 样本：

* Google Scholar 搜索快讯至少 2 封
* `no-reply@ieee.org` 至少 1 封
* `no-reply@xplore.ieee.org` 至少 1 封

验证：

* 论文数量
* 字段准确性
* 多篇条目识别
* 快讯名称或作者名
* 跨来源去重
* 未读状态控制

---

## 21. 首次运行顺序

```bash
python -m scholar_alerts folders
```

将目标文件夹名称写入 `.env`。

然后：

```bash
python -m scholar_alerts test-connection
python -m scholar_alerts scan
python -m scholar_alerts process --dry-run --limit 3
```

核对：

* 发件人识别是否正确
* 每封邮件的论文数量
* 标题和作者是否准确
* IEEE Document ID 是否正确
* 去重结果是否合理

确认后运行：

```bash
python -m scholar_alerts process --limit 10
```

最后检查：

* `output/papers.xlsx`
* 163 网页端中的已读状态
* 日志中的错误或警告

---

## 22. 完成标准

项目完成时必须满足：

```bash
pytest
ruff check .
```

全部通过。

功能验收标准：

1. 只处理三个指定发件地址。
2. IEEE 普通系统邮件不会被误处理。
3. 读取邮件不会自动设置已读。
4. Google Scholar 多篇论文可以完整提取。
5. IEEE Author Alert 多篇论文可以完整提取。
6. 同一论文跨邮件只保留一条记录。
7. 同一论文跨 Google Scholar 和 IEEE 只保留一条记录。
8. Excel 写入失败时邮件保持未读。
9. 成功处理后邮件同步变为已读。
10. 重复运行不会产生重复行。
11. dry-run 不改变 Excel 和邮箱状态。
12. 不调用外部 API，不访问外部论文链接。

---

## 23. 已知限制

第一版不处理：

* 邮件正文中没有明确论文列表的提醒
* 附件中的论文列表
* JavaScript 动态生成内容
* 外部网页补全元数据
* 模糊标题合并
* 预印本和正式版自动关联
* 引用次数更新
* 摘要生成
* 论文分类和优先级评分

邮件模板发生明显变化时，需要更新对应解析器和测试 fixture。
