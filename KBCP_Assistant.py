# -*- coding: utf-8 -*-
"""
KBCP_Assistant.py - 智能诗词问答助手 v4 (混合架构)
===================================================
混合流程：
  1. 别名映射（AliasMapper）
  2. 查询分类（QueryClassifier）
  3. 路由分发：
     - ENTITY_AUTHOR/POEM       → 直接 SQL 查 DB → ResultFormatter
     - FIND_POEM                → search_poems_exact → ResultFormatter
     - STATS/TAG_BASED/COMPARE  → SQLAssist（LLM 生成 SQL）
     - ANALYTICAL               → RAGIndex 检索 → LLM 分析回答

不再使用纯向量检索作为主路径。
"""
import re
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from KBCP_DAL import SQLiteDAL
from KBCP_LLM_Provider import load_config, create_provider
from KBCP_RAG_Index import RAGIndex
from KBCP_AliasMapper import AliasMapper
from KBCP_QueryClassifier import QueryClassifier, QueryType
from KBCP_ResultFormatter import (
    format_author_info, format_poem_list, format_poem_detail,
    format_empty, format_error,
)
from KBCP_SQLAssist import SQLAssist
from KBCP_Agent import run_agent, get_near_synonym_flag


# ============================================================
#  全局单例
# ============================================================

_dal = None
_index = None
_alias_mapper = None
_classifier = None
_sql_assist = None


def _get_dal():
    global _dal
    if _dal is None:
        _dal = SQLiteDAL()
    return _dal


def get_index():
    global _index
    if _index is None:
        _index = RAGIndex()
    return _index


def get_mapper():
    global _alias_mapper
    if _alias_mapper is None:
        _alias_mapper = AliasMapper()
    return _alias_mapper


def get_classifier():
    global _classifier
    if _classifier is None:
        _classifier = QueryClassifier()
    return _classifier


def get_sql_assist():
    global _sql_assist
    if _sql_assist is None:
        _sql_assist = SQLAssist()
    return _sql_assist


def warmup():
    """预热所有组件（Web 启动时调用一次）"""
    t0 = time.time()
    print("[Assistant] 预热 RAG 索引...")
    get_index().warmup()
    print("[Assistant] 加载别名映射...")
    get_mapper().build_index()
    print(f"[Assistant] 预热完成，用时 {time.time() - t0:.1f}s")


# ============================================================
#  AI 分析路径（保留原有的 RAG + LLM 能力）
# ============================================================

SYSTEM_PROMPT = """你是一位精通中华诗词的专家。请根据提供的检索结果回答用户的问题。

要求：
1. 只使用检索结果中的信息，不要编造事实
2. 回答要自然流畅、有条理
3. 如果检索结果不足以回答，请如实说"检索结果中没有相关信息"
4. 回答时可引用诗词原文来佐证"""


def build_prompt(query: str, results) -> str:
    """构建带上下文的 Prompt（用于 ANALYTICAL 路径）"""
    if not results:
        return (
            f"{SYSTEM_PROMPT}\n\n"
            f"用户问题：{query}\n\n"
            f"未检索到相关信息，请如实告知用户。"
        )

    context_parts = []
    for i, r in enumerate(results, 1):
        ctx = r.to_context()
        if ctx:
            context_parts.append(f"[参考 {i}]\n{ctx}")

    context = '\n\n'.join(context_parts)
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"以下是检索到的相关信息：\n\n"
        f"{context}\n\n"
        f"用户问题：{query}"
    )


def retrieve(query: str, top_k: int = 5) -> list:
    """RAG 检索（用于 ANALYTICAL 路径）"""
    return get_index().search(query, top_k=top_k)


def answer_with_llm(prompt: str) -> str:
    """用配置的 LLM 生成回答（支持自动降级到下一个可用的 LLM）"""
    from KBCP_LLM_Provider import get_llm_priority_list

    config = load_config()
    providers = get_llm_priority_list(config)

    last_error = None
    for i, provider_name in enumerate(providers):
        try:
            provider = create_provider(provider_name, config)
            resp = provider.chat(prompt)
            if resp:
                return resp.strip()
            # chat 返回空（如 api_key 为空），记录并尝试下一个
            if last_error is None:
                last_error = f"LLM '{provider_name}' 返回为空"
            if i < len(providers) - 1:
                print(f"    [降级] {provider_name} 不可用，尝试下一个...")
        except Exception as e:
            last_error = f"LLM '{provider_name}' 调用失败: {e}"
            if i < len(providers) - 1:
                print(f"    [降级] {provider_name} 出错: {e}，尝试下一个...")
            continue

    # 所有 LLM 都不可用
    if last_error:
        return f"所有 LLM 均不可用，最后错误: {last_error}"
    return "所有 LLM 均返回空，请检查 KBCP_LLM_config.ini 配置。"


# ============================================================
#  各查询路径的处理函数
# ============================================================

