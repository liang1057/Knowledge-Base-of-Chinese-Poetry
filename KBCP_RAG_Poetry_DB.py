# -*- coding: utf-8 -*-
# @Time    : 2026/06/23
# @Author  : Leon
# @Email   : liang1057@163.com
# @File    : KBCP_RAG_Poetry_DB.py
# @Project : 中华诗词知识库 Knowledge Base of Chinese Poetry (KBCP)
# @Description: 重构后的数据库操作 - v2.0
#   基于新 Schema，支持 FK + 中间表 + 归一化 vocab

import json
import os
import sys
import datetime
from KBCP_RAG_Poem_Schema import *

# ============================================================
#  实体工厂
# ============================================================
def GenerateEntity(entity_name):
    mapper = {
        'poem': table_poem,
        'author': table_author,
        'dynasty': table_dynasty,
        'vocab': table_vocab,
        'poem_tag': table_poem_tag,
        'author_tag': table_author_tag,
        'myschema': table_myschema,
    }
    cls = mapper.get(entity_name)
    return cls() if cls else None


# ============================================================
#  受控词表初始数据
#  格式: [(category, label), ...]
# ============================================================
VOCAB_DATA = {
    'theme': [
        '思乡', '送别', '边塞', '怀古', '咏史', '山水', '田园',
        '咏物', '闺情', '羁旅', '饮酒', '赠答', '节序', '宫怨',
        '爱国', '闲适', '隐逸', '月夜', '怀人', '写景',
    ],
    'style': [
        '豪放', '婉约', '沉郁', '清新', '雄浑', '含蓄', '典雅',
        '质朴', '悲壮', '空灵', '绮丽', '旷达', '自然', '凝练', '诙谐',
    ],
    'emotion': [
        '喜悦', '悲伤', '愤怒', '恐惧', '惊讶', '哀愁', '忧愁',
        '忧愤', '悲愤', '悲凉', '离愁', '思君', '思妇', '思亲',
        '旷达', '狂放', '乐观', '自大', '惆怅',
    ],
    'imagery': [
        '月', '柳', '花', '雨', '雪', '云', '风', '山', '水',
        '夜', '天', '地', '日', '星', '河', '湖', '江', '海',
        '松', '竹', '梅', '兰', '菊', '鸟', '鱼',
    ],
    'genre': ['诗', '词', '曲', '赋', '其他'],
    'form': [
        '五言绝句', '七言绝句', '五言律诗', '七言律诗',
        '五言长诗', '七言长诗', '乐府', '古体诗', '其他',
    ],
    'meter': ['平水韵', '中华新韵', '其他'],
    'language_style': ['典雅', '豪放', '婉约', '幽默', '讽刺', '其他'],
    'season': ['春', '夏', '秋', '冬', '其他'],
    'festival': ['春节', '中秋节', '端午节', '元宵节', '重阳节', '清明节', '其他'],
    'review_status': ['未审核', '已审核', '草稿', '已发布'],
    'allusion': [],
}

# 类别简称 → vocab_id 前缀映射
CATEGORY_PREFIX = {
    'theme': 'THM', 'style': 'STY', 'emotion': 'EMO', 'imagery': 'IMG',
    'genre': 'GEN', 'form': 'FRM', 'meter': 'MET', 'language_style': 'LGS',
    'season': 'SES', 'festival': 'FES', 'review_status': 'RVS', 'allusion': 'ALU',
}


# ============================================================
#  初始化 vocab 表
# ============================================================
def init_table_data_vocab():
    # 清空
    sql = 'DELETE FROM vocab'
    cursor = runSQL(sql)
    if cursor is None:
        print('>>>> [warning] 清空表 vocab 失败')

    entity = GenerateEntity('vocab')
    idx = 1
    for category, labels in VOCAB_DATA.items():
        prefix = CATEGORY_PREFIX[category]
        for i, label in enumerate(labels):
            vocab_id = f'V-{prefix}-{i+1:03d}'
            entity.SetValue('vocab_id', vocab_id)
            entity.SetValue('category', category)
            entity.SetValue('label', label)
            entity.SetValue('sort_order', i + 1)
            entity.Insert()
            idx += 1
    print(f'>>>> [info] 初始化 vocab 表完成, 共 {idx - 1} 条记录')


