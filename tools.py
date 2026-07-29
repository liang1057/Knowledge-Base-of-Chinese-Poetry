# -*- coding: utf-8 -*-
"""
tools.py - KBCP 数据迁移与维护工具
"""
import json
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "dataset" / "kbcp.db"


def get_conn():
    """获取数据库连接"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate_description_to_appreciation(dry_run=True):
    """将 poem.description 迁移到 poem.appreciation"""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM poem WHERE description IS NOT NULL AND description != ''")
    total_desc = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM poem WHERE appreciation IS NOT NULL AND appreciation != ''")
    total_appr = cur.fetchone()[0]

    cur.execute("""
        SELECT poem_id, title, description,
               substr(appreciation, 1, 80) AS appreciation_preview
        FROM poem
        WHERE description IS NOT NULL AND description != ''
          AND (appreciation IS NULL OR appreciation = '')
        ORDER BY poem_id
    """)
    rows = cur.fetchall()

    print(f"={'='*60}")
    print(f"  数据迁移：description => appreciation")
    print(f"={'='*60}")
    print(f"  模式: {'预览 (dry-run)' if dry_run else '执行'}")
    print(f"  诗词总量: {total_desc} 首有 description")
    print(f"  已有赏析: {total_appr} 首")
    print(f"  待迁移: {len(rows)} 首")

    if not rows:
        print("  [完成] 无需迁移")
        conn.close()
        return

    if dry_run:
        print("\n  迁移预览（前 10 条）：")
        for r in rows[:10]:
            desc = (r['description'] or '')[:50].replace('\n', ' ')
            print(f"  {r['poem_id']:<20} {r['title']:<20} {desc}")
        print(f"\n  [dry-run] 确认无误后运行: python tools.py migrate --no-dry-run")
        conn.close()
        return

    start = time.time()
    updated = 0
    cur.execute("BEGIN TRANSACTION")
    for r in rows:
        cur.execute("UPDATE poem SET appreciation = ? WHERE poem_id = ?",
                    (r['description'], r['poem_id']))
        updated += 1
        if updated % 5000 == 0:
            print(f"    进度: {updated}/{len(rows)}")
    conn.commit()
    elapsed = time.time() - start
    print(f"  [完成] 共更新 {updated} 首，用时 {elapsed:.1f}s")
    conn.close()


def stats():
    """数据字段填写率统计"""
    conn = get_conn()
    cur = conn.cursor()

    fields = [
        ('description', '客观简介'),
        ('appreciation', '赏析'),
        ('translation', '白话释义'),
        ('background', '创作背景'),
    ]

    cur.execute("SELECT COUNT(*) FROM poem")
    total = cur.fetchone()[0]

    print(f"={'='*55}")
    print(f"  KBCP 数据字段填写率统计")
    print(f"={'='*55}")
    print(f"  诗词总数: {total} 首\n")

    for col, label in fields:
        cur.execute(f"SELECT COUNT(*) FROM poem WHERE {col} IS NOT NULL AND {col} != ''")
        filled = cur.fetchone()[0]
        pct = filled / total * 100 if total else 0
        print(f"  {label:<12} {col:<16} {filled:>6} 首 ({pct:>5.1f}%)")
    conn.close()


def import_author_bio(dry_run=True):
    """
    从 data/Author.json 导入诗人传记到 author.bio 字段。
    JSON 中的 author_id/dynasty_id 与数据库不匹配，
    按 author_name + dynasty 名称匹配。
    """
    json_path = BASE_DIR / "data" / "Author.json"
    if not json_path.exists():
        print(f"[错误] 文件不存在: {json_path}")
        return

    print(f"={'='*60}")
    print(f"  导入诗人传记：Author.json => author.bio")
    print(f"={'='*60}")
    print(f"  模式: {'预览 (dry-run)' if dry_run else '执行'}")

    conn = get_conn()
    cur = conn.cursor()

    with open(str(json_path), 'r', encoding='utf-8') as f:
        authors_data = json.load(f)
    dynasty_count = len(authors_data)
    print(f"  朝代: {dynasty_count} 个")

    # 朝代名 => dynasty_id 映射
    cur.execute("SELECT dynasty_id, name FROM dynasty")
    dynasty_map = {row['name']: row['dynasty_id'] for row in cur.fetchall()}

    # 预加载数据库中诗人
    cur.execute("SELECT a.author_id, a.name, a.dynasty_id, a.bio, d.name AS dynasty_name FROM author a LEFT JOIN dynasty d ON a.dynasty_id = d.dynasty_id")
    db_authors = [dict(row) for row in cur.fetchall()]

    total_poets = 0
    matched = 0
    not_found = 0
    already_have = 0
    updated = 0
    report = []

    for dynasty_name, poet_list in authors_data.items():  # 遍历从json文件中读取的结果
        for item in poet_list:
            total_poets += 1
            dynasty = (item.get('dynasty', '') or '').strip()
            name = (item.get('author_name', '') or '').strip()
            info = (item.get('info', '') or '').strip()
            if not name or not info:
                continue


            matches = [a for a in db_authors
                       if a['name'] == name and a['dynasty_name'] == dynasty]
            if not matches:
                report.append(f"  [未匹配] {dynasty_name}·{name}")
                not_found += 1
                continue

            author = matches[0]
            if author['bio']:
                already_have += 1
                continue

            matched += 1
            if not dry_run:
                cur.execute("UPDATE author SET bio = ? WHERE author_id = ?",
                            (info, author['author_id']))
                updated += 1
                if updated <= 5:
                    preview = info[:60].replace('\n', ' ')
                    report.append(f"  [更新] {dynasty_name}·{name} => {preview}...")

            if not dry_run:
                conn.commit()

    print(f"  {'='*50}")
    print(f"  统计:")
    print(f"    总读取: {total_poets} 条")
    print(f"    匹配成功: {matched} 位")
    if not dry_run:
        print(f"    已更新: {updated} 位")
    print(f"    已有传记: {already_have} 位（跳过）")
    print(f"    未匹配: {not_found} 位")

    if dry_run and report:
        print("\n  预览:")
        for line in report[:10]:
            print(line)

    if dry_run:
        print(f"\n  [dry-run] 确认后运行: python tools.py import-bio --no-dry-run")

    conn.close()


def show_schama(startcol, endcol):
    '''
    显示元数据
    :return:
    '''
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM myschema")
    rows = cur.fetchall()
    col_names = [desc[0] for desc in cur.description]

    if not rows:
        print("myschema 表为空")
        conn.close()
        return

    print(f"表 myschema，共 {len(rows)} 行，{len(col_names)} 列")
    print(f"{'─' * 70}")
    # 表头
    header = '\t'.join(col_names)
    print(f"  {header}")
    print(f"{'─' * 70}")
    # 数据行
    for r in rows:
        vals = '\t'.join(str(v) if v is not None else 'NULL' for v in r[startcol:endcol+1])
        print(f"  {vals}")

    conn.close()




if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python tools.py stats                      查看字段填写率")
        print("  python tools.py migrate                    dry-run 预览description迁移")
        print("  python tools.py migrate --no-dry-run       执行description迁移")
        print("  python tools.py import-bio                 预览导入传记")
        print("  python tools.py import-bio --no-dry-run    执行导入传记")
        print("  python tools.py show-schema                显示元数据")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == 'stats':
        stats()
    elif cmd == 'migrate':
        dry_run = '--no-dry-run' not in sys.argv
        migrate_description_to_appreciation(dry_run=dry_run)
    elif cmd == 'import-bio':
        dry_run = '--no-dry-run' not in sys.argv
        import_author_bio(dry_run=dry_run)
    elif cmd == 'show-schema':
        show_schama(startcol=1, endcol=3)
    else:
        print(f"未知命令: {cmd}")
