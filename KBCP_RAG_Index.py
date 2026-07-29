# -*- coding: utf-8 -*-
"""
KBCP_RAG_Index.py - RAG 多源检索索引
=====================================
在内存中构建统一检索索引，覆盖 3 个来源：
  1. 诗词（从 poem_embedding 表读取预计算向量）
  2. 作者（利用 LIKE 语句实时搜索）
  3. 标签（语义匹配 VocabMatcher）

启动时预热加载，后续查询纯内存操作。

[新架构角色]
仅用于 ANALYTICAL（主观分析）查询路径。
结构化/实体类查询由 SQLAssist 路径处理。
"""
import time
import numpy as np
from pathlib import Path
from typing import List
from KBCP_DAL import SQLiteDAL


# ============================================================
#  检索结果对象
# ============================================================

class RAGResult:
    """单条检索结果"""
    __slots__ = ('type', 'score', 'title', 'author_name',
                 'dynasty_name', 'content', 'appreciation',
                 'bio', 'historical_role', 'tag_category', 'tag_label')

    def __init__(self, **kwargs):
        for k in self.__slots__:
            setattr(self, k, kwargs.get(k, ''))

    def to_context(self) -> str:
        """转为 LLM Prompt 中的上下文片段"""
        if self.type == 'author':
            parts = [f"[作者] {self.title}"]
            if self.dynasty_name:
                parts.append(f"朝代：{self.dynasty_name}")
            if self.bio:
                parts.append(f"生平：{self.bio[:500]}")
            if self.historical_role:
                parts.append(f"文学史定位：{self.historical_role[:200]}")
            return '\n'.join(parts)

        elif self.type == 'poem':
            parts = [f"[诗词] {self.author_name}《{self.title}》"]
            if self.content:
                parts.append(f"正文：{self.content[:600]}")
            if self.appreciation:
                parts.append(f"赏析：{self.appreciation[:400]}")
            return '\n'.join(parts)

        elif self.type == 'tag':
            return f"[标签] {self.tag_category}: {self.tag_label}"
        return ''


# ============================================================
#  检索索引
# ============================================================

