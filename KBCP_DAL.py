# -*- coding: utf-8 -*-
"""
KBCP_DAL.py - 数据访问层 (Data Access Layer)
==============================================
统一接口，AI 功能层通过 DAL 查询数据，不直接操作 ORM / SQL。
未来替换为 Neo4j 图数据库后端时，只需实现 Neo4jDAL 并切换配置。

使用方式:
    # 独立脚本
    dal = SQLiteDAL(db_path="dataset/kbcp.db")
    poem = dal.get_poem_by_id("T00001_00000")

    # Flask 环境（传入已有的 db.session）
    dal = SQLiteDAL(db_session=db.session)
    poem = dal.get_poem_by_id("T00001_00000")
"""
import sqlite3
import json
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Optional, List, Dict


# ============================================================
#  基础数据对象 (Plain Old Python Objects)
# ============================================================

class PoemData:
    """诗词数据对象"""
    __slots__ = (
        'poem_id', 'title', 'author_id', 'dynasty_id',
        'content', 'paragraphs', 'sentences', 'line_count', 'char_count',
        'description', 'translation', 'appreciation', 'background',
        'historical_context', 'keywords', 'places_involved', 'people_involved',
        'citation_text', 'aliases', 'related_poem_ids',
        'created_at', 'updated_at', 'data_version',
        # 关联数据（需要额外加载）
        'author_name', 'dynasty_name', 'tags',
    )

    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k, '' if k in (
                'poem_id', 'title', 'author_id', 'dynasty_id', 'content',
                'description', 'translation', 'appreciation', 'background',
                'historical_context', 'keywords', 'places_involved',
                'people_involved', 'citation_text', 'aliases',
                'related_poem_ids', 'created_at', 'updated_at', 'data_version',
                'author_name', 'dynasty_name', 'paragraphs', 'sentences',
            ) else None))

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


class AuthorData:
    """诗人数据对象"""
    __slots__ = (
        'author_id', 'name', 'dynasty_id',
        'courtesy_name', 'art_name', 'other_names',
        'birth_year', 'death_year', 'birth_place', 'bio',
        'historical_role', 'representative_works',
        'representative_poem_ids', 'created_at', 'updated_at',
        'dynasty_name',
    )

    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k, ''))

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


class DynastyData:
    """朝代数据对象"""
    __slots__ = ('dynasty_id', 'name', 'another_name',
                 'start_year', 'end_year', 'note')

    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k, ''))

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


class TagData:
    """标签数据对象"""
    __slots__ = ('poem_id', 'vocab_id', 'tag_type', 'label', 'category')

    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k, ''))

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


# ============================================================
#  DAL 抽象基类
# ============================================================

class DALBase(ABC):
    """数据访问层基类 — 所有底层实现需实现以下方法"""

    @abstractmethod
    def get_poem_by_id(self, poem_id: str) -> Optional[PoemData]:
        ...

    @abstractmethod
    def get_poems_by_author(self, author_id: str) -> List[PoemData]:
        ...

    @abstractmethod
    def get_author(self, author_id: str) -> Optional[AuthorData]:
        ...

    @abstractmethod
    def get_dynasty(self, dynasty_id: str) -> Optional[DynastyData]:
        ...

    @abstractmethod
    def get_dynasties(self) -> List[DynastyData]:
        ...

    @abstractmethod
    def get_authors_by_dynasty(self, dynasty_id: str) -> List[AuthorData]:
        ...

    @abstractmethod
    def get_poem_tags(self, poem_id: str) -> List[TagData]:
        ...

    @abstractmethod
    def get_related_poems_by_tags(self, poem_id: str, limit: int = 10) -> List[dict]:
        """通过标签 Jaccard 相似度找相关诗词"""
        ...

    @abstractmethod
    def get_poems_by_tags(self, category: str, labels: List[str],
                          match_all: bool = False) -> List[PoemData]:
        ...

    @abstractmethod
    def get_poet_portrait_data(self, author_id: str) -> Dict:
        """诗人标签聚合统计"""
        ...

    @abstractmethod
    def search_poems(self, keyword: str, limit: int = 50) -> List[dict]:
        ...

    @abstractmethod
    def get_stats(self) -> Dict:
        ...

    @abstractmethod
    def get_all_vocab(self) -> List[dict]:
        ...

    @abstractmethod
    def get_vocab_by_category(self, category: str) -> List[dict]:
        ...

    @abstractmethod
    def get_poem_full_detail(self, poem_id: str) -> Optional[PoemData]:
        """诗词详情（含作者名、朝代名、标签列表）"""
        ...


# ============================================================
#  SQLite 实现（当前后端）
# ============================================================