# ============================================================
#  查询 vocab: 根据 category + label 返回 vocab_id
# ============================================================
def query_vocab_id(category, label):
    """查询受控词, 找不到则返回 None"""
    try:
        cursor = Cursor()
        cursor.execute(
            "SELECT vocab_id FROM vocab WHERE category = ? AND label = ?",
            (category, label)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f'>>>> [error] query_vocab_id({category}, {label}): {e}')
        return None


# ============================================================
#  初始化朝代表
# ============================================================
def init_table_data_dynasty():
    sql = 'DELETE FROM dynasty'
    cursor = runSQL(sql)
    if cursor is None:
        print('>>>> [warning] 清空表 dynasty 失败')

    entity = GenerateEntity('dynasty')
    json_path = os.path.join(os.path.dirname(__file__), 'data', 'Dynasty.json')

    if not os.path.exists(json_path):
        print(f'>>>> [error] Dynasty.json 不存在: {json_path}')
        return

    json_dynasty = json.load(open(json_path, 'r', encoding='utf-8'))['dynasty']
    for d in json_dynasty:
        try:
            entity.SetValue('dynasty_id', d['dynasty_id'])
            entity.SetValue('name', d['name'])
            entity.SetValue('another_name', d['another_name'])
            entity.SetValue('start_year', d['start_year'])
            entity.SetValue('end_year', d['end_year'])
            entity.SetValue('note', d['note'])
            entity.Insert()
        except Exception as e:
            print(f'>>>> [error] 插入朝代失败 {d.get("name", "?")}: {e}')

    print('>>>> [info] 初始化朝代表完成')


# ============================================================
#  初始化 myschema 表
# ============================================================
def init_table_data_myschema():
    sql = 'DELETE FROM myschema'
    cursor = runSQL(sql)
    if cursor is None:
        print('>>>> [warning] 清空表 myschema 失败')

    sr = SYS_RESOURCE()
    tIndex = 1
    entity = GenerateEntity('myschema')

    for table_name in ['poem', 'author', 'dynasty', 'vocab', 'poem_tag', 'author_tag', 'myschema']:
        try:
            table_entity = sr.tables.get(table_name)
            if table_entity is None:
                continue
            entity.SetValue('table_name', table_entity.TableName())
            for j, col in enumerate(table_entity.col_name):
                entity.SetValue('schema_id', f'S_{tIndex:05d}')
                tIndex += 1
                entity.SetValue('column_label', table_entity.col_label[j])
                entity.SetValue('column_name', table_entity.col_name[j])
                entity.SetValue('type', table_entity.col_type[j])
                entity.Insert()
            print(f'>>>> [info] 插入表 {table_entity.TableName()} 的 schema 信息成功')
        except Exception as e:
            print(f'>>>> [error] 插入 schema 失败 {table_name}: {e}')


