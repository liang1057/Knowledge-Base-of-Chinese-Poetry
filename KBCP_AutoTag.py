# -*- coding: utf-8 -*-
"""
KBCP_AutoTag.py - 智能诗词打标签工具 v1.0
功能:
  1. 遍历诗词，调用本地 Ollama 大模型自动打标签
  2. 标签映射到 KBCP 受控词表 (vocab)，写入 poem_tag 中间表
  3. 支持断点续传、增量分析、限速等
"""

import re
import json
import time
import sqlite3
import argparse
import requests
from datetime import datetime
from pathlib import Path
from KBCP_LLM_Provider import load_config, create_provider, DEFAULT_CONFIG_PATH


# ==================== 配置 ====================

# 数据库路径
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "dataset" / "kbcp.db"

# AI 打标的标签类别（不包含 genre/form/review_status 等已有默认值的）
TAG_CATEGORIES = ["theme", "style", "emotion", "imagery", "season", "festival", "allusion"]

# 以下默认值可通过 KBCP_LLM_config.ini 的 [common] 段覆盖
DEFAULT_REQUEST_INTERVAL = 0.5
DEFAULT_MAX_CONTENT_LEN = 600

# 运行时参数（由 main 从 config 加载后覆盖）
REQUEST_INTERVAL = DEFAULT_REQUEST_INTERVAL
MAX_CONTENT_LEN = DEFAULT_MAX_CONTENT_LEN

# 失败重试
MAX_RETRIES = 3
RETRY_DELAY = 5

# 是否保留已有标签（True=跳过已打标类别，False=覆盖）
SKIP_EXISTING = True


# ==================== 数据库操作 ====================

def get_conn():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_log_table():
    """初始化分析日志表"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS auto_tag_log (
            poem_id    TEXT PRIMARY KEY,
            analyzed_at TEXT NOT NULL,
            model      TEXT NOT NULL,
            tag_count  INTEGER DEFAULT 0,
            status     TEXT DEFAULT 'ok'
        );
    """)
    conn.commit()
    conn.close()


def load_vocab():
    """从数据库加载所有受控词条，返回 {category: [{vocab_id, label}, ...]}"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT vocab_id, category, label FROM vocab ORDER BY category, sort_order"
    ).fetchall()
    conn.close()

    vocab = {}
    for r in rows:
        cat = r["category"]
        if cat not in vocab:
            vocab[cat] = []
        vocab[cat].append({"vocab_id": r["vocab_id"], "label": r["label"]})
    return vocab


def query_vocab_id(category, label):
    """根据类别+标签名查找 vocab_id，找不到返回 None"""
    conn = get_conn()
    row = conn.execute(
        "SELECT vocab_id FROM vocab WHERE category = ? AND label = ?",
        (category, label)
    ).fetchone()
    conn.close()
    return row["vocab_id"] if row else None


def get_poems_missing_tags(limit=None, category=None):
    """获取缺少指定类别标签的诗（增量模式）"""
    conn = get_conn()
    if category:
        sql = """
            SELECT p.poem_id, p.title, p.content, a.name AS author_name
            FROM poem p
            JOIN author a ON p.author_id = a.author_id
            LEFT JOIN poem_tag pt ON p.poem_id = pt.poem_id AND pt.tag_type = ?
            LEFT JOIN auto_tag_log tl ON p.poem_id = tl.poem_id
            WHERE pt.poem_id IS NULL AND tl.poem_id IS NULL
            ORDER BY p.poem_id
        """
        params = (category,)
    else:
        sql = """
            SELECT p.poem_id, p.title, p.content, a.name AS author_name
            FROM poem p
            JOIN author a ON p.author_id = a.author_id
            LEFT JOIN auto_tag_log tl ON p.poem_id = tl.poem_id
            WHERE tl.poem_id IS NULL
            ORDER BY p.poem_id
        """
        params = ()

    if limit:
        sql += " LIMIT ?"
        params = params + (limit,)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_unanalyzed_poems(limit=None):
    """获取所有未分析的诗（不切割类别）"""
    conn = get_conn()
    sql = """
        SELECT p.poem_id, p.title, p.content, a.name AS author_name
        FROM poem p
        JOIN author a ON p.author_id = a.author_id
        LEFT JOIN auto_tag_log tl ON p.poem_id = tl.poem_id
        WHERE tl.poem_id IS NULL
        ORDER BY p.poem_id
    """
    if limit:
        sql += " LIMIT ?"
        rows = conn.execute(sql, (limit,) if limit else ()).fetchall()
    else:
        rows = conn.execute(sql).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    """获取分析统计信息"""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) AS c FROM poem").fetchone()["c"]
    analyzed = conn.execute("SELECT COUNT(*) AS c FROM auto_tag_log WHERE status='ok'").fetchone()["c"]
    failed = conn.execute("SELECT COUNT(*) AS c FROM auto_tag_log WHERE status='fail'").fetchone()["c"]
    conn.close()
    return total, analyzed, failed


def has_existing_tags(poem_id, category):
    """检查某首诗在指定类别下是否已有标签"""
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM poem_tag WHERE poem_id = ? AND tag_type = ?",
        (poem_id, category)
    ).fetchone()
    conn.close()
    return row["c"] > 0


def save_poem_tag(poem_id, vocab_id, tag_type):
    """插入一条 poem_tag（去重）"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO poem_tag (poem_id, vocab_id, tag_type) VALUES (?, ?, ?)",
            (poem_id, vocab_id, tag_type)
        )
        conn.commit()
    except Exception as e:
        print(f"    [错误] 插入标签失败: {e}")
    finally:
        conn.close()


