# 量身文化，中华诗词知识库 (KBCP)

基于 Flask 的中华诗词管理与阅读系统，v2 版本重构了数据库 Schema，引入外键约束和标签中间表，支持受控词表管理和精细化标签操作。

## 项目信息

- **项目**: 中华诗词知识库 Knowledge Base of Chinese Poetry (KBCP)
- **数据库**: SQLite
- **数据量**: 16 个朝代 / 4,611 位诗人 / 62,450 首诗词 / 12 类受控词表
- **定位**: 数据管理与可视化编辑，为后续 RAG（检索增强生成）提供高质量结构化数据

## 技术栈

- **后端**: Python 3 + Flask + Flask-SQLAlchemy
- **前端**: HTML/CSS/JS + jQuery + Bootstrap 5 + jsTree + Font Awesome
- **数据库**: SQLite（FK 约束 + 复合主键）

## 快速开始

### 1. 安装依赖

```bash
cd Prj_Poetry_China
pip install flask flask-sqlalchemy werkzeug opencc-python-reimplemented
```

### 2. 生成数据库（首次运行）

```bash
python KBCP_RAG_Poetry_DB.py
```

该脚本会：
- 创建 `dataset/kbcp.db`（新 Schema：带 FK + 中间表 + 归一化 vocab）
- 从 `data/Poetry_China_all.json` 导入全部诗词数据
- 初始化受控词表（主题、风格、情感、意象等 12 个类别）
- 为每首诗词自动添加默认标签（体裁、审核状态等）

### 3. 启动 Web

```bash
cd KBCP_web
python KBCP_app.py
```

默认地址: **http://127.0.0.1:8081**

默认管理员账号: **admin** / **admin123**

## 页面布局

```
┌──────────────────────────────────────────────────────────────────┐
│  [导航栏]  诗词库 v2  |  首页  |  管理  |  搜索  |  [用户名/退出] │
├──────────┬──────────┬──────────────────────┬────────────────────┤
│  左一栏   │  左二栏   │      左三栏          │      左四栏        │
│ 朝代-诗人 │ 诗词列表  │  标题 / 作者         │    诗词标签        │
│  树形导航 │          │  正文（可编辑）      │   [+增加标签]       │
│          │          │  赏析（可编辑）      │   [清除标签]        │
│  先秦(4) │  静夜思   │  翻译（可编辑）      │   # 体裁            │
│  唐(2475)│  望庐山   │  [保存修改]          │   诗 [×]           │
│   │─李白  │  瀑布    │                     │   # 主题            │
│   │─杜甫  │  将进酒   │                     │   思乡 [×] 月夜 [×] │
│  宋(1497)│  ...     │                     │   # 情感            │
│  ...     │          │                     │   悲伤 [×]          │
├──────────┴──────────┴──────────────────────┴────────────────────┤
│  统计栏:  16 朝代 | 4611 诗人 | 62450 诗词 | 175 标签           │
└──────────────────────────────────────────────────────────────────┘
```

## 功能介绍

### 诗词浏览

1. 左侧树形导航：点击**朝代**展开诗人列表，点击**诗人**加载其诗词列表
2. 点击诗词标题，中部显示详情（正文用楷体展示，保留排版）
3. 右侧显示诗词的完整标签（按体裁、形式、主题、风格、情感、季节等分组）

### 诗词编辑（管理员）

1. 选中一首诗后，在中间面板编辑正文、赏析、翻译
2. 点击「保存修改」按钮提交
3. 右侧标签面板：
   - **[+增加标签]**：弹出标签选择器，可按类别勾选多个标签批量添加
   - **单个标签 [×]**：点击删除单个标签
   - **[清除标签]**：一键清除本诗全部标签

### 内容管理（`/admin`）

后台以 Tab 页形式提供 5 个管理模块：