# ============================================================
#  SYS_RESOURCE: 创建数据库表
# ============================================================
class SYS_RESOURCE():
    def __init__(self):
        self.tables = {}
        table_names = ['dynasty', 'author', 'poem', 'vocab', 'poem_tag', 'author_tag', 'myschema']
        for t in table_names:
            t_entity = GenerateEntity(t)
            self.tables[t] = t_entity

    def CreateDB(self, db_path='./dataset/kbcp.db'):
        """创建或重建数据库 (DB 已连接)"""

        # 开启外键支持
        try:
            Cursor().execute("PRAGMA foreign_keys = ON")
            print('>>>> [info] 外键约束已开启')
        except Exception as e:
            print(f'>>>> [warning] 开启外键失败: {e}')

        # 先 drop 后 create (注意顺序: 先删除有外键依赖的)
        drop_order = ['poem_tag', 'author_tag', 'poem', 'author', 'vocab', 'dynasty', 'myschema']
        for t in drop_order:
            try:
                Cursor().execute(f"DROP TABLE IF EXISTS {t}")
            except Exception as e:
                print(f'>>>> [warning] drop {t} 失败: {e}')

        # 创建表 (注意顺序: 先创建被依赖的表)
        create_order = ['dynasty', 'author', 'poem', 'vocab', 'poem_tag', 'author_tag', 'myschema']
        for t in create_order:
            try:
                sql = self.tables[t].GET_SQL_Create_Table()
                Cursor().execute(sql)
                print(f'>>>> [info] 创建表 {t} 成功')
            except Exception as e:
                print(f'>>>> [error] 创建表 {t} 失败: {e}')
                print(f'     SQL: {self.tables[t].GET_SQL_Create_Table()}')

        init_table_data_myschema()


# ============================================================
#  从 JSON 加载数据到新数据库
# ============================================================
def load_poems_from_json(json_path='./data/Poetry_China_all.json'):
    """迁移: 将旧 JSON 数据按新 Schema 导入数据库"""

    # 连接数据库
    db_path = os.path.join(os.path.dirname(__file__), 'dataset', 'kbcp.db')
    Conn(db_path)

    # 重建表结构
    sys_res = SYS_RESOURCE()
    sys_res.CreateDB()

    # 初始化基础数据
    init_table_data_dynasty()
    init_table_data_vocab()

    # 加载 JSON
    abs_json = os.path.join(os.path.dirname(__file__), json_path)
    if not os.path.exists(abs_json):
        print(f'>>>> [error] JSON 文件不存在: {abs_json}')
        return

    all_poems = json.load(open(abs_json, 'r', encoding='utf-8'))
    dynasty_dict = _load_dynasty_map()

    # 准备实体
    entity_poem = GenerateEntity('poem')
    entity_author = GenerateEntity('author')
    entity_poem_tag = GenerateEntity('poem_tag')

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    author_count = 0
    poem_count = 0

    print('>>>> 开始导入诗词数据...')

    for i, dynasty_name in enumerate(all_poems.keys()):
        dynasty_id = dynasty_dict.get(dynasty_name, '?')
        authors = all_poems[dynasty_name]

        for j, author_name in enumerate(authors.keys()):
            author_id = f'{dynasty_id}{j+1:04d}'
            poem_list = authors[author_name]

            # --- 插入作者 ---
            try:
                entity_author.SetValue('author_id', author_id)
                entity_author.SetValue('name', author_name)
                entity_author.SetValue('dynasty_id', dynasty_id)
                entity_author.SetValue('created_at', now)
                entity_author.SetValue('updated_at', now)
                entity_author.Insert()
                author_count += 1
            except Exception as e:
                print(f'>>>> [error] 插入作者失败 {author_name}: {e}')
                continue

            # --- 插入诗词 ---
            for k, poem in enumerate(poem_list):
                poem_id = f'{author_id}_{k:05d}'
                try:
                    # 处理内容
                    content_lines = poem.get('content', [])
                    content = '\n'.join(content_lines).strip()
                    # 去掉注释数字
                    content = content.replace('[', '').replace(']', '')
                    for n in range(10):
                        content = content.replace(str(n), '')
                    content = content.replace('&nbsp', '')

                    entity_poem.SetValue('poem_id', poem_id)
                    entity_poem.SetValue('title', poem.get('title', '').strip())
                    entity_poem.SetValue('author_id', author_id)
                    entity_poem.SetValue('dynasty_id', dynasty_id)
                    entity_poem.SetValue('content', content)
                    entity_poem.SetValue('description', poem.get('discription', ''))
                    entity_poem.SetValue('paragraphs', content_lines)
                    entity_poem.SetValue('line_count', len(content_lines))
                    entity_poem.SetValue('char_count', len(content.replace('\n', '')))
                    entity_poem.SetValue('created_at', now)
                    entity_poem.SetValue('updated_at', now)
                    entity_poem.SetValue('data_version', '2.0')
                    entity_poem.Insert()
                    poem_count += 1

                    # --- 添加标签 (format → form, genre 默认'诗') ---
                    poem_format = poem.get('format', '').strip()
                    if poem_format:
                        form_id = query_vocab_id('form', poem_format)
                        if form_id:
                            entity_poem_tag.SetValue('poem_id', poem_id)
                            entity_poem_tag.SetValue('vocab_id', form_id)
                            entity_poem_tag.SetValue('tag_type', 'form')
                            entity_poem_tag.Insert()

                    # 默认 genre = '诗'
                    genre_id = query_vocab_id('genre', '诗')
                    if genre_id:
                        entity_poem_tag.SetValue('poem_id', poem_id)
                        entity_poem_tag.SetValue('vocab_id', genre_id)
                        entity_poem_tag.SetValue('tag_type', 'genre')
                        entity_poem_tag.Insert()

                    # review_status = '未审核'
                    status_id = query_vocab_id('review_status', '未审核')
                    if status_id:
                        entity_poem_tag.SetValue('poem_id', poem_id)
                        entity_poem_tag.SetValue('vocab_id', status_id)
                        entity_poem_tag.SetValue('tag_type', 'review_status')
                        entity_poem_tag.Insert()

                except Exception as e:
                    print(f'>>>> [error] 插入诗词失败 {poem.get("title", "?")}: {e}')

            print(f'      {dynasty_name} - {author_name}: {len(poem_list)} 首')

        print(f'  {i+1}. {dynasty_name} 完成')

    print(f'\n>>>> 导入完成: 作者 {author_count} 人, 诗词 {poem_count} 首')