def save_log(poem_id, tag_count, model_name, status="ok"):
    """写入分析日志"""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO auto_tag_log (poem_id, analyzed_at, model, tag_count, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (poem_id, datetime.now().isoformat(), model_name, tag_count, status)
        )
        conn.commit()
    except Exception as e:
        print(f"    [错误] 写入日志失败: {e}")
    finally:
        conn.close()


# ==================== Prompt 构建与解析 ====================

def build_prompt_n(vocab):
    """
    构建打标签的 通用Prompt，属于系统提示词。
    将可用标签按类别分组传给 LLM，要求返回 JSON。
    """
    # 按类别组织标签描述
    labels_sections = []
    for cat in TAG_CATEGORIES:
        items = vocab.get(cat, [])
        if items:
            labels = "、".join([v["label"] for v in items])
            labels_sections.append(f"【{cat}】{labels}")

    labels_desc = "\n".join(labels_sections)

    # 构建日期、季节等提示辅助 LLM 理解
    prompt = f"""你是一位精通中华诗词的分析专家。按照下面的要求对下面的一组诗词分别进行分析。这是统一的指令。分析每首诗，为每个类别从可用标签中选择最合适的标签（每个类别最多选3个）。

要求：
1. 只输出 JSON 格式，不要输出任何其他内容（包括不要思考过程）
2. 仅从下方"可用标签"中选择，不要自创标签
3. 类别名称使用英文（theme/style/emotion/imagery/season/festival/allusion）
4. 如果某类别无法确定，省略该字段
5. 思考过程写在内部，最终输出严格的 JSON

输出示例：
{{ id1: {{"theme": "思乡", "style": "清新", "emotion": "哀愁", "imagery": "月", "season": "秋"}},
 id2: {{"theme": "思乡", "style": "清新", "emotion": "哀愁", "imagery": "月", "season": "秋"}}  }}
 
可用标签：
{labels_desc}

"""
    return prompt

