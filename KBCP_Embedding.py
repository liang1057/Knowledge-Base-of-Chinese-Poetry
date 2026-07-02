# -*- coding: utf-8 -*-
"""
KBCP_Embedding.py - 生成诗词 Embedding 向量
============================================
两种模式：
  1. [默认] sentence-transformers 模型（需下载模型，网络受限时可用 --local-model）
  2. --use-tfidf   使用 sklearn TfidfVectorizer（纯本地，零下载）

使用方式:
    # 查看状态
    python KBCP_Embedding.py --status

    # 用 TF-IDF 生成向量（推荐，零依赖下载）
    python KBCP_Embedding.py --generate --use-tfidf

    # 用 sentence-transformers 生成（需先下载模型）
    python KBCP_Embedding.py --generate

    # 测试：只处理前 100 首
    python KBCP_Embedding.py --generate --use-tfidf --limit 100
"""
import time
import json
import os
import argparse
import numpy as np
from KBCP_DAL import SQLiteDAL


# ============================================================
#  TF-IDF 向量化（零下载，纯本地）
# ============================================================

class TfidfEmbedder:
    """使用 sklearn TfidfVectorizer 生成向量"""

    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        print("  [模型] 初始化 TF-IDF 向量化器...")
        t0 = time.time()
        # 使用字符级别的 n-gram 支持中文
        self.vectorizer = TfidfVectorizer(
            analyzer='char',
            ngram_range=(1, 3),
            max_features=10000,
            sublinear_tf=True,
        )
        # 先收集所有文本以拟合词表（只收集前 5000 首作为样本）
        print("  [模型] 正在拟合词表（采样前 5000 首）...")
        dal = SQLiteDAL()
        sample = dal.get_poems_for_embedding(limit=5000)
        texts = []
        for p in sample:
            t = _build_chunk_text(p)
            if t:
                texts.append(t)
        self.vectorizer.fit(texts)
        self.vocab_size = len(self.vectorizer.get_feature_names_out())
        print(f"  [模型] 词表大小: {self.vocab_size}")
        print(f"  [模型] 初始化完成，用时 {time.time() - t0:.1f}s")

    def encode(self, texts, show_progress_bar=False):
        """将文本列表转为向量（返回 numpy 数组）"""
        if isinstance(texts, str):
            texts = [texts]
        matrix = self.vectorizer.transform(texts)
        # 转为 dense 向量
        return matrix.toarray()

    @property
    def dim(self):
        return self.vocab_size


# ============================================================
#  sentence-transformers 模型
# ============================================================

def get_sbert_model(model_name='paraphrase-multilingual-MiniLM-L12-v2',
                    local_path=None):
    """加载 sentence-transformers 模型"""
    from sentence_transformers import SentenceTransformer
    t0 = time.time()
    if local_path:
        print(f"  [模型] 从本地加载: {local_path}")
        model = SentenceTransformer(local_path)
    else:
        print(f"  [模型] 下载 {model_name}...")
        model = SentenceTransformer(model_name)
    print(f"  [模型] 加载完成，用时 {time.time() - t0:.1f}s")
    return model


# ============================================================
#  公共工具函数
# ============================================================

def _build_chunk_text(poem):
    """从诗词记录构建待向量化的文本"""
    title = poem.get('title', '')
    author = poem.get('author_name', '')
    sentences_text = _parse_sentences(poem.get('sentences', ''))
    if not sentences_text:
        sentences_text = poem.get('content', '') or ''
    if not sentences_text:
        return ''
    return f"{author}《{title}》{sentences_text}"


def _parse_sentences(sentences_raw):
    """解析 sentences 字段（可能是 JSON 数组或纯文本）"""
    if not sentences_raw:
        return ''
    try:
        arr = json.loads(sentences_raw)
        if isinstance(arr, list):
            return ' '.join(arr)
    except (json.JSONDecodeError, TypeError):
        pass
    return sentences_raw


