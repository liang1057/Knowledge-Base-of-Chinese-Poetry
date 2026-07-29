# -*- coding: utf-8 -*-
"""
KBCP_QueryClassifier.py - 查询分类器
=====================================
规则驱动，将用户问题分类为不同查询类型。
分类后由 KBCP_Assistant 路由到对应的处理路径。

查询类型:
    ENTITY_AUTHOR  - 查诗人信息（李白是谁）
    ENTITY_POEM    - 查作品信息（静夜思）
    FIND_POEM      - 找诗句出处（床前明月光）
    STATS          - 统计/计数（多少首诗）
    TAG_BASED      - 主题/风格检索（描写秋天的诗）
    COMPARE        - 对比（李白和杜甫的区别）
    ANALYTICAL     - 主观分析（赏析、表达什么感情）
"""
import re
from enum import Enum


class QueryType(Enum):
    ENTITY_AUTHOR = 'entity_author'
    ENTITY_POEM = 'entity_poem'
    FIND_POEM = 'find_poem'
    STATS = 'stats'
    TAG_BASED = 'tag_based'
    COMPARE = 'compare'
    ANALYTICAL = 'analytical'


class QueryResult:
    """分类结果"""
    __slots__ = ('type', 'entities', 'raw_query')

    def __init__(self, qtype: QueryType, entities: list = None,
                 raw_query: str = ''):
        self.type = qtype
        self.entities = entities or []
        self.raw_query = raw_query

    def __repr__(self):
        return (f"QueryResult(type={self.type.value}, "
                f"entities={self.entities})")


class QueryClassifier:
    """规则驱动的查询分类器（无需 LLM 调用）"""

    def classify(self, query: str) -> QueryResult:
        """
        对用户输入进行分类。

        规则优先级从上到下，命中即返回。
        """
        q = query.strip()
        if not q:
            return QueryResult(QueryType.ANALYTICAL, raw_query=q)

        extracted = []

        # ---- 1. 统计类 ----
        if self._has_keywords(q, ['多少', '统计', '数量', '几首', '几篇',
                                   '最多', '最少', '总数', '共']):
            return QueryResult(QueryType.STATS, raw_query=q)

        # ---- 2. 对比类 ----
        if self._has_keywords(q, ['与', '和', 'vs', '对比', '区别',
                                   '不同', '差异', '比较']):
            # 尝试提取两个实体
            parts = re.split(r'[和与vsVS]', q)
            entities = [p.strip() for p in parts if p.strip()]
            if len(entities) >= 2:
                return QueryResult(QueryType.COMPARE, entities=entities[:2],
                                   raw_query=q)

        # ---- 3. 作者实体查询 ----
        if self._has_keywords(q, ['是谁', '是', '是谁?', '简介', '生平',
                                   '介绍', '了解', '关于']):
            # 提取人名
            names = self._extract_names(q)
            return QueryResult(QueryType.ENTITY_AUTHOR, entities=names,
                               raw_query=q)

        # ---- 4. 诗句出处查询 ----
        if self._is_poem_line(q):
            return QueryResult(QueryType.FIND_POEM, raw_query=q)

        # ---- 5. 作品查询 ----
        if '《' in q and '》' in q:
            titles = re.findall(r'《([^》]+)》', q)
            return QueryResult(QueryType.ENTITY_POEM, entities=titles,
                               raw_query=q)

        if self._has_keywords(q, ['这首诗', '那首诗', '作品', '诗作',
                                   '词作']):
            return QueryResult(QueryType.ENTITY_POEM, raw_query=q)

        # ---- 6. 主题/风格/标签检索 ----
        if self._has_keywords(q, ['什么主题', '关于', '描写', '主题',
                                   '风格', '类型', '类别', '季节',
                                   '情感', '意象', '体裁', '格律']):
            return QueryResult(QueryType.TAG_BASED, raw_query=q)

        # ---- 7. 默认：主观分析 ----
        return QueryResult(QueryType.ANALYTICAL, raw_query=q)

    # ------------------------------------------------------------
    #  辅助方法
    # ------------------------------------------------------------

    @staticmethod
    def _has_keywords(text: str, keywords: list) -> bool:
        """检查文本中是否包含任意关键词"""
        t = text.lower()
        return any(kw.lower() in t for kw in keywords)

    @staticmethod
    def _is_poem_line(text: str) -> bool:
        """
        判断是否为诗句（非标题，而是诗句原文）。
        规则：长度 > 8 且包含标点或明显是诗句特征。
        """
        t = text.strip()
        if len(t) < 5:
            return False
        # 含句号/逗号/问号等标点
        if re.search(r'[，。！？、；：\n]', t):
            return True
        # 五言/七言句式：5/7字且无书名号
        if '《' not in t and '》' not in t:
            clean = re.sub(r'[\s""'']', '', t)
            if len(clean) in (5, 7, 10, 14, 20, 21, 28):
                return True
        return False

    @staticmethod
    def _extract_names(text: str) -> list:
        """
        从文本中提取可能的人名。
        先看别名映射，再用简单规则。
        """
        # 先尝试从 KBCP_AliasMapper 查
        try:
            from KBCP_AliasMapper import AliasMapper
            mapper = AliasMapper()
            result = mapper.resolve(text)
            names = [m[1] for m in result['matches'] if m[2] == 'author']
            if names:
                return names
        except ImportError:
            pass

        # 简单回退：去掉关键词剩下的词
        q = re.sub(r'[是谁?？\s介绍生平简介了解关于]', '', text)
        return [q.strip()] if q.strip() else []