def build_prompt(title, author_name, content, vocab):
    """
    构建打标签的 Prompt。
    将可用标签按类别分组传给 LLM，要求返回 JSON。
    """
    # 按类别组织标签描述
    labels_sections = []
    for cat in TAG_CATEGORIES:
        items = vocab.get(cat, [])
        if items:
            labels = "、".join([v["label"] for v in items])
            labels_sections.append(f"【{cat}】{labels}")

    labels_desc = "\n".join(labels_sections)

    # 截断过长内容
    if len(content) > MAX_CONTENT_LEN:
        content = content[:MAX_CONTENT_LEN] + "……"

    # 构建日期、季节等提示辅助 LLM 理解
    prompt = f"""你是一位精通中华诗词的分析专家。分析下面这首诗，为每个类别从可用标签中选择最合适的标签（每个类别最多选3个）。

要求：
1. 只输出 JSON 格式，不要输出任何其他内容（包括不要思考过程）
2. 仅从下方"可用标签"中选择，不要自创标签
3. 类别名称使用英文（theme/style/emotion/imagery/season/festival/allusion）
4. 如果某类别无法确定，省略该字段
5. 思考过程写在内部，最终输出严格的 JSON

输出示例：
{{"theme":"思乡","style":"清新","emotion":"哀愁","imagery":"月","season":"秋"}}

可用标签：
{labels_desc}

诗题：{title}
作者：{author_name}
诗歌正文：
{content}"""
    return prompt


def parse_llm_response(response_text, vocab):
    """
    解析 LLM 返回的 JSON，返回 {category: label} 字典。
    处理 R1 思考链干扰、多余文本等。
    """
    if not response_text:
        return {}

    # 1. 清除思考链 [思考内容]
    cleaned = re.sub(r'\《.*?》', '', response_text).strip()
    # 2. 清除 和  中英文标签包围的思考内容
    cleaned = re.sub(r'<.*?>', '', cleaned).strip()
    cleaned = re.sub(r'【.*?】', '', cleaned).strip()

    # 3. 提取 JSON 对象（第一个 { } 块）
    json_match = re.search(r'\{[\s\S]*?\}', cleaned)
    if not json_match:
        return {}

    json_str = json_match.group()

    # 4. 尝试解析
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        # 尝试修复常见问题：单引号、末尾逗号、多余空白
        json_str = re.sub(r"'", '"', json_str)          # 单引号→双引号
        json_str = re.sub(r",\s*}", "}", json_str)      # 末尾逗号
        json_str = re.sub(r",\s*]", "]", json_str)      # 数组末尾逗号
        json_str = re.sub(r"\s+", " ", json_str)        # 压缩空白
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError:
            return {}

    # 5. 只保留有效类别，且 label 必须在 vocab 中存在
    tags = {}
    for cat in TAG_CATEGORIES:
        label = result.get(cat, "").strip()
        if not label:
            continue
        # 在 vocab 中查找是否存在
        exists = any(v["label"] == label for v in vocab.get(cat, []))
        if exists:
            tags[cat] = label
        else:
            # 尝试模糊匹配（包含关系）
            for v in vocab.get(cat, []):
                if label in v["label"] or v["label"] in label:
                    tags[cat] = v["label"]
                    break

    return tags


# ==================== 核心分析逻辑 ====================