| Tab | 功能 |
|-----|------|
| **朝代管理** | 添加/编辑/删除朝代（有诗人的朝代禁止删除） |
| **作者管理** | 按朝代筛选，添加/编辑/级联删除作者（同时删除其所有诗词） |
| **诗词管理** | 按朝代→作者筛选，添加/删除诗词 |
| **受控词表** | 按类别展示所有词条，可新增词条、删除词条（被引用的词条禁止删除） |
| **用户管理** | 仅超级管理员可见，添加/删除管理员账号 |

### 角色与权限

| 角色 | 权限 |
|------|------|
| **超级管理员** | 所有权限 + 用户管理（添加/删除管理员） |
| **管理员** | 所有管理功能（朝代/作者/诗词/标签 CRUD） |
| **普通用户** | 仅浏览查看，无编辑权限 |

## API 接口

### 公开接口

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/` | 首页 |
| GET | `/login` | 登录页 |
| GET | `/api/dynasties` | 获取朝代树一级节点（含诗人数量） |
| GET | `/api/authors/<dynasty_id>` | 获取某朝代诗人列表（含诗词数量） |
| GET | `/api/poems/<author_id>` | 获取某诗人诗词列表 |
| GET | `/api/poem/detail?poem_id=` | 获取诗词详情（含标签） |
| GET | `/api/poem/tags?poem_id=` | 获取诗词标签列表 |
| GET | `/api/vocab/<category>` | 获取某类受控词表 |
| GET | `/api/vocab/categories` | 获取所有受控词表类别 |
| GET | `/api/search?q=` | 搜索诗词 |
| GET | `/api/stats` | 统计数据 |
| GET | `/api/me` | 当前登录用户信息 |
| POST | `/api/login` | 登录 |
| POST | `/api/logout` | 登出 |

### 管理接口（需 admin/superadmin）

| 方法 | 路由 | 说明 |
|------|------|------|
| POST | `/api/poem/save` | 保存诗词编辑 |
| POST | `/api/poem/add` | 添加诗词 |
| POST | `/api/poem/delete` | 删除诗词 |
| POST | `/api/poem/tag/add` | 添加标签（批量） |
| POST | `/api/poem/tag/remove` | 移除标签 |
| POST | `/api/poem/tag/clear` | 清除全部标签 |
| POST | `/api/author/add` | 添加作者 |
| POST | `/api/author/edit/<author_id>` | 编辑作者 |
| POST | `/api/author/delete/<author_id>` | 删除作者（级联删除诗词） |
| POST | `/api/dynasty/add` | 添加朝代 |
| POST | `/api/dynasty/edit/<dynasty_id>` | 编辑朝代 |
| POST | `/api/dynasty/delete/<dynasty_id>` | 删除朝代 |
| POST | `/api/vocab/add` | 添加受控词条 |
| POST | `/api/vocab/delete/<vocab_id>` | 删除受控词条 |

### 超级管理员接口

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/users` | 获取用户列表 |
| POST | `/api/user/add` | 添加用户 |
| POST | `/api/user/delete/<user_id>` | 删除用户 |

## 数据库结构（v2 Schema）

### 7 张表

```
dynasty ──1:N──> author ──1:N──> poem
vocab  <──N:M──> poem    (通过 poem_tag 中间表)
vocab  <──N:M──> author  (通过 author_tag 中间表)
```

#### dynasty（朝代表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| dynasty_id | TEXT | PK | 朝代唯一编号 |
| name | TEXT | NOT NULL | 朝代名称 |
| another_name | VARCHAR | | 别名 |
| start_year | INT | | 起始年 |
| end_year | INT | | 结束年 |
| note | TEXT | | 备注 |

#### author（作者表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| author_id | TEXT | PK | 作者唯一编号 |
| name | TEXT | NOT NULL | 姓名 |
| dynasty_id | TEXT | FK → dynasty | 所属朝代 |
| courtesy_name | TEXT | | 字 |
| art_name | VARCHAR | | 号 |
| other_names | VARCHAR | | 其他别名 |
| birth_year | INT | | 出生年 |
| death_year | INT | | 卒年 |
| birth_place | TEXT | | 籍贯 |
| bio | TEXT | | 生平简介 |
| ... | | | |

