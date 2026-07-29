# -*- coding: utf-8 -*-
"""
KBCP_ResultFormatter.py - 结果格式化
=====================================
将 SQL 检索结果或 RAG 上下文格式化为自然语言文本。
用于 KBCP_Assistant 的各个处理路径，统一输出风格。
"""
from typing import List, Dict, Optional


def format_author_info(author: dict) -> str:
    """格式化作者信息"""
    parts = [f"【{author.get('name', '')}】"]
    dynasty = author.get('dynasty_name', '')
    if dynasty:
        parts[0] += f"（{dynasty}）"

    # 字号
    alias_parts = []
    for k, label in [('courtesy_name', '字'), ('art_name', '号')]:
        v = author.get(k, '') or ''
        if v:
            alias_parts.append(f"{label}{v}")
    other = author.get('other_names', '') or ''
    if other:
        alias_parts.append(f"别名{other}")
    if alias_parts:
        parts.append('，'.join(alias_parts))

    # 生卒年
    by = author.get('birth_year') or ''
    dy = author.get('death_year') or ''
    if by or dy:
        years = f"{by}—{dy}" if by and dy else (by or dy)
        parts.append(f"生卒年：{years}")

    # 籍贯
    bp = author.get('birth_place', '') or ''
    if bp:
        parts.append(f"籍贯：{bp}")

    # 生平简介
    bio = author.get('bio', '') or ''
    if bio:
        parts.append(f"\n{bio[:600]}")

    # 文学史定位
    role = author.get('historical_role', '') or ''
    if role:
        parts.append(f"\n文学史定位：{role[:300]}")

    return '\n'.join(parts)


def format_poem_list(poems: List[dict], title: str = '') -> str:
    """格式化诗词列表"""
    if not poems:
        return '未找到相关诗词。'

    lines = [f"共找到 {len(poems)} 首诗词："]
    for i, p in enumerate(poems, 1):
        author = p.get('author_name', '') or ''
        dynasty = p.get('dynasty_name', '') or ''
        title = p.get('title', '') or ''
        # 首句
        content = p.get('content', '') or ''
        first_line = content.split('\n')[0][:30] if content else ''
        lines.append(f"  {i}. 《{title}》—{author}（{dynasty}）{first_line}")

    return '\n'.join(lines)


def format_poem_detail(poem: dict) -> str:
    """格式化单首诗词详情"""
    title = poem.get('title', '') or ''
    author = poem.get('author_name', '') or ''
    dynasty = poem.get('dynasty_name', '') or ''
    content = poem.get('content', '') or ''
    appreciation = poem.get('appreciation', '') or ''
    translation = poem.get('translation', '') or ''

    parts = [f"《{title}》—{author}（{dynasty}）", '', content]
    if translation:
        parts.extend(['', f"【译文】{translation[:400]}"])
    if appreciation:
        parts.extend(['', f"【赏析】{appreciation[:500]}"])

    return '\n'.join(parts)


def format_stat_result(result: dict) -> str:
    """格式化统计结果"""
    label = result.get('label', '')
    count = result.get('count', 0)
    detail = result.get('detail', '')
    if detail:
        return f"{label}：{count} 条。{detail}"
    return f"{label}：共 {count} 条。"


def format_tag_based(poems: List[dict], tags: list) -> str:
    """格式化标签检索结果"""
    tag_str = '、'.join(tags) if tags else ''
    header = f"以下是与「{tag_str}」相关的诗词："
    return header + '\n' + format_poem_list(poems).split('\n', 1)[-1]


def format_empty(query: str, suggestions: list = None) -> str:
    """格式化空结果"""
    msg = f"没有找到与「{query}」相关的信息。"
    if suggestions:
        msg += f"\n建议尝试：{'；'.join(suggestions)}"
    return msg


def format_error(query: str, error: str) -> str:
    """格式化错误信息"""
    return f"查询「{query}」时出错：{error}\n请尝试换个方式提问。"


def format_compare(left: dict, right: dict, common_tags: list = None,
                   diff_tags: list = None) -> str:
    """格式化对比结果"""
    lines = [f"【{left.get('name', '')} vs {right.get('name', '')}】"]

    if common_tags:
        lines.append(f"\n共同特点（{len(common_tags)}项）：{'、'.join(common_tags[:10])}")

    if diff_tags:
        lines.append(f"\n差异：")
        for d in diff_tags:
            lines.append(f"  · {d.get('left', '')} ←→ {d.get('right', '')}")

    return '\n'.join(lines)