def analyze_one(poem, vocab, idx, total, provider):
    """
    分析单首诗并保存结果。
    返回 (poem_id, tag_count, success_or_not)
    """
    poem_id = poem["poem_id"]
    title = poem["title"]
    author_name = poem["author_name"]
    content = poem.get("content", "")

    if not content:
        print(f"    [跳过] ID={poem_id} 内容为空")
        save_log(poem_id, 0, provider.name, "skip")
        return poem_id, 0, "skip"

    print(f"  [开始] 第{idx}/{total}首 | {author_name}《{title}》({len(content)}字)")

    # 构建 Prompt
    prompt = build_prompt(title, author_name, content, vocab)

    # 调用 LLM（含重试）
    resp_text = None
    for attempt in range(1, MAX_RETRIES + 1):
        resp_text = provider.chat(prompt)
        if resp_text:
            break
        print(f"    [重试] 第{attempt}/{MAX_RETRIES}次失败，{RETRY_DELAY}s 后重试...")
        time.sleep(RETRY_DELAY)

    if not resp_text:
        print(f"    [失败] ID={poem_id} 调用 LLM 返回空")
        save_log(poem_id, 0, provider.name, "fail")
        return poem_id, 0, "fail"

    # 解析返回结果
    #tags = parse_llm_response(resp_text, vocab)
    try:
        tags = json.loads(resp_text)
    except json.JSONDecodeError:
        print(f"    [警告] ID={poem_id} LLM 返回无法解析")
        # 打印前 200 字符用于调试
        debug_text = resp_text[:200].replace("\n", " ")
        print(f"         原始返回: {debug_text}...")
        save_log(poem_id, 0, provider.name, "parse_fail")
        time.sleep(2)
        return poem_id, 0, "parse_fail"

    if not tags:
        print(f"    [警告] ID={poem_id} LLM 返回无法解析")
        # 打印前 200 字符用于调试
        debug_text = resp_text[:200].replace("\n", " ")
        print(f"         原始返回: {debug_text}...")
        save_log(poem_id, 0, provider.name, "parse_fail")
        return poem_id, 0, "parse_fail"

    # 写入数据库
    tag_count = 0
    for cat, label in tags.items():
        # 检查是否已有同类别标签
        if SKIP_EXISTING and has_existing_tags(poem_id, cat):
            continue
        if type(label) == list:
            for l in label:
                vocab_id = query_vocab_id(cat, l)
                if vocab_id:
                    save_poem_tag(poem_id, vocab_id, cat)
                    tag_count += 1
        else:
            vocab_id = query_vocab_id(cat, label)
            if vocab_id:
                save_poem_tag(poem_id, vocab_id, cat)
                tag_count += 1

    save_log(poem_id, tag_count, provider.name, "ok")
    tag_summary = ", ".join([f"{cat}={label}" for cat, label in tags.items()])
    print(f"    [OK] → {tag_summary}  (新增{tag_count}个标签)")
    return poem_id, tag_count, "ok"