def _handle_entity_author(query: str, alias_result: dict,
                          qtype_result) -> str:
    """ENTITY_AUTHOR: 查作者信息"""
    dal = _get_dal()

    # 尝试从别名映射中获取标准名
    std_name = ''
    if alias_result.get('matches'):
        for orig, std, etype, eid in alias_result['matches']:
            if etype == 'author':
                std_name = std
                break

    if not std_name:
        # 去掉疑问词后尝试直接匹配
        import re
        clean = re.sub(r'[是谁？\s介绍生平简介了解关于]', '', query).strip()
        if clean:
            std_name = clean

    # 查数据库
    author = dal.get_author_by_name(std_name) if std_name else None
    if not author and std_name:
        authors = dal.get_author_by_alias(std_name)
        if authors:
            author = authors[0]

    if not author:
        return format_empty(query, ['试试输入全名，如"李白"、"杜甫"'])

    return format_author_info(author.to_dict())


def _handle_entity_poem(query: str, alias_result: dict,
                        qtype_result) -> str:
    """ENTITY_POEM: 查作品信息"""
    dal = _get_dal()
    titles = []

    # 从《》中提取标题
    import re
    matches = re.findall(r'《([^》]+)》', query)
    if matches:
        titles = matches
    elif alias_result.get('matches'):
        for orig, std, etype, eid in alias_result['matches']:
            if etype == 'poem':
                titles.append(std)

    for title in titles:
        poems = dal.get_poems_by_title(title)
        if poems:
            return format_poem_detail(poems[0].to_dict())

    return format_empty(query, ['试试用《》括起诗词名，如《静夜思》'])


def _handle_find_poem(query: str, alias_result: dict,
                      qtype_result) -> str:
    """FIND_POEM: 找诗句出处"""
    dal = _get_dal()

    # 直接搜索诗句内容
    results = dal.search_poems_exact(query)

    if not results:
        # 试别名解析后的文本
        resolved = alias_result.get('resolved', query)
        if resolved != query:
            results = dal.search_poems_exact(resolved)

    if not results:
        return format_empty(query, ['试试输入完整的诗句'])

    return format_poem_list(results, title='诗句出处')


def _try_deterministic_count(query: str, alias_result: dict) -> Optional[str]:
    """
    确定性计数快路径。
    对"某作者有多少首诗"直接用 COUNT(*) 作答，不依赖 LLM，秒回且 100% 准确。
    仅当别名映射解析出 author 实体时生效。
    """
    author_name = None
    if alias_result.get('matches'):
        for orig, std, etype, eid in alias_result['matches']:
            if etype == 'author':
                author_name = std
                break

    if not author_name:
        # 尝试从问题中提取人名
        clean = re.sub(r'[收集收录有多少共写了创作了诗词作品几首几篇几阕？?，。、\s]',
                       '', query).strip()
        if clean:
            author_name = clean

    if not author_name:
        return None

    dal = _get_dal()
    # 先查 author 表确认存在
    author = dal.get_author_by_name(author_name)
    if not author:
        authors = dal.get_author_by_alias(author_name)
        if authors:
            author = authors[0]
            author_name = author.name
        else:
            return None

    row = dal._fetchone(
        "SELECT COUNT(*) AS c FROM poem WHERE author_id = ?",
        (author.author_id,)
    )
    cnt = row['c'] if row else 0
    return f"数据库中收录了「{author_name}」的诗词共 {cnt} 首。"


def _handle_stats(query: str, alias_result: dict,
                  qtype_result) -> str:
    """STATS: 先尝试确定性计数快路径，失败则走 SQLAssist"""
    det = _try_deterministic_count(query, alias_result)
    if det is not None:
        return det
    return _handle_sql_query(query, alias_result, qtype_result)


def _handle_sql_query(query: str, alias_result: dict,
                      qtype_result) -> str:
    """TAG_BASED / COMPARE / 复杂 STATS: 走 SQLAssist 路径（不再降级到 RAG）"""
    assist = get_sql_assist()
    qtype = qtype_result.type.value  # 'stats' / 'tag_based' / 'compare'

    result = assist.query(
        query=query,
        query_type=qtype,
        alias_info=alias_result,
    )

    if result.get('success'):
        return result['text']

    # SQL 路径失败：结构化/计数问题不应降级到 RAG（RAG 无法计数/比较）
    # 直接返回错误信息
    return result.get('text') or "无法生成查询 SQL，请换种方式描述问题。"


def _handle_rag(query: str, alias_result: dict = None,
                qtype_result=None) -> str:
    """ANALYTICAL: 走 RAG 检索 + LLM 分析"""
    results = retrieve(query)
    prompt = build_prompt(query, results)
    return answer_with_llm(prompt)


# ============================================================
#  路由表
# ============================================================

_HANDLERS = {
    QueryType.ENTITY_AUTHOR: _handle_entity_author,
    QueryType.ENTITY_POEM: _handle_entity_poem,
    QueryType.FIND_POEM: _handle_find_poem,
    QueryType.STATS: _handle_stats,            # 先走确定性 COUNT，再走 SQLAssist
    QueryType.TAG_BASED: _handle_sql_query,
    QueryType.COMPARE: _handle_sql_query,
    QueryType.ANALYTICAL: _handle_rag,
}


