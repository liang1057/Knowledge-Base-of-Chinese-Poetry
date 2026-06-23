# 诗词库网站

基于 Flask 的中国诗词库网站，支持朝代-作者-诗词三级导航，提供诗词展示、编辑和管理功能。

## 项目信息

- **项目路径**: `D:\WorkBuddy\Knowledge-Base-of-Chinese-Poetry\web2`
- **数据库**: SQLite（27.5MB）
- **数据量**: 16个朝代 / 4605位作者 / 62361首诗词

## 技术栈

- **后端**: Python Flask + Flask-SQLAlchemy
- **前端**: HTML/CSS/JS + jQuery + jstree + Bootstrap 5
- **数据库**: SQLite

## 快速开始

### 1. 安装依赖

```bash
cd D:\WorkBuddy\Knowledge-Base-of-Chinese-Poetry\web2
pip install flask flask-sqlalchemy
```

### 2. 启动应用

```bash
python app.py
```

### 3. 访问网站

打开浏览器访问: **http://127.0.0.1:5001**

## 功能介绍

### 首页 - 诗词展示

- **左侧导航**: 朝代 → 作者 → 诗词三级树形结构（懒加载）
- **中部展示**: 诗词正文、赏析、翻译（可编辑）
- **右侧属性**: 体裁、形式、主题、风格等属性（可编辑）
- **统一保存**: 点击保存按钮一次性保存所有修改

### 内容管理

- 添加/编辑/删除作者
- 添加/删除诗词
- 级联删除（删除作者时同时删除其诗词）

## API 接口

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/` | 首页 |
| GET | `/manage` | 内容管理页 |
| GET | `/api/dynasties` | 获取朝代列表 |
| GET | `/api/authors/<dynasty_id>` | 获取某朝代作者 |
| GET | `/api/poems/<author_id>` | 获取某作者诗词 |
| GET | `/api/poem/<poem_id>` | 获取诗词详情 |
| POST | `/api/poem/save/<poem_id>` | 保存诗词 |
| POST | `/api/author/add` | 添加作者 |
| POST | `/api/author/edit/<author_id>` | 编辑作者 |
| POST | `/api/author/delete/<author_id>` | 删除作者 |
| POST | `/api/poem/add` | 添加诗词 |
| POST | `/api/poem/delete/<poem_id>` | 删除诗词 |
| GET | `/api/stats` | 获取统计信息 |

## 数据库结构

### dynasty（朝代表）

| 字段 | 类型 | 说明 |
|------|------|------|
| dynasty_id | TEXT | 朝代ID |
| name | TEXT | 朝代名称 |
| another_name | TEXT | 别名 |
| start_year | INT | 起始年份 |
| end_year | INT | 结束年份 |
| note | TEXT | 备注 |

### author（作者表）

| 字段 | 类型 | 说明 |
|------|------|------|
| author_id | TEXT | 作者ID |
| name | TEXT | 姓名 |
| dynasty | TEXT | 朝代名称 |
| dynasty_id | TEXT | 朝代ID |
| courtesy_name | TEXT | 字 |
| art_name | TEXT | 号 |
| bio | TEXT | 生平简介 |
| ... | ... | ... |

### poem（诗词表）

| 字段 | 类型 | 说明 |
|------|------|------|
| poem_id | TEXT | 诗词ID |
| title | TEXT | 标题 |
| author | TEXT | 作者名称 |
| dynasty | TEXT | 朝代名称 |
| content | TEXT | 正文 |
| appreciation | TEXT | 赏析 |
| translation | TEXT | 翻译 |
| genre | TEXT | 体裁 |
| form | TEXT | 形式 |
| theme | TEXT | 主题 |
| style | TEXT | 风格 |
| emotion | TEXT | 情感 |
| imagery | TEXT | 意象 |
| ... | ... | ... |

## 项目结构

```
web2/
├── app.py                 # Flask 主程序
├── config.py              # 配置文件
├── models.py              # 数据库模型
├── README.md              # 本文件
├── TODO.md                # 开发进度
├── templates/
│   ├── base.html          # 基础模板
│   ├── index.html         # 首页（诗词展示）
│   └── manage.html        # 内容管理页
├── static/
│   ├── css/
│   │   └── style.css      # 自定义样式
│   ├── js/
│   │   ├── tree.js        # 树控件交互
│   │   └── editor.js      # 编辑器脚本
│   └── lib/
│       ├── jquery/         # jQuery
│       ├── bootstrap/      # Bootstrap
│       └── jstree/         # jstree
└── db/
    └── kbcp.db             # 数据库文件
```

## 使用说明

### 浏览诗词

1. 在左侧树形导航中点击朝代展开作者列表
2. 点击作者名称展开诗词列表
3. 点击诗词标题在中部显示详情

### 编辑诗词

1. 选择诗词后，在中部编辑正文/赏析/翻译
2. 在右侧修改属性值
3. 点击"保存修改"按钮保存

### 管理内容

1. 点击顶部导航"内容管理"
2. 选择朝代后可以添加/编辑作者
3. 选择作者后可以添加/删除诗词

## 注意事项

- 数据库已有完整数据，无需初始化
- 修改诗词后记得点击保存按钮
- 删除作者会级联删除其所有诗词

## License

MIT License