#### poem（诗词表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| poem_id | TEXT | PK | 作品编号 |
| title | TEXT | NOT NULL | 标题 |
| author_id | TEXT | FK → author | 作者 |
| dynasty_id | TEXT | FK → dynasty | 朝代 |
| content | TEXT | | 全文 |
| appreciation | TEXT | | 赏析 |
| translation | TEXT | | 白话释义 |
| line_count | INT | | 行数 |
| char_count | INT | | 字数 |
| ... | | | |

所有标签字段（genre / form / theme / style / emotion 等）已从 poem 表剥离，移至 `poem_tag` 中间表。

#### vocab（受控词表）

归一化结构，每条记录一个词条：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| vocab_id | TEXT | PK | 如 V-THM-001 |
| category | TEXT | NOT NULL | 类别（theme/style/emotion 等） |
| label | TEXT | NOT NULL | 中文名 |
| sort_order | INT | | 排序 |

#### poem_tag（诗词标签中间表）

| 字段 | 类型 | 约束 |
|------|------|------|
| poem_id | TEXT | FK → poem, PK |
| vocab_id | TEXT | FK → vocab, PK |
| tag_type | TEXT | 标签类别（冗余） |

#### author_tag（作者标签中间表）

同上结构，FK → author + vocab。

#### myschema（元数据表）

记录所有表的字段信息，辅助工具使用。

## 项目结构

```
Prj_Poetry_China/
├── dataset/
│   └── kbcp.db               # 数据库文件（新 Schema v2）
├── data/
│   ├── Poetry_China_all.json  # 原始诗词数据
│   ├── Dynasty.json           # 朝代数据
│   ├── Author.json            # 诗人数据
│   └── ...
├── KBCP_RAG_Poem_Schema.py   # Schema 定义（v2）
├── KBCP_RAG_Poetry_DB.py     # 数据库构建脚本
├── KBCP_web/                  # Web 应用（本文件）
│   ├── KBCP_app.py            # Flask 主程序
│   ├── KBCP_auth.py           # 认证模块
│   ├── KBCP_models.py         # SQLAlchemy ORM 模型
│   ├── config.py              # 配置文件
│   ├── templates/
│   │   ├── KBCP_base.html     # 基础模板
│   │   ├── KBCP_index.html    # 首页（四栏布局）
│   │   ├── KBCP_admin.html    # 管理后台
│   │   ├── KBCP_admin_modals.html  # 管理 Modal
│   │   └── KBCP_login.html    # 登录页
│   └── static/
│       ├── css/
│       │   └── KBCP_style.css # 自定义样式
│       └── js/
│           ├── KBCP_tree.js   # 树控件逻辑
│           ├── KBCP_editor.js # 编辑器 + 标签管理
│           └── KBCP_admin.js  # 管理后台脚本
└── web/                       # 原有 Web（v1，保留）
```

## 与 v1 的核心差异

| 对比项 | v1（web/） | v2（KBCP_web/） |
|--------|-----------|----------------|
| 标签存储 | poem 表直接存文本字段 | 剥离到 `poem_tag` 中间表 |
| 跨表引用 | 文本字符串（无约束） | FK 约束（author_id / dynasty_id） |
| 受控词表 | JSON 数组存储 | 归一化单条记录 |
| 标签管理 | 纯文本输入框 | 受控词表选择器 + 可视化标签控件 |
| 认证 | 无 | 三角色体系（user/admin/superadmin） |
| 用户管理 | 无 | 超级管理员可管理 |

## 注意事项

- 首次运行需执行 `KBCP_RAG_Poetry_DB.py` 生成数据库
- 数据库采用 PRAGMA foreign_keys = ON 开启外键约束
- 删除作者会级联删除其所有诗词及标签
- 删除受控词条前需先解除所有引用
- 默认端口 8081，可通过环境变量 `PORT` 修改

---

## 智能诗词打标签工具

