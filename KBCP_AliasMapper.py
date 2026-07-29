# -*- coding: utf-8 -*-
"""
KBCP_AliasMapper.py - 别名映射引擎
===================================
将用户输入中的别名/异名/字号映射为标准名称。
在 KBCP 中新架构中用于所有查询路径的第一步。

使用方式:
    mapper = AliasMapper()
    mapper.build_index()
    result = mapper.resolve("子瞻")
    # -> {"original": "子瞻", "resolved": "苏轼",
    #     "matches": [("子瞻", "苏轼", "author", "A00123")]}
"""
import re
from typing import Dict, List, Optional, Tuple
from KBCP_DAL import SQLiteDAL


class AliasMapper:
    """别名映射引擎（单例），全局只需一个实例"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._dal = SQLiteDAL()
        # {alias_lower: (standard_name, entity_type, entity_id)}
        self._alias_map: Dict[str, Tuple[str, str, str]] = {}
        self._loaded = False

    # ------------------------------------------------------------
    #  构建索引
    # ------------------------------------------------------------

    def build_index(self):
        """从数据库加载所有别名，构建 {输入} → {标准名} 映射"""
        self._alias_map.clear()

        # --- 1. 诗人: name + courtesy_name(字) + art_name(号) + other_names(别名) ---
        authors = self._dal._fetchall(
            "SELECT author_id, name, courtesy_name, art_name, other_names "
            "FROM author"
        )
        for a in authors:
            aid, std = a['author_id'], a['name']
            self._add_alias(std, 'author', aid)                     # 标准名
            for fld in ('courtesy_name', 'art_name', 'other_names'):
                val = a.get(fld, '') or ''
                for alias in self._split(val):
                    self._add_alias(alias, 'author', aid, std)

        # --- 2. 诗词: title + aliases(别名) ---
        poems = self._dal._fetchall(
            "SELECT poem_id, title, aliases FROM poem "
            "WHERE aliases IS NOT NULL AND aliases != ''"
        )
        for p in poems:
            pid, std = p['poem_id'], p['title']
            self._add_alias(std, 'poem', pid)
            for alias in self._split(p.get('aliases', '')):
                self._add_alias(alias, 'poem', pid, std)

        # --- 3. 朝代: name + another_name(别名) ---
        dynasties = self._dal._fetchall(
            "SELECT dynasty_id, name, another_name FROM dynasty "
            "WHERE another_name IS NOT NULL AND another_name != ''"
        )
        for d in dynasties:
            did, std = d['dynasty_id'], d['name']
            self._add_alias(std, 'dynasty', did)
            for alias in self._split(d.get('another_name', '')):
                self._add_alias(alias, 'dynasty', did, std)

        self._loaded = True

    def _add_alias(self, alias: str, entity_type: str,
                   entity_id: str, standard: str = None):
        """注册一个别名映射（首次注册优先，不覆盖已有映射）"""
        alias = alias.strip()
        if not alias:
            return
        key = alias.lower()
        if key in self._alias_map:
            return  # 保留首次注册的标准名
        self._alias_map[key] = (standard or alias, entity_type, entity_id)

    @staticmethod
    def _split(text: str) -> List[str]:
        """分割逗号/分号/空格/顿号分隔的别名列表"""
        return [p.strip() for p in re.split(r'[,;，；、\s]+', text) if p.strip()]

    # ------------------------------------------------------------
    #  解析入口
    # ------------------------------------------------------------

    def resolve(self, text: str) -> dict:
        """
        解析输入文本，返回映射结果。

        返回:
            original  : 原始输入
            resolved  : 别名被替换后的文本
            matches   : [(原始词, 标准名, 实体类型, 实体ID), ...]
        """
        if not self._loaded:
            self.build_index()

        matches = []

        # (1) 全句精准匹配
        key = text.strip().lower()
        if key in self._alias_map:
            std, etype, eid = self._alias_map[key]
            matches.append((text, std, etype, eid))
            return dict(original=text, resolved=std,
                        matches=matches)

        # (2) 提取《》中的内容匹配
        for m in re.finditer(r'《([^》]+)》', text):
            name = m.group(1).strip()
            key = name.lower()
            if key in self._alias_map:
                std, etype, eid = self._alias_map[key]
                matches.append((name, std, etype, eid))

        # (3) 分词匹配
        if not matches:
            for token in re.split(r'[\s,，。！？、；：""''（）()《》]+', text):
                token = token.strip()
                if token and token.lower() in self._alias_map:
                    std, etype, eid = self._alias_map[token.lower()]
                    matches.append((token, std, etype, eid))

        # 替换原文中的别名为标准名
        resolved = text
        for orig, std, _, _ in matches:
            resolved = resolved.replace(orig, std)

        return dict(original=text, resolved=resolved,
                    matches=matches)

    def find_entity(self, text: str) -> Optional[dict]:
        """
        快捷方法：返回匹配到的第一个实体信息。
        用于 QueryClassifier 判断用户问题涉及哪个实体。
        """
        result = self.resolve(text)
        if result['matches']:
            _, std, etype, eid = result['matches'][0]
            return dict(standard_name=std, entity_type=etype, entity_id=eid)
        return None