def analyze_n(poems, vocab,  provider):
    """
    分析单首诗并保存结果。
    返回 (poem_id, tag_count, success_or_not)
    """
    start_time = time.time()
    total, success_count, fail_count, parse_fail_count, skip_count, total_tags = len(poems), 0, 0, 0, 0, 0
    for i in range(0, len(poems), 10):
        poems_list = []
        time1 = time.time()
        for j in range(i, i+10):
            if j >= len(poems):
                break
            poem = poems[j]
            poem_id = poem["poem_id"]
            title = poem["title"]
            author_name = poem["author_name"]
            content = poem.get("content", "")
            if not content:
                print(f"    [跳过] ID={poem_id} 内容为空")
                save_log(poem_id, 0, provider.name, "skip")
            poems_list.append({"id":poem_id,  "title": title, "author_name": author_name, "content": content.replace("\n", "")})

        print(f"  [开始] 第{i+1}~{i+len(poems_list)}/{len(poems)}首")

        # 构建 Prompt
        prompt = build_prompt_n(vocab)
        prompt += f"""\n待分析诗词：\n{json.dumps(poems_list, ensure_ascii=False)}"""

        # 调用 LLM（含重试）
        resp_text = None
        for attempt in range(1, MAX_RETRIES + 1):
            resp_text = provider.chat(prompt)
            if resp_text:
                break
            print(f"    [重试] 第{attempt}次失败，{RETRY_DELAY}s 后重试...")
            time.sleep(RETRY_DELAY)

        if not resp_text:
            print(f"    [失败] 第{i+1}~{i+len(poems_list)}/{len(poems)}首 调用 LLM 返回空")
            save_log(poem_id, 0, provider.name, "fail")
            continue  # 跳过当前批次

        # 解析返回结果
        try:
            tmp = resp_text.replace('```json', '').replace('```', '')
            #tags_list = json.loads(f"""{{"results":[{tmp[9:-5]}]}}""")["results"]
            tags_dict = json.loads(tmp)
        except json.JSONDecodeError:
            print(f"    [警告] 第{i+1}~{i+len(poems_list)}/{len(poems)}首 LLM 返回无法解析")
            # 打印前 200 字符用于调试
            debug_text = resp_text.replace("\n", " ")
            print(f"         原始返回: {debug_text}...")
            save_log(poem_id, 0, provider.name, "parse_fail")
            time.sleep(2)
            continue

        if not tags_dict:
            print(f"    [警告] ID={poem_id} LLM 返回无法解析")
            # 打印前 200 字符用于调试
            debug_text = resp_text[:200].replace("\n", " ")
            print(f"         原始返回: {debug_text}...")
            save_log(poem_id, 0, provider.name, "parse_fail")
            return poem_id, 0, "parse_fail"

        # 写入数据库
        batch_success_count = 0
        batch_fail_count = 0
        batch_total_tags = 0
        #tags_dict = {tag["id"]:tag["ret"]for i, tag in enumerate(tags_list)}
        for poem in poems_list:
            poem_id = poem["id"]
            title = poem["title"]
            author_name = poem["author_name"]
            if poem_id not in tags_dict:
                print(f"    [警告] ID={poem_id} LLM 返回无法解析")
                save_log(poem_id, 0, provider.name, "parse_fail")
                batch_fail_count += 1
                continue

            tag_count = 0
            tags = tags_dict[poem_id]
            for cat, label in tags.items():
                # 检查是否已有同类别标签
                if SKIP_EXISTING and has_existing_tags(poem_id, cat):
                    continue
                if type(label) == list:
                    for l in label:
                        vocab_id = query_vocab_id(cat, l)
                        if vocab_id:
                            save_poem_tag(poem_id, vocab_id, cat)
                            tag_count += 1
                else:
                    vocab_id = query_vocab_id(cat, label)
                    if vocab_id:
                        save_poem_tag(poem_id, vocab_id, cat)
                        tag_count += 1

            save_log(poem_id, tag_count, provider.name, "ok")
            tag_summary = f"    [OK] → {author_name}《{title}》(新增{tag_count}个标签),"
            tag_summary += ", ".join([f"{cat}={label}" for cat, label in tags.items()])
            print(f"{tag_summary}  ")
            batch_success_count += 1
            batch_total_tags += tag_count
        print(f">>>>[完成] 用时{time.time() - time1:.1f}s,  本批次共分析 {batch_success_count} 首，失败 {batch_fail_count} 首，新增标签 {batch_total_tags} 个")
        success_count += batch_success_count
        fail_count += batch_fail_count
        total_tags += batch_total_tags
    elapsed = time.time() - start_time
    print(f"\n{'=' * 50}")
    print(f"[完成] 共分析 {total} 首")
    print(f"       成功 {success_count} 首，失败 {fail_count} 首")
    print(f"       新增标签 {total_tags} 个")
    print(f"       用时 {elapsed:.1f}s (平均 {elapsed/max(total,1):.1f}s/首)")
    print(f"{'=' * 50}")