def _load_dynasty_map():
    """加载朝代名 → dynasty_id 映射"""
    json_path = os.path.join(os.path.dirname(__file__), 'data', 'Dynasty.json')
    if not os.path.exists(json_path):
        return {}

    data = json.load(open(json_path, 'r', encoding='utf-8'))['dynasty']
    mapping = {}
    for d in data:
        mapping[d['name']] = d['dynasty_id']
    return mapping


# ============================================================
#  工具函数: 查询
# ============================================================
def query_poems_by_author(author_name):
    """根据作者名查诗词 (使用 JOIN 避免重名问题)"""
    sql = '''
        SELECT p.poem_id, p.title, p.content, a.author_id, a.name
        FROM poem p
        JOIN author a ON p.author_id = a.author_id
        WHERE a.name = ?
    '''
    cursor = Cursor()
    try:
        cursor.execute(sql, (author_name,))
        rows = cursor.fetchall()
        return rows
    except Exception as e:
        print(f'>>>> [error] 查询失败: {e}')
        return []


def query_poems_by_tag(category, label):
    """根据标签查诗词"""
    sql = '''
        SELECT p.poem_id, p.title, a.name
        FROM poem p
        JOIN poem_tag pt ON p.poem_id = pt.poem_id
        JOIN vocab v ON pt.vocab_id = v.vocab_id
        JOIN author a ON p.author_id = a.author_id
        WHERE v.category = ? AND v.label = ?
    '''
    cursor = Cursor()
    try:
        cursor.execute(sql, (category, label))
        return cursor.fetchall()
    except Exception as e:
        print(f'>>>> [error] 查询失败: {e}')
        return []


# ============================================================
#  入口
# ============================================================
if __name__ == '__main__':
    load_poems_from_json()

    # 示例查询
    print('\n===== 查询示例 =====')
    poems = query_poems_by_author('李白')
    print(f'李白: {len(poems)} 首')

    poems_wuyan = query_poems_by_tag('form', '五言绝句')
    print(f'五言绝句: {len(poems_wuyan)} 首')
