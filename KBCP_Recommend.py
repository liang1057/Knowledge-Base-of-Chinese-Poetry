# -*- coding: utf-8 -*-
"""
KBCP_Recommend.py - 诗词语义推荐
=================================
基于 poem_embedding 向量余弦相似度，
为指定诗词推荐语义相近的作品。

使用方式:
    python KBCP_Recommend.py <poem_id>
    python KBCP_Recommend.py T00001_00000
"""
import sys
import numpy as np
from KBCP_DAL import SQLiteDAL


def recommend_by_poem(dal, poem_id: str, top_k: int = 10):
    """基于 Embedding 向量找语义相似的诗词"""
    # 获取目标诗的向量
    target = dal._fetchone(
        "SELECT e.*, p.title, a.name AS author_name, d.name AS dynasty_name "
        "FROM poem_embedding e "
        "JOIN poem p ON e.poem_id = p.poem_id "
        "LEFT JOIN author a ON p.author_id = a.author_id "
        "LEFT JOIN dynasty d ON p.dynasty_id = d.dynasty_id "
        "WHERE e.poem_id = ?",
        (poem_id,)
    )
    if not target or not target.get('embedding'):
        return []

    target_vec = np.frombuffer(target['embedding'], dtype=np.float32)

    # 加载所有向量
    rows = dal._fetchall("""
        SELECT e.poem_id, e.embedding,
               p.title, a.name AS author_name, d.name AS dynasty_name
        FROM poem_embedding e
        JOIN poem p ON e.poem_id = p.poem_id
        LEFT JOIN author a ON p.author_id = a.author_id
        LEFT JOIN dynasty d ON p.dynasty_id = d.dynasty_id
        WHERE e.poem_id != ?
    """, (poem_id,))

    results = []
    for r in rows:
        emb_bytes = r.get('embedding')
        if not emb_bytes:
            continue
        try:
            emb_vec = np.frombuffer(emb_bytes, dtype=np.float32)
            dot = np.dot(target_vec, emb_vec)
            norm = np.linalg.norm(target_vec) * np.linalg.norm(emb_vec)
            sim = dot / norm if norm > 0 else 0
            results.append((sim, r))
        except Exception:
            continue

    results.sort(key=lambda x: -x[0])
    return [
        {
            'poem_id': r['poem_id'],
            'title': r['title'],
            'author_name': r['author_name'] or '',
            'dynasty_name': r['dynasty_name'] or '',
            'similarity': round(float(sim), 4),
        }
        for sim, r in results[:top_k]
    ]


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python KBCP_Recommend.py <poem_id>")
        sys.exit(1)

    poem_id = sys.argv[1]
    dal = SQLiteDAL()
    recs = recommend_by_poem(dal, poem_id)

    if not recs:
        print(f"未找到「{poem_id}」的推荐结果")
        sys.exit(1)

    print(f"【{recs[0]['author_name']}《{recs[0]['title']}》的相似诗词推荐】\n")
    for r in recs:
        bar = '█' * int(r['similarity'] * 20)
        print(f"  {r['dynasty_name']} {r['author_name']}《{r['title']}》"
              f"  {bar} {r['similarity']:.2f}")