class SQLiteDAL(DALBase):
    """
    SQLite 实现 — 使用 raw sqlite3。
    支持两种初始化方式：
      1. db_path: 独立脚本使用
      2. db_session: Flask / SQLAlchemy 环境中使用
    """

    def __init__(self, db_path: Optional[str] = None,
                 db_session=None):
        if db_session is not None:
            # Flask 环境：复用已有 SQLAlchemy session
            self._session = db_session
            self._get_conn = self._conn_from_session
        else:
            # 独立环境：直接连接 SQLite 文件
            if db_path is None:
                db_path = str(Path(__file__).parent / "dataset" / "kbcp.db")
            self._db_path = db_path
            self._get_conn = self._conn_from_path

    def _conn_from_path(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _conn_from_session(self):
        """将 SQLAlchemy session 包装为 sqlite3 兼容接口"""
        # 返回原生 SQLite 连接
        return self._session.connection().connection

    def _fetchone(self, sql, params=None):
        conn = self._get_conn()
        try:
            cur = conn.execute(sql, params or ())
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            if not hasattr(self, '_session'):
                conn.close()

    def _fetchall(self, sql, params=None):
        conn = self._get_conn()
        try:
            cur = conn.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]
        finally:
            if not hasattr(self, '_session'):
                conn.close()

    # ---------- 基础查询 ----------

    def get_poem_by_id(self, poem_id: str) -> Optional[PoemData]:
        row = self._fetchone(
            "SELECT * FROM poem WHERE poem_id = ?", (poem_id,)
        )
        if not row:
            return None
        return PoemData(**row)

    def get_poems_by_author(self, author_id: str) -> List[PoemData]:
        rows = self._fetchall(
            "SELECT * FROM poem WHERE author_id = ? ORDER BY poem_id", (author_id,)
        )
        return [PoemData(**r) for r in rows]

    def get_author(self, author_id: str) -> Optional[AuthorData]:
        row = self._fetchone(
            "SELECT a.*, d.name AS dynasty_name "
            "FROM author a LEFT JOIN dynasty d ON a.dynasty_id = d.dynasty_id "
            "WHERE a.author_id = ?", (author_id,)
        )
        if not row:
            return None
        return AuthorData(**row)

    def get_dynasty(self, dynasty_id: str) -> Optional[DynastyData]:
        row = self._fetchone(
            "SELECT * FROM dynasty WHERE dynasty_id = ?", (dynasty_id,)
        )
        if not row:
            return None
        return DynastyData(**row)

    def get_dynasties(self) -> List[DynastyData]:
        rows = self._fetchall(
            "SELECT * FROM dynasty ORDER BY start_year"
        )
        return [DynastyData(**r) for r in rows]

    def get_authors_by_dynasty(self, dynasty_id: str) -> List[AuthorData]:
        rows = self._fetchall(
            "SELECT a.*, d.name AS dynasty_name "
            "FROM author a LEFT JOIN dynasty d ON a.dynasty_id = d.dynasty_id "
            "WHERE a.dynasty_id = ? ORDER BY a.author_id", (dynasty_id,)
        )
        return [AuthorData(**r) for r in rows]

    def get_poem_tags(self, poem_id: str) -> List[TagData]:
        rows = self._fetchall(
            "SELECT pt.*, v.label, v.category "
            "FROM poem_tag pt "
            "JOIN vocab v ON pt.vocab_id = v.vocab_id "
            "WHERE pt.poem_id = ?", (poem_id,)
        )
        return [TagData(**r) for r in rows]

    # ---------- 标签相关 ----------

    def get_related_poems_by_tags(self, poem_id: str,
                                  limit: int = 10) -> List[dict]:
        """Jaccard 相似度：标签交集 / 标签并集"""
        sql = """
            SELECT
                t.poem_id,
                p.title,
                a.name AS author_name,
                d.name AS dynasty_name,
                COUNT(DISTINCT t.vocab_id) AS common_tags,
                (
                    SELECT COUNT(DISTINCT pt2.vocab_id)
                    FROM poem_tag pt2
                    WHERE pt2.poem_id = t.poem_id
                ) + (
                    SELECT COUNT(DISTINCT pt3.vocab_id)
                    FROM poem_tag pt3
                    WHERE pt3.poem_id = ?
                ) - COUNT(DISTINCT t.vocab_id) AS union_tags,
                ROUND(1.0 * COUNT(DISTINCT t.vocab_id) / (
                    SELECT COUNT(DISTINCT pt2.vocab_id)
                    FROM poem_tag pt2
                    WHERE pt2.poem_id = t.poem_id
                ), 4) AS similarity
            FROM poem_tag t
            JOIN poem p ON t.poem_id = p.poem_id
            JOIN author a ON p.author_id = a.author_id
            JOIN dynasty d ON p.dynasty_id = d.dynasty_id
            WHERE t.vocab_id IN (
                SELECT vocab_id FROM poem_tag WHERE poem_id = ?
            )
            AND t.poem_id != ?
            GROUP BY t.poem_id
            HAVING union_tags > 0
            ORDER BY similarity DESC
            LIMIT ?
        """
        return self._fetchall(sql, (poem_id, poem_id, poem_id, limit))

    def get_poems_by_tags(self, category: str, labels: List[str],
                          match_all: bool = False) -> List[PoemData]:
        """按标签类别和标签名查找诗词"""
        if not labels:
            return []
        placeholders = ','.join('?' for _ in labels)
        having_clause = ("HAVING COUNT(DISTINCT v.label) = ?"
                         if match_all else "")
        params = [category, *labels]
        if match_all:
            params.append(len(labels))

        sql = f"""
            SELECT p.* FROM poem p
            JOIN poem_tag pt ON p.poem_id = pt.poem_id
            JOIN vocab v ON pt.vocab_id = v.vocab_id
            WHERE v.category = ? AND v.label IN ({placeholders})
            GROUP BY p.poem_id
            {having_clause}
            ORDER BY p.poem_id
        """
        rows = self._fetchall(sql, params)
        return [PoemData(**r) for r in rows]

    # ---------- 诗人画像 ----------

    def get_poet_portrait_data(self, author_id: str) -> Dict:
        """诗人维度：各类标签的分布统计"""
        # 标签聚合
        tags = self._fetchall("""
            SELECT v.category, v.label, COUNT(*) AS cnt
            FROM poem_tag pt
            JOIN vocab v ON pt.vocab_id = v.vocab_id
            JOIN poem p ON pt.poem_id = p.poem_id
            WHERE p.author_id = ?
            GROUP BY v.category, v.label
            ORDER BY v.category, cnt DESC
        """, (author_id,))

        # 诗人基本信息
        author = self.get_author(author_id)

        # 按 category 分组
        from collections import defaultdict
        grouped = defaultdict(list)
        for t in tags:
            grouped[t['category']].append({
                'label': t['label'],
                'count': t['cnt'],
            })

        # 总诗数
        total = self._fetchone(
            "SELECT COUNT(*) AS cnt FROM poem WHERE author_id = ?",
            (author_id,)
        )

        return {
            'author': author.to_dict() if author else {},
            'total_poems': total['cnt'] if total else 0,
            'tag_distribution': dict(grouped),
        }

    # ---------- 搜索与统计 ----------

    def search_poems(self, keyword: str, limit: int = 50) -> List[dict]:
        like = f'%{keyword}%'
        rows = self._fetchall("""
            SELECT p.poem_id, p.title, a.name AS author_name,
                   d.name AS dynasty_name
            FROM poem p
            LEFT JOIN author a ON p.author_id = a.author_id
            LEFT JOIN dynasty d ON p.dynasty_id = d.dynasty_id
            WHERE p.title LIKE ? OR p.content LIKE ?
            LIMIT ?
        """, (like, like, limit))
        return rows

    def get_stats(self) -> Dict:
        return {
            'dynasty_count': self._fetchone(
                "SELECT COUNT(*) AS c FROM dynasty")['c'],
            'author_count': self._fetchone(
                "SELECT COUNT(*) AS c FROM author")['c'],
            'poem_count': self._fetchone(
                "SELECT COUNT(*) AS c FROM poem")['c'],
            'vocab_count': self._fetchone(
                "SELECT COUNT(*) AS c FROM vocab")['c'],
            'tag_count': self._fetchone(
                "SELECT COUNT(*) AS c FROM poem_tag")['c'],
        }

    def get_all_vocab(self) -> List[dict]:
        return self._fetchall(
            "SELECT * FROM vocab ORDER BY category, sort_order"
        )

    def get_vocab_by_category(self, category: str) -> List[dict]:
        return self._fetchall(
            "SELECT * FROM vocab WHERE category = ? ORDER BY sort_order",
            (category,)
        )

    # ---------- 组合查询 ----------

    def get_poem_full_detail(self, poem_id: str) -> Optional[PoemData]:
        poem = self.get_poem_by_id(poem_id)
        if not poem:
            return None

        # 填充关联信息
        author = self.get_author(poem.author_id)
        dynasty = self.get_dynasty(poem.dynasty_id)
        tags = self.get_poem_tags(poem_id)

        poem.author_name = author.name if author else ''
        poem.dynasty_name = dynasty.name if dynasty else ''
        poem.tags = [t.to_dict() for t in tags]
        return poem

    # ---------- 新增：按名称/别名检索（供 SQLAssist 使用） ----------

    def get_author_by_name(self, name: str) -> Optional[AuthorData]:
        """按标准名精确查作者"""
        row = self._fetchone(
            "SELECT a.*, d.name AS dynasty_name "
            "FROM author a LEFT JOIN dynasty d ON a.dynasty_id = d.dynasty_id "
            "WHERE a.name = ?", (name,)
        )
        if not row:
            return None
        return AuthorData(**row)

    def get_author_by_alias(self, alias: str) -> List[AuthorData]:
        """按别名模糊查作者（匹配 other_names/courtesy_name/art_name）"""
        like = f'%{alias}%'
        rows = self._fetchall(
            "SELECT a.*, d.name AS dynasty_name "
            "FROM author a LEFT JOIN dynasty d ON a.dynasty_id = d.dynasty_id "
            "WHERE a.name LIKE ? OR a.courtesy_name LIKE ? "
            "   OR a.art_name LIKE ? OR a.other_names LIKE ? "
            "LIMIT 10",
            (like, like, like, like)
        )
        return [AuthorData(**r) for r in rows]

    def get_poems_by_title(self, title: str) -> List[PoemData]:
        """按标题精确查诗词"""
        rows = self._fetchall(
            "SELECT p.*, a.name AS author_name, d.name AS dynasty_name "
            "FROM poem p "
            "LEFT JOIN author a ON p.author_id = a.author_id "
            "LEFT JOIN dynasty d ON p.dynasty_id = d.dynasty_id "
            "WHERE p.title = ? ORDER BY p.poem_id", (title,)
        )
        return [PoemData(**r) for r in rows]

    def search_poems_exact(self, content: str, limit: int = 5) -> List[dict]:
        """精确匹配诗句内容（用于 FIND_POEM 查询）"""
        like = f'%{content}%'
        rows = self._fetchall(
            "SELECT p.poem_id, p.title, p.content, "
            "       a.name AS author_name, d.name AS dynasty_name "
            "FROM poem p "
            "LEFT JOIN author a ON p.author_id = a.author_id "
            "LEFT JOIN dynasty d ON p.dynasty_id = d.dynasty_id "
            "WHERE p.content LIKE ? "
            "LIMIT ?", (like, limit)
        )
        return rows

    def get_schema_metadata(self) -> List[dict]:
        """读取 myschema 表的所有记录"""
        return self._fetchall(
            "SELECT * FROM myschema ORDER BY table_name, column_label"
        )

    def execute_readonly_sql(self, sql: str, params: tuple = None,
                             max_rows: int = 100) -> dict:
        """
        安全的只读 SQL 执行沙箱。
        仅允许 SELECT，禁止任何写操作。
        返回: {"success": bool, "columns": [...], "rows": [...], "error": str}
        """
        sql_strip = sql.strip().upper()
        if not sql_strip.startswith('SELECT'):
            return {"success": False, "error": "只允许 SELECT 查询"}

        conn = self._get_conn()
        try:
            cur = conn.execute(sql, params or ())
            col_names = [desc[0] for desc in cur.description]
            rows = [dict(r) for r in cur.fetchmany(max_rows)]
            return {"success": True, "columns": col_names,
                    "rows": rows, "error": None}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not hasattr(self, '_session'):
                conn.close()

    # ---------- 向量支持 ----------

    def get_poems_for_embedding(self, limit: Optional[int] = None,
                                offset: int = 0) -> List[dict]:
        """获取需要生成向量的诗词（优先用 sentences，回退到 content）"""
        sql = """
            SELECT p.poem_id, p.title, p.sentences, p.content,
                   a.name AS author_name, d.name AS dynasty_name
            FROM poem p
            LEFT JOIN author a ON p.author_id = a.author_id
            LEFT JOIN dynasty d ON p.dynasty_id = d.dynasty_id
            ORDER BY p.poem_id
        """
        if limit:
            sql += f" LIMIT {limit} OFFSET {offset}"
        return self._fetchall(sql)

    def save_embedding(self, poem_id: str, chunk_text: str,
                       embedding_bytes: bytes):
        """保存 Embedding 向量到 poem_embedding 表"""
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO poem_embedding "
                "(poem_id, chunk_text, embedding) VALUES (?, ?, ?)",
                (poem_id, chunk_text, embedding_bytes)
            )
            conn.commit()
        finally:
            if not hasattr(self, '_session'):
                conn.close()

    def ensure_embedding_table(self):
        """确保 poem_embedding 表存在"""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS poem_embedding (
                    poem_id   TEXT PRIMARY KEY,
                    chunk_text TEXT NOT NULL,
                    embedding BLOB,
                    created_at TEXT DEFAULT (datetime('now')),
                    FOREIGN KEY (poem_id) REFERENCES poem(poem_id)
                )
            """)
            conn.commit()
        finally:
            if not hasattr(self, '_session'):
                conn.close()