def analyze_batch(poems, vocab, provider):
    """批量分析"""
    total = len(poems)
    success_count = 0
    fail_count = 0
    total_tags = 0
    start_time = time.time()

    for i, poem in enumerate(poems, 1):
        time1 = time.time()
        _, tag_count, status = analyze_one(poem, vocab, i, total, provider)
        if status == "ok":
            success_count += 1
            total_tags += tag_count
        else:
            fail_count += 1
        # 间隔
        if i < total:
            time.sleep(REQUEST_INTERVAL)

        elapsed_one = time.time() - time1
        print(f"    [完成] 用时 {elapsed_one:.1f}s, 第{i}/{total}首 | "
              f"{poem['author_name']}《{poem['title']}》({len(poem['content'])}字)")

    elapsed = time.time() - start_time
    print(f"\n{'=' * 50}")
    print(f"[完成] 共分析 {total} 首")
    print(f"       成功 {success_count} 首，失败 {fail_count} 首")
    print(f"       新增标签 {total_tags} 个")
    print(f"       用时 {elapsed:.1f}s (平均 {elapsed/max(total,1):.1f}s/首)")
    print(f"{'=' * 50}")


# ==================== 入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description="KBCP 智能诗词打标签工具 - 支持多种 LLM 提供者 (Ollama/DeepSeek/智谱)"
    )
    parser.add_argument("-m", "--mode",
                        choices=["all", "missing", "stats", "full"],
                        default="missing",
                        help="运行模式: all=全量分析, missing=仅分析某类别缺失的诗(默认), "
                             "full=全量不分类别, stats=仅查看统计")
    parser.add_argument("-c", "--category",
                        choices=TAG_CATEGORIES,
                        default="theme",
                        help="缺失分析模式下检查的标签类别 (默认: theme)")
    parser.add_argument("-l", "--limit", type=int, default=None,
                        help="限制分析数量 (用于测试)")
    parser.add_argument("-p", "--provider",
                        choices=["ollama", "deepseek", "zhipu"],
                        default="zhipu",
                        help="LLM 提供者 (默认使用 KBCP_LLM_config.ini 中的 default)")
    args = parser.parse_args()

    # 加载配置文件
    config = load_config()
    provider_name = args.provider or config['provider'].get('default', 'ollama')

    # 创建 LLM 提供者
    try:
        provider = create_provider(provider_name, config)
    except ValueError as e:
        print(f"[错误] {e}")
        return

    # 从配置覆盖公共参数
    global REQUEST_INTERVAL, MAX_CONTENT_LEN
    REQUEST_INTERVAL = float(config['common'].get('request_interval', str(DEFAULT_REQUEST_INTERVAL)))
    MAX_CONTENT_LEN = int(config['common'].get('max_content_len', str(DEFAULT_MAX_CONTENT_LEN)))

    print(f"[信息] 提供者: {provider}")
    print(f"[信息] 请求间隔: {REQUEST_INTERVAL}s, 内容截断: {MAX_CONTENT_LEN}字")

    # 初始化日志表
    init_log_table()

    # 加载受控词表
    vocab = load_vocab()
    print(f"[信息] 加载受控词表: {sum(len(v) for v in vocab.values())} 条")

    if args.mode == "stats":
        total, analyzed, failed = get_stats()
        remaining = total - analyzed - failed
        print(f"\n[统计]")
        print(f"       诗词总数:     {total}")
        print(f"       已分析:       {analyzed}")
        print(f"       失败/跳过:    {failed}")
        print(f"       待分析:       {remaining}")
        return

    if args.mode == "missing":
        print(f"[信息] 检查缺少 [{args.category}] 标签的诗...")
        poems = get_poems_missing_tags(limit=args.limit, category=args.category)
    else:
        print("[信息] 获取所有未分析的诗...")
        poems = get_all_unanalyzed_poems(limit=args.limit)

    if not poems:
        print("[信息] 没有待分析的诗")
        total, analyzed, failed = get_stats()
        print(f"       总计 {total} 首，已分析 {analyzed} 首")
        return

    total, analyzed, failed = get_stats()
    print(f"[信息] 进度: 总计 {total} 首，已分析 {analyzed} 首，本次待分析 {len(poems)} 首")

    analyze_batch(poems, vocab, provider)   # 一首诗一首诗的遍历（本意虽然是批量）
    #analyze_n(poems, vocab, provider)      # 批量分析

if __name__ == '__main__':
    main()
