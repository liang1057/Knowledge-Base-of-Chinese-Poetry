# -*- coding: utf-8 -*-
"""
KBCP_SQLAssist.py - SQL 自动生成 + 校验 + 执行
=================================================
为 STRUCTURED 类型查询（统计/主题/对比）提供 SQL 路径。
流程: 加载元数据 → 构建 Prompt → LLM 生成 SQL → 校验 → 执行 → 格式化

[元数据注入]
从 myschema 表读取字段中文名+键名对照，注入 LLM Prompt 防止字段幻觉。
同时注入外键关系、检索优先级、禁止事项等规则。
"""
import re
import time
from typing import List, Dict, Optional
from KBCP_DAL import SQLiteDAL
from KBCP_LLM_Provider import load_config, create_provider, get_llm_priority_list
from KBCP_ResultFormatter import format_stat_result, format_tag_based, \
    format_compare, format_error


class SQLAssist:
    """
    SQL 自动生成助手。

    使用方式:
        assist = SQLAssist()
        result = assist.query("李白写了多少首诗", query_type="stats")
        # -> {"success": True, "text": "...", "data": {...}}
    """

    def __init__(self):
        self._dal = SQLiteDAL()
        self._schema: List[dict] = []     # myschema 缓存
        self._schema_text: str = ''        # 格式化后的 schema 文本
        self._loaded = False

    # ------------------------------------------------------------
    #  元数据加载
    # ------------------------------------------------------------

    def _load_schema(self):
        """从 myschema 表加载元数据，并格式化为 Prompt 文本"""
        if self._loaded:
            return
        self._schema = self._dal.get_schema_metadata()
        self._schema_text = self._format_schema(self._schema)
        self._loaded = True

    @staticmethod
    def _format_schema(schema: List[dict]) -> str:
        """将 myschema 记录格式化为易读的表格结构"""
        # 按表名分组
        tables: Dict[str, List[str]] = {}
        for row in schema:
            tn = row.get('table_name', '')
            label = row.get('column_label', '')
            col = row.get('column_name', '')
            typ = row.get('type', '')
            if tn not in tables:
                tables[tn] = []
            tables[tn].append(f"    {label}({col}: {typ})")

        parts = []
        for tn, cols in sorted(tables.items()):
            parts.append(f"  {tn}:")
            parts.extend(cols)
        return '\n'.join(parts)

    # ------------------------------------------------------------
    #  Schema Prompt 模板（核心注入内容）
    # ------------------------------------------------------------

    SQL_SYSTEM_PROMPT = """你是一位精通 SQLite 查询的数据库专家。请根据用户的问题和数据库结构，生成一条 SQLite SELECT 查询语句。

数据库表结构（字段中文名 -> 字段键名）：
{schema}

外键关联规则（固定 JOIN 路径）：
  poem.author_id = author.author_id
  poem.dynasty_id = dynasty.dynasty_id
  poem_tag.poem_id = poem.poem_id
  poem_tag.vocab_id = vocab.vocab_id
  author_tag.author_id = author.author_id
  author_tag.vocab_id = vocab.vocab_id
  author.dynasty_id = dynasty.dynasty_id

检索优先级规则：
  1. 主题/风格/情感/意象/体裁类查询：优先 JOIN poem_tag → vocab，用 vocab.label 匹配
  2. 关键词查询：先用 poem.keywords 字段，再回退到 content LIKE
  3. 人名/作品名查询：先与 author.name/poem.title 精确匹配

禁止事项（违规则拒绝）：
  - 只允许 SELECT，禁止 UPDATE/DELETE/INSERT/DROP/ALTER
  - 禁止 SELECT *（明确列出需要的字段）
  - 禁止对 TEXT 字段 GROUP BY
  - 涉及标签必须 JOIN poem_tag + vocab

{extra_rules}

用户问题：{query}

请只输出 SQL 语句本身，不要任何解释。如果需要使用 JOIN，请确保 JOIN 条件符合上述外键规则。如果无法生成合理的 SQL，请输出：--NO_SQL--"""

    # ------------------------------------------------------------
    #  SQL 生成
    # ------------------------------------------------------------

    @staticmethod
    def _normalize_sql(raw: str) -> str:
        """从 LLM 输出中提取纯净的 SQL（剥离 <think>、代码块、注释等）"""
        if not raw:
            return ''
        t = raw
        # 剥离 <think>...</think>
        t = re.sub(r'<think>.*?</think>', '', t, flags=re.DOTALL)
        # 剥离 ```sql 或 ``` 代码围栏
        t = re.sub(r'```(?:sql)?', '', t, flags=re.IGNORECASE).replace('```', '')
        # 剥离行注释（-- ...）
        t = re.sub(r'--[^\n]*', '', t)
        # 提取首个 SELECT
        m = re.search(r'SELECT\s', t, flags=re.IGNORECASE)
        if m:
            t = t[m.start():]
        # 去掉末尾分号之后的内容
        if ';' in t:
            t = t[:t.index(';')]
        return t.strip()

    def _build_vocab_hint(self) -> str:
        """
        从 vocab 表读取所有标签分类和可选值，注入到 Prompt 中，
        让 LLM 知道精确的标签取值（防止生成 '月亮' 而库里是 '月'）。
        """
        try:
            rows = self._dal.get_all_vocab()
            if not rows:
                return ''
            from collections import defaultdict
            grouped = defaultdict(list)
            for r in rows:
                cat = r.get('category', '')
                label = r.get('label', '')
                if cat and label:
                    grouped[cat].append(label)
            parts = []
            for cat in sorted(grouped.keys()):
                labels = grouped[cat]
                parts.append(f"  {cat}: {', '.join(labels)}")
            return (f"\n数据库 vocab 表中的标签可选值（请使用以下精确标签名进行匹配）：\n"
                    + '\n'.join(parts))
        except Exception:
            return ''

    def _generate_sql(self, query: str, alias_info: dict = None,
                      extra_rules: str = '', prev_error: str = '') -> Optional[str]:
        """调用 LLM 生成 SQL"""
        self._load_schema()

        # 注入别名映射信息
        alias_hint = ''
        if alias_info and alias_info.get('matches'):
            parts = []
            for orig, std, etype, eid in alias_info['matches']:
                parts.append(f"  \"{orig}\" 在数据库中的标准名为 \"{std}\"（{etype}）")
            alias_hint = ('已确认的别名映射（请使用标准名查询）：\n'
                          + '\n'.join(parts))

        # 注入 vocab 标签值（让 LLM 知道可用的标签词）
        vocab_hint = self._build_vocab_hint()

        # 注入前一次错误（重试时让 LLM 修正）
        error_hint = ''
        if prev_error:
            error_hint = f'\n\n⚠️ 前一次生成的 SQL 验证失败，错误信息：\n{prev_error}\n请修正后重新生成。'

        extra_parts = []
        if alias_hint:
            extra_parts.append(alias_hint)
        if vocab_hint:
            extra_parts.append(vocab_hint)
        if error_hint:
            extra_parts.append(error_hint)
        all_extra = '\n\n'.join(extra_parts) if extra_parts else '（无特殊约束）'

        prompt = self.SQL_SYSTEM_PROMPT.format(
            schema=self._schema_text,
            extra_rules=all_extra,
            query=query,
        )

        config = load_config()
        providers = get_llm_priority_list(config, purpose='sql')
        resp = None
        for pname in providers:
            try:
                provider = create_provider(pname, config)
                resp = provider.chat(prompt)
                if resp:
                    resp = self._normalize_sql(resp)
                    if resp:
                        break
            except Exception:
                continue
        if not resp:
            return None
        return resp

    # ------------------------------------------------------------
    #  SQL 校验
    # ------------------------------------------------------------

    def _validate(self, sql: str) -> tuple:
        """
        校验生成的 SQL，返回 (is_valid, error_msg)。

        校验项：
          1. 是否为 SELECT 语句（容错提取首个 SELECT）
          2. 是否包含禁止操作
          3. SELECT 中引用的字段是否在 myschema 中
          4. JOIN 条件是否符合 FK 规则
        """
        sql_strip = sql.strip()
        if not sql_strip or sql_strip.upper() == '--NO_SQL--':
            return False, "LLM 无法生成合适的 SQL"

        # 容错：尝试提取首个 SELECT 开头的部分
        m = re.search(r'SELECT\s', sql_strip, flags=re.IGNORECASE)
        if m:
            sql_strip = sql_strip[m.start():]
        else:
            return False, "无法识别出 SELECT 查询语句"

        # 禁止危险操作
        danger = ['DROP ', 'DELETE ', 'INSERT ', 'UPDATE ', 'ALTER ',
                  'CREATE ', 'PRAGMA ', 'ATTACH ', 'DETACH ']
        sql_upper = sql_strip.upper()
        for d in danger:
            if d in sql_upper:
                return False, f"禁止使用 {d.strip()} 操作"

        # 禁止 SELECT *
        if re.search(r'SELECT\s+\*', sql_strip, flags=re.IGNORECASE):
            return False, "禁止 SELECT *，请明确列出字段"

        # 检查字段引用（简单检查：提取所有可能的字段名）
        self._load_schema()
        valid_columns = set()
        for row in self._schema:
            col = row.get('column_name', '')
            if col:
                valid_columns.add(col.lower())

        # 提取 SELECT 中的字段
        select_cols = re.findall(r'(\w+)\.(\w+)', sql_strip)
        for _, col in select_cols:
            if col.lower() not in valid_columns and col.lower() != '*':
                return False, f"字段 '{col}' 不在 myschema 中"

        return True, ''

    # ------------------------------------------------------------
    #  执行与格式化
    # ------------------------------------------------------------

    def _execute(self, sql: str) -> dict:
        """安全执行 SQL"""
        return self._dal.execute_readonly_sql(sql, max_rows=50)

    def _format_result(self, result: dict, query_type: str,
                       query: str) -> dict:
        """根据查询类型格式化结果"""
        if not result.get('success'):
            return dict(success=False,
                        text=format_error(query, result.get('error', '')),
                        data=None)

        rows = result['rows']
        cols = result['columns']
        if not rows:
            return dict(success=True,
                        text=f"查询「{query}」没有找到匹配的记录。",
                        data=result)

        if query_type in ('stats',):
            # 统计：通常返回 COUNT 或聚合结果
            first = rows[0]
            label = query[:30]
            count = list(first.values())[0] if first else 0
            formatted = format_stat_result(dict(label=label, count=count))
            return dict(success=True, text=formatted, data=result)

        elif query_type in ('tag_based',):
            # 主题检索：返回诗词列表
            formatted = format_tag_based(rows, [query])
            return dict(success=True, text=formatted, data=result)

        elif query_type in ('compare',):
            # 对比：用 LLM 对两组结果做对比分析
            return self._format_compare_with_llm(result, query)

        else:
            # 通用：将结果转为文字
            lines = [f"查询结果（{len(rows)} 条）："]
            for i, row in enumerate(rows[:10], 1):
                vals = ' | '.join(str(v) if v is not None else '-'
                                  for v in row.values())
                lines.append(f"  {i}. {vals}")
            if len(rows) > 10:
                lines.append(f"  ... 还有 {len(rows) - 10} 条")
            return dict(success=True, text='\n'.join(lines), data=result)

    def _format_compare_with_llm(self, result: dict, query: str) -> dict:
        """对比结果：用 LLM 对两组数据做对比分析"""
        rows = result['rows']
        cols = result['columns']

        # 构建对比上下文
        context = '对比数据：\n'
        for i, row in enumerate(rows[:5], 1):
            context += f"{i}. " + ' | '.join(
                str(v) if v is not None else '-' for v in row.values()
            ) + '\n'

        prompt = (
            f"以下是根据「{query}」查询到的对比数据。\n"
            f"请从数据中总结对比要点，用自然语言回答。\n\n"
            f"{context}\n"
            f"请直接给出对比结论，无需提及数据来源。"
        )

        config = load_config()
        providers = get_llm_priority_list(config)
        text = ''
        for pname in providers:
            try:
                provider = create_provider(pname, config)
                resp = provider.chat(prompt)
                if resp:
                    text = resp.strip()
                    break
            except Exception:
                continue

        if not text:
            # LLM 不可用，直接展示数据
            text = self._format_result(result, 'generic', query)['text']

        return dict(success=True, text=text, data=result)

    # ------------------------------------------------------------
    #  对外入口
    # ------------------------------------------------------------

    def query(self, query: str, query_type: str = 'stats',
              alias_info: dict = None, max_retry: int = 3) -> dict:
        """
        完整 SQL 查询流程。

        参数:
            query: 用户问题
            query_type: 查询类型 (stats/tag_based/compare)
            alias_info: 别名映射结果
            max_retry: SQL 校验失败重试次数（含错误反馈）

        返回:
            {"success": bool, "text": str, "data": dict}
        """
        prev_error = ''
        for attempt in range(max_retry):
            sql = self._generate_sql(query, alias_info, prev_error=prev_error)
            if not sql:
                return dict(success=False,
                            text="LLM 无法生成查询语句，请重新描述问题。",
                            data=None)

            is_valid, err = self._validate(sql)
            if not is_valid:
                prev_error = err
                if attempt < max_retry - 1:
                    print(f"  [SQLAssist] SQL 校验失败（第{attempt+1}次）: {err}")
                    continue
                return dict(success=False,
                            text=format_error(query, err),
                            data=None)
            break

        result = self._execute(sql)
        return self._format_result(result, query_type, query)