# ============================================================
#  统一问答入口
# ============================================================

# ------------------------------------------------------------
#  多轮对话上下文处理
# ------------------------------------------------------------

def _resolve_references(query: str, history: list = None) -> str:
    """
    指代消解：将"他""这首诗""还有呢"等替换为上文最近出现的实体。
    简单规则：如果本句没匹配到任何实体，且 history 中有上一个实体，则补全。
    """
    if not history:
        return query

    # 指代词检测
    pronoun_patterns = [
        (r'\b他\b', 'author'), (r'\b她\b', 'author'),
        (r'\b此[人诗作词篇]\b', 'author'), (r'\b这[首]\b', 'poem'),
        (r'\b那[首]\b', 'poem'),
        (r'\b还有呢\b', ''), (r'\b再说说\b', ''),
        (r'\b继续说\b', ''), (r'\b再\s*说说\b', ''),
    ]
    has_pronoun = any(re.search(p[0], query) for p in pronoun_patterns)

    # 检测当前 query 是否已包含明确实体
    mapper = get_mapper()
    alias_result = mapper.resolve(query)
    has_entity = bool(alias_result.get('matches'))

    if not has_pronoun and has_entity:
        return query  # 有明确实体，无需消解

    # 从 history 中提取最近出现的实体
    last_entity = None
    for entry in reversed(history):
        if 'entity' in entry and entry['entity']:
            last_entity = entry['entity']
            break

    if not last_entity:
        return query

    # 补全：将指代替换为最近实体
    # 简单处理：如果"他/她"出现在开头，替换为实体名
    import re as _re
    for pattern, etype in pronoun_patterns:
        query = _re.sub(pattern, last_entity, query)

    return query


def _extract_entity(alias_result: dict) -> str:
    """从别名映射结果中提取主要实体名"""
    if alias_result.get('matches'):
        for orig, std, etype, eid in alias_result['matches']:
            if etype in ('author', 'poem'):
                return std
    return ''


def answer_question(query: str, history: list = None,
                     llm_near_synonym: bool = None) -> str:
    """
    统一问答入口（智能化 Agent 版本）。

    流程：把问题交给 Agent 中枢，由 LLM 理解意图并调用合适的工具
    （KBCP_Tools）或 RAG 工具，最后用自然语言综合回答。

    参数:
        query: 用户当前问题
        history: 对话历史列表，每个元素为 {"q": str, "a": str, "entity": str}
                 用于多轮对话的指代消解和上下文记忆
        llm_near_synonym: 是否开启主题词近义理解。
                  None → 内部调用 get_near_synonym_flag() 自动判定
                  （Web 模式用 config.py，CLI 模式回退 ini）
    """
    if not query or not query.strip():
        return "请输入问题。"

    query = query.strip()
    t0 = time.time()

    # 近义理解开关：未显式传入则自动判定
    if llm_near_synonym is None:
        llm_near_synonym = get_near_synonym_flag()

    # 交给 Agent 中枢统一调度（答案本身不含计时标记，计时由调用方单独展示）
    answer = run_agent(query, history, llm_near_synonym)
    return answer


def _handle_rag_with_history(query: str, alias_result: dict,
                              qtype_result, history: list = None) -> str:
    """带历史上下文的 RAG 回答"""
    results = retrieve(query)

    # 构建历史上下文
    history_context = ''
    if history:
        lines = []
        for entry in history[-3:]:  # 最多取最近 3 轮
            lines.append(f"用户：{entry['q']}")
            lines.append(f"助手：{entry['a'][:200]}")
        if lines:
            history_context = '\n'.join(lines)

    prompt = build_prompt(query, results)

    # 如果有历史，注入到 system prompt 后
    if history_context:
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"以下是之前的对话历史（供参考）：\n{history_context}\n\n"
            f"{prompt.split('用户问题：')[0]}\n"
            f"用户问题：{query}"
        )

    return answer_with_llm(prompt)


# ============================================================
#  CLI 入口
# ============================================================

def interactive_mode():
    print("=" * 55)
    print("  KBCP 智能诗词助手 v4 (混合架构)")
    print("  输入问题，输入 q 退出")
    print("=" * 55)

    while True:
        try:
            q = input("\n❓ ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q.lower() in ('q', 'quit', 'exit'):
            break

        print("  [思考中...]")
        t0 = time.time()
        answer = answer_question(q)
        elapsed = time.time() - t0
        print(f"\n{answer}")
        print(f"⏱ {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="KBCP 智能诗词问答助手 v4 (混合架构)"
    )
    parser.add_argument('-q', '--question', default=None, help='单次问答')
    args = parser.parse_args()

    print("[信息] 预热中...")
    warmup()
    print("[信息] 预热完成，准备就绪\n")

    if args.question:
        t0 = time.time()
        answer = answer_question(args.question)
        elapsed = time.time() - t0
        print(answer)
        print(f"⏱ {elapsed:.1f}s")
    else:
        interactive_mode()


if __name__ == '__main__':
    main()