`KBCP_AutoTag.py` 是一个独立的后台脚本，遍历所有诗词，调用大语言模型自动分析并为每首诗添加标签（主题、风格、情感、意象等），利用 v2 Schema 的 `poem_tag` + `vocab` 中间表存入数据库。

### 设计目标

- **自动化**：对 6.2 万首诗词自动打标，减少人工标注成本
- **受控词表约束**：LLM 只能从现有的 vocab 词条中选择，不自创标签，保证数据一致性
- **增量更新**：支持断点续传，已分析的诗不会重复处理
- **多模型后端**：支持本地模型和云端 API，根据需求灵活切换

### 技术架构

```
KBCP_AutoTag.py (分析逻辑)
  └── KBCP_LLM_Provider.py (提供者抽象层)
       ├── OllamaProvider       (本地: http://localhost:11434)
       ├── DeepSeekProvider     (云端: api.deepseek.com)
       └── ZhipuProvider        (云端: open.bigmodel.cn)
            ├── _chat_with_sdk()    (优先: zhipuai SDK)
            └── _chat_with_http()   (回退: requests 直接调用)
```

### 快速使用

```bash
# 1. 安装依赖
pip install requests
pip install zhipuai          # 仅使用智谱时需要

# 2. 查看统计
python KBCP_AutoTag.py -m stats

# 3. 增量分析：先测试 5 首
python KBCP_AutoTag.py -m missing -c theme -l 5

# 4. 使用不同提供者（需先配置 KBCP_LLM_config.ini）
python KBCP_AutoTag.py -p ollama                         # Ollama 本地
python KBCP_AutoTag.py -p deepseek -m missing -c style    # DeepSeek 云端
python KBCP_AutoTag.py -p zhipu -m missing -c imagery     # 智谱 GLM 云端
```

### 配置文件

`KBCP_LLM_config.ini` 控制提供者选择和参数：

```ini
[provider]
default = ollama

[ollama]
url = http://localhost:11434/api/chat
model = deepseek-r1:8b

[deepseek]
api_key = sk-your-key-here
model = deepseek-chat
base_url = https://api.deepseek.com/v1/chat/completions

[zhipu]
api_key = your-key-here
model = glm-4-flash
base_url = https://open.bigmodel.cn/api/paas/v4/chat/completions

[common]
request_interval = 0.3
max_content_len = 600
```

> 配置文件包含 API Key，**不应提交到 Git**。首次运行自动创建，编辑填写 Key 后生效。

### 命令行参数

| 参数 | 说明 |
|------|------|
| `-m, --mode` | 运行模式: `all`(全量) / `missing`(增量,默认) / `full`(不分类全量) / `stats`(统计) |
| `-c, --category` | 增量模式检查的标签类别，默认 `theme` |
| `-l, --limit` | 限制分析数量，用于测试 |
| `-p, --provider` | 提供者: `ollama` / `deepseek` / `zhipu`，默认使用配置文件 |

### 打标的标签类别

| 类别 | 英文键 | 词条数 | 说明 |
|------|--------|--------|------|
| 主题 | theme | 20 | 思乡、送别、边塞、山水、咏物等 |
| 风格 | style | 15 | 豪放、婉约、沉郁、清新等 |
| 情感 | emotion | 20 | 喜悦、悲伤、忧愁、离别等 |
| 意象 | imagery | 25 | 月、柳、花、雨、风、山、水等 |
| 季节 | season | 5 | 春、夏、秋、冬、其他 |
| 节令 | festival | 7 | 春节、中秋、端午、重阳等 |
| 典故 | allusion | (可扩展) | 暂为空，LLM 可分析后扩充 |

> 体裁（genre）、形式（form）、审核状态（review_status）已有默认值，不打标。

### 打标流程