def get_status(dal):
    """查看向量生成状态"""
    total = dal._fetchone(
        "SELECT COUNT(*) AS c FROM poem "
        "WHERE content IS NOT NULL AND content != ''"
    )
    embedded = dal._fetchone("SELECT COUNT(*) AS c FROM poem_embedding")
    pending = total['c'] - embedded['c']

    print(f"={'='*55}")
    print(f"  Embedding 状态")
    print(f"={'='*55}")
    print(f"  有内容的诗词:   {total['c']}")
    print(f"  已生成向量:     {embedded['c']}")
    print(f"  待生成:         {pending}")
    print(f"  {'='*55}")
    return pending


def generate_embeddings(dal, model, limit=None, use_tfidf=False):
    """批量生成向量"""
    poems = dal.get_poems_for_embedding(limit=limit)
    if not poems:
        print("  [信息] 没有待处理的诗词")
        return

    total = len(poems)
    print(f"  [开始] 共 {total} 首需要生成向量")

    start = time.time()
    success = 0

    for i, poem in enumerate(poems, 1):
        chunk_text = _build_chunk_text(poem)
        if not chunk_text:
            continue

        poem_id = poem['poem_id']

        if use_tfidf:
            vec = model.encode([chunk_text])[0]
            # TF-IDF 返回 float64，转 float32 节省空间
            vec_bytes = vec.astype(np.float32).tobytes()
        else:
            vec = model.encode([chunk_text], show_progress_bar=False)[0]
            vec_bytes = vec.astype('float32').tobytes()

        dal.save_embedding(poem_id, chunk_text, vec_bytes)
        success += 1

        if i % 5 == 0 or i == total:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            eta = (total - i) / rate if rate > 0 else 0
            print(f"    进度: {i}/{total}  |  "
                  f"{rate:.0f}首/s | 预计剩余 {eta:.0f}s")

    elapsed = time.time() - start
    print(f"\n  ✓ 完成！共生成 {success}/{total} 首，总用时 {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="KBCP Embedding 生成工具"
    )
    parser.add_argument('--generate', action='store_true',
                        help='生成 Embedding 向量')
    parser.add_argument('--status', action='store_true',
                        help='查看生成状态')
    parser.add_argument('--limit', type=int, default=None,
                        help='限制处理数量（测试用）')
    parser.add_argument('--use-tfidf', action='store_true',
                        help='使用 TF-IDF 替代 sentence-transformers（零下载）')
    parser.add_argument('--model',
                        default='paraphrase-multilingual-MiniLM-L12-v2',
                        help='sentence-transformers 模型名')
    parser.add_argument('--local-model', default=None,
                        help='本地模型目录路径')

    args = parser.parse_args()

    dal = SQLiteDAL()

    if args.status:
        get_status(dal)
        return

    if args.generate:
        pending = get_status(dal)
        if pending == 0:
            print("  没有需要生成的向量")
            return

        if args.use_tfidf:
            model = TfidfEmbedder()
            generate_embeddings(dal, model, limit=args.limit, use_tfidf=True)
        else:
            model = get_sbert_model(args.model, local_path=args.local_model)
            generate_embeddings(dal, model, limit=args.limit)

        # 更新状态
        print()
        get_status(dal)
        return

    # 默认显示状态
    get_status(dal)
    print(f"\n  用法示例:")
    print(f"    python KBCP_Embedding.py --status                  # 查看状态")
    print(f"    python KBCP_Embedding.py --generate --use-tfidf    # 用 TF-IDF 生成")
    print(f"    python KBCP_Embedding.py --generate               # 用 sbert 生成")
    print(f"    python KBCP_Embedding.py --generate --limit 100    # 测试")


if __name__ == '__main__':
    main()

    # bash
    # python KBCP_Embedding.py --generate --local-model ./models/paraphrase-multilingual-MiniLM --limit 100