class RAGIndex:
    """
    多源检索索引。
    使用方式：
        index = RAGIndex()
        index.warmup()              # 预热（启动后调用一次）
        results = index.search(query)  # 检索
    """

    def __init__(self):
        self._dal = None
        self._warm = False

    def _get_dal(self):
        if self._dal is None:
            self._dal = SQLiteDAL()
        return self._dal

    # ---------- 检索方法 ----------

    def search(self, query: str, top_k: int = 5) -> List[RAGResult]:
        """
        多源检索主入口。
        并行搜索诗词、作者、标签，合并后取 top_k。
        """
        results = []

        # 1. 诗词语义检索（poem_embedding）
        try:
            poem_results = self._search_poems(query, top_k=3)
            results.extend(poem_results)
        except Exception as e:
            print(f"  [RAG] 诗词检索失败: {e}")

        # 2. 作者检索（LIKE 匹配）
        try:
            author_results = self._search_authors(query, top_k=2)
            results.extend(author_results)
        except Exception as e:
            print(f"  [RAG] 作者检索失败: {e}")

        # 3. 标签语义匹配
        try:
            tag_results = self._search_tags(query, top_k=2)
            results.extend(tag_results)
        except Exception as e:
            print(f"  [RAG] 标签检索失败: {e}")

        # 按分数降序，去重（同一 poem_id 只保留一次）
        results.sort(key=lambda x: -x.score)
        seen = set()
        unique = []
        for r in results:
            key = (r.type, r.title)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique[:top_k]

    def semantic_search(self, query: str, top_k: int = 5) -> List[dict]:
        """
        语义检索的 Agent 工具入口：在 search() 基础上，把 RAGResult 转为
        结构化 dict 列表，便于 LLM 直接阅读与综合。
        """
        results = self.search(query, top_k=top_k)
        out = []
        for r in results:
            out.append({
                "type": r.type,
                "score": round(r.score, 4),
                "title": r.title,
                "author_name": r.author_name,
                "dynasty_name": r.dynasty_name,
                "content": r.content,
                "appreciation": r.appreciation,
                "bio": r.bio,
                "historical_role": r.historical_role,
                "tag_category": r.tag_category,
                "tag_label": r.tag_label,
            })
        return out

    # ---------- 诗词检索 ----------

    def _search_poems(self, query: str, top_k: int) -> List[RAGResult]:
        """用 embedding 向量检索诗词"""
        dal = self._get_dal()
        vec = self._encode(query)
        if vec is None:
            return []

        rows = dal._fetchall("""
            SELECT e.poem_id, e.chunk_text, e.embedding,
                   p.title, p.content, p.appreciation,
                   a.name AS author_name, d.name AS dynasty_name
            FROM poem_embedding e
            JOIN poem p ON e.poem_id = p.poem_id
            LEFT JOIN author a ON p.author_id = a.author_id
            LEFT JOIN dynasty d ON p.dynasty_id = d.dynasty_id
        """)

        scored = []
        for r in rows:
            emb_bytes = r.get('embedding')
            if not emb_bytes:
                continue
            try:
                emb_vec = np.frombuffer(emb_bytes, dtype=np.float32)
                dot = np.dot(vec, emb_vec)
                norm = np.linalg.norm(vec) * np.linalg.norm(emb_vec)
                sim = dot / norm if norm > 0 else 0
                scored.append((sim, r))
            except Exception:
                continue

        scored.sort(key=lambda x: -x[0])
        results = []
        for sim, r in scored[:top_k]:
            results.append(RAGResult(
                type='poem',
                score=float(sim),
                title=r['title'] or '',
                author_name=r['author_name'] or '',
                dynasty_name=r['dynasty_name'] or '',
                content=r['content'] or '',
                appreciation=r['appreciation'] or '',
            ))
        return results

    # ---------- 作者检索 ----------

    def _search_authors(self, query: str, top_k: int) -> List[RAGResult]:
        """通过 LIKE 语句检索作者生平"""
        dal = self._get_dal()
        like = f'%{query}%'
        rows = dal._fetchall("""
            SELECT a.name, a.bio, a.historical_role,
                   d.name AS dynasty_name
            FROM author a
            LEFT JOIN dynasty d ON a.dynasty_id = d.dynasty_id
            WHERE a.name LIKE ? OR a.bio LIKE ?
               OR a.birth_place LIKE ? OR a.historical_role LIKE ?
            LIMIT ?
        """, (like, like, like, like, top_k))

        results = []
        for r in rows:
            results.append(RAGResult(
                type='author',
                score=0.9,  # 精确匹配高优先级
                title=r['name'] or '',
                dynasty_name=r['dynasty_name'] or '',
                bio=r['bio'] or '',
                historical_role=r['historical_role'] or '',
            ))
        return results

    # ---------- 标签检索 ----------

    def _search_tags(self, query: str, top_k: int) -> List[RAGResult]:
        """用 VocabLabelMatcher 做标签语义匹配"""
        matcher = VocabLabelMatcher.get_instance()
        matches = matcher.match(query, top_k=top_k)
        results = []
        for cat, label, score in matches:
            results.append(RAGResult(
                type='tag',
                score=float(score),
                tag_category=cat,
                tag_label=label,
                title=f"{cat}:{label}",
            ))
        return results

    # ---------- 向量化 ----------

    _model = None

    def _encode(self, text: str):
        """用本地模型将文本转为向量"""
        if RAGIndex._model is None:
            model_path = Path(__file__).parent / 'models' / 'paraphrase-multilingual-MiniLM'
            if model_path.is_dir():
                try:
                    from sentence_transformers import SentenceTransformer
                    RAGIndex._model = SentenceTransformer(str(model_path))
                except Exception:
                    return None
            else:
                return None

        try:
            vec = RAGIndex._model.encode([text], show_progress_bar=False)[0]
            return vec.astype(np.float32)
        except Exception:
            return None

    # ---------- 预热 ----------

    def warmup(self):
        """预热：确保 poem_embedding 表有数据，模型加载到内存"""
        if self._warm:
            return
        t0 = time.time()

        dal = self._get_dal()
        count = dal._fetchone(
            "SELECT COUNT(*) AS c FROM poem_embedding"
        )
        print(f"  [RAG] poem_embedding 表: {count['c'] if count else 0} 条")

        # 加载模型
        model_path = Path(__file__).parent / 'models' / 'paraphrase-multilingual-MiniLM'
        if model_path.is_dir():
            from sentence_transformers import SentenceTransformer
            RAGIndex._model = SentenceTransformer(str(model_path))
            print(f"  [RAG] 模型加载完成")

        self._warm = True
        print(f"  [RAG] 预热完成，用时 {time.time() - t0:.1f}s")


# ============================================================
#  标签语义匹配器（供 _search_tags 使用）
# ============================================================

class VocabLabelMatcher:
    """用本地模型将用户查询与 vocab 标签做语义相似度匹配"""

    _instance = None
    _model = None
    _label_vectors = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if VocabLabelMatcher._label_vectors is not None:
            return
        self._build_index()

    def _build_index(self):
        """读取 vocab 表，预计算所有标签的向量"""
        dal = SQLiteDAL()
        labels = dal._fetchall(
            "SELECT category, label FROM vocab ORDER BY category"
        )
        if not labels:
            VocabLabelMatcher._label_vectors = []
            return

        texts = [f"{r['label']}" for r in labels]
        model = RAGIndex._model
        if model is not None:
            vectors = model.encode(texts, show_progress_bar=False)
            VocabLabelMatcher._label_vectors = [
                (r['category'], r['label'],
                 vectors[i].astype(np.float32))
                for i, r in enumerate(labels)
            ]
        else:
            VocabLabelMatcher._label_vectors = [
                (r['category'], r['label'], None) for r in labels
            ]

    def match(self, query: str, threshold: float = 0.5,
              top_k: int = 5):
        """语义匹配：将 query 与所有标签向量计算余弦相似度"""
        if not VocabLabelMatcher._label_vectors:
            return []

        model = RAGIndex._model
        if model is None:
            return []

        vec = model.encode([query], show_progress_bar=False)[0]
        vec = vec.astype(np.float32)

        results = []
        for cat, label, lvec in VocabLabelMatcher._label_vectors:
            if lvec is None:
                continue
            dot = np.dot(vec, lvec)
            norm = np.linalg.norm(vec) * np.linalg.norm(lvec)
            sim = float(dot / norm) if norm > 0 else 0
            if sim >= threshold:
                results.append((cat, label, sim))

        results.sort(key=lambda x: -x[2])
        return results[:top_k]