```
┌──────────────────────────────────────────────────┐
│  1. 从 poem 表获取未分析的诗                     │
│     (通过 auto_tag_log 判断)                     │
├──────────────────────────────────────────────────┤
│  2. 从 vocab 表读取 7 类受控词条                 │
├──────────────────────────────────────────────────┤
│  3. 构建 Prompt，将标签列表和诗词一起发送给 LLM   │
│     (分析 → 返回 JSON 格式标签)                  │
├──────────────────────────────────────────────────┤
│  4. 解析 LLM 返回的 JSON                         │
│     (无思考链清洗，直接提取 JSON 对象)            │
├──────────────────────────────────────────────────┤
│  5. 查询 vocab_id → 写入 poem_tag 表            │
│     (INSERT OR IGNORE 去重)                     │
├──────────────────────────────────────────────────┤
│  6. 写入 auto_tag_log (断点续传)                │
└──────────────────────────────────────────────────┘
```

### Prompt 设计

```text
你是一位精通中华诗词的分析专家。分析下面这首诗，为每个类别
从可用标签中选择最合适的标签（每个类别最多选3个）。

要求：
1. 只输出 JSON 格式，不要输出任何其他内容
2. 仅从下方"可用标签"中选择，不要自创标签
3. 类别名称使用英文
4. 如果某类别无法确定，省略该字段

输出示例：
{"theme":"思乡","style":"清新","emotion":"哀愁","imagery":"月","season":"秋"}

可用标签：
【theme】思乡、送别、边塞、怀古、山水、田园……
【style】豪放、婉约、沉郁、清新、雄浑……
……

诗题：静夜思
作者：李白
诗歌正文：
床前明月光
疑是地上霜
……
```

### LLM 结果解析

`parse_llm_response()` 采用**先提取 JSON 后解析**策略（而非先清洗后提取），避免误删 JSON 数组语法：

```python
def parse_llm_response(response_text, vocab):
    # 1. 直接定位 JSON 对象（防止方括号被误当作思考链清除）
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)

    # 2. 尝试解析，带自动修复（单引号/末尾逗号）
    ...

    # 3. 标签匹配：精确优先 → 模糊匹配（包含关系）兜底
    for cat in TAG_CATEGORIES:
        label = result.get(cat, "")
        if 精确匹配(vocab):
            tags[cat] = label
        elif 模糊匹配(vocab):
            tags[cat] = matched_label
```

### 断点续传

`auto_tag_log` 表记录每次分析结果：

```sql
CREATE TABLE auto_tag_log (
    poem_id     TEXT PRIMARY KEY,
    analyzed_at TEXT NOT NULL,
    model       TEXT NOT NULL,
    tag_count   INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'ok'
);
```

- 程序启动时先检查该表，跳过已分析的诗
- 成功/失败/解析失败均有状态记录
- 支持中断后重跑，不会重复分析

### 提供者性能对比

| 提供者 | 模型 | 每首耗时(估) | 1万首耗时 | 成本 | 需要 |
|--------|------|-------------|----------|------|------|
| Ollama 本地 | deepseek-r1:8b | 5-15s | 14-42h | 免费 | 本地 GPU |
| DeepSeek API | deepseek-chat | 1-3s | 3-8h | ~¥0.5/百万token | API Key |
| 智谱 GLM API | glm-4-flash | 1-3s | 3-8h | ~¥0.5/百万token | API Key + `pip install zhipuai` |

### 并发机制

当前采用**串行**策略（每首间隔 `request_interval` 秒），避免 Ollama 过载或触发云端 API 限流。未来可通过 `ThreadPoolExecutor` 扩展并发。

### 新增文件清单

| 文件 | 说明 |
|------|------|
| `KBCP_AutoTag.py` | 主逻辑：遍历诗词 → 调 LLM → 解析 → 写入 poem_tag |
| `KBCP_LLM_Provider.py` | LLM 提供者抽象层（3 个实现 + 工厂 + 配置加载） |
| `KBCP_LLM_config.ini` | 配置文件（含 API Key，已加入 .gitignore） |
| `KBCP_LLM_config.example.ini` | 配置模板（无 Key，可提交到 Git） |
