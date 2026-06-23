# 诗词库网站开发进度

## 项目信息
- **项目路径**: `D:\WorkBuddy\Knowledge-Base-of-Chinese-Poetry\web2`
- **数据库**: `D:\WorkBuddy\Knowledge-Base-of-Chinese-Poetry\db\kbcp.db`
- **数据量**: 16个朝代 / 4605位作者 / 62361首诗词

## 技术栈
- **后端**: Python Flask + Flask-SQLAlchemy
- **前端**: HTML/CSS/JS + jQuery + jstree + Bootstrap 5
- **数据库**: SQLite（已有数据）

---

## 功能清单

### 1. 首页 - 诗词展示
- [x] 左侧树控件（三级导航：朝代 → 作者 → 诗词）
- [x] 中部诗词展示区（标题、朝代、作者、正文、赏析）
- [x] 右侧属性表（体裁、形式、主题、风格等）
- [x] 保存功能（统一保存正文+赏析+属性）

### 2. 内容管理
- [ ] 添加作者
- [ ] 编辑作者信息
- [ ] 删除作者（级联删除诗词）
- [ ] 添加诗词
- [ ] 删除诗词

### 3. 高级功能
- [ ] 搜索功能
- [ ] 收藏功能
- [ ] 导出功能

---

## 开发进度

| 阶段 | 任务 | 状态 |
|------|------|------|
| 第一阶段 | 1.1 创建目录结构 | ✅ |
| 第一阶段 | 1.2 创建 config.py | ⏳ |
| 第一阶段 | 1.3 创建 models.py | ⏳ |
| 第二阶段 | 2.1 创建 app.py 主程序 | ⏳ |
| 第二阶段 | 2.2 API 路由实现 | ⏳ |
| 第三阶段 | 3.1 base.html 模板 | ⏳ |
| 第三阶段 | 3.2 index.html 首页 | ⏳ |
| 第三阶段 | 3.3 manage.html 管理页 | ⏳ |
| 第三阶段 | 3.4 CSS 样式 | ⏳ |
| 第三阶段 | 3.5 JS 交互逻辑 | ⏳ |
| 第四阶段 | 4.1 下载第三方库 | ⏳ |
| 第四阶段 | 4.2 复制数据库 | ⏳ |
| 第四阶段 | 4.3 创建 README.md | ⏳ |
| 第四阶段 | 4.4 测试运行 | ⏳ |

---

## 数据库表结构

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
| dynasty_id | TEXT | 朝代ID |
| content | TEXT | 正文 |
| appreciation | TEXT | 赏析 |
| genre | TEXT | 体裁 |
| form | TEXT | 形式 |
| theme | TEXT | 主题 |
| style | TEXT | 风格 |
| ... | ... | ... |

---

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

---

## 进度记录

| 日期 | 完成内容 | 状态 |
|------|---------|------|
| 2026-04-22 | 创建目录结构 | ✅ |
| 2026-04-22 | 创建配置文件 | ✅ |
| 2026-04-22 | 创建数据库模型 | ✅ |
| 2026-04-22 | 创建 Flask 主程序 | ✅ |
| 2026-04-22 | 创建前端模板 | ✅ |
| 2026-04-22 | 创建静态资源 | ✅ |
| 2026-04-22 | 下载第三方库 | ✅ |
| 2026-04-22 | 复制数据库 | ✅ |
| 2026-04-22 | 测试运行 | ✅ |
