# -*- coding: utf-8 -*-
# @Time    : 2026/06/23
# @Author  : Leon
# @Email   : liang1057@163.com
# @File    : KBCP_RAG_Poem_Schema.py
# @Project : 中华诗词知识库 Knowledge Base of Chinese Poetry (KBCP)
# @Description: 重构后的 Schema 定义 - v2.0
#   改进:
#     1. 所有跨表引用改为 FK (author_id, dynasty_id)
#     2. 单值/多值标签统一剥离到 poem_tag / author_tag 中间表
#     3. vocab 表归一化为单条记录
#     4. myschema 表保持不变

from data_entity import *
from opencc import OpenCC

sc2tc = OpenCC('s2t')
tc2sc = OpenCC('t2s')


# ============================================================
#  增强基类：支持外键 + 复合主键
# ============================================================
class KBCP_EntityBase(EntityBase):
    def __init__(self):
        super().__init__()
        self._foreign_keys = []     # [{col, ref_table, ref_col, on_delete, on_update}]
        self._composite_pk = []     # [col1, col2, ...]

    def AddFK(self, col, ref_table, ref_col, on_delete=None, on_update=None):
        self._foreign_keys.append({
            'col': col,
            'ref_table': ref_table,
            'ref_col': ref_col,
            'on_delete': on_delete,
            'on_update': on_update,
        })

    def SetCompositePK(self, cols):
        self._composite_pk = cols

    def GET_SQL_Create_Table(self):
        col_defs = []
        pk_single = self._composite_pk[0] if len(self._composite_pk) == 1 else None

        for i, name in enumerate(self.col_name):
            line = f"  {name} {self.col_type[i]}"
            if name == pk_single:
                line += " PRIMARY KEY"
            col_defs.append(line)

        for fk in self._foreign_keys:
            line = f"  FOREIGN KEY ({fk['col']}) REFERENCES {fk['ref_table']}({fk['ref_col']})"
            if fk.get('on_delete'):
                line += f" ON DELETE {fk['on_delete']}"
            if fk.get('on_update'):
                line += f" ON UPDATE {fk['on_update']}"
            col_defs.append(line)

        if len(self._composite_pk) > 1:
            col_defs.append(f"  PRIMARY KEY ({', '.join(self._composite_pk)})")

        return "CREATE TABLE IF NOT EXISTS {} (\n{}\n)".format(
            self.table_name, ',\n'.join(col_defs)
        )


# ============================================================
#  1. 朝代表 (不变)
# ============================================================
class table_dynasty(KBCP_EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('dynasty')
        self.SetCompositePK(['dynasty_id'])
        self.AddColumn(colName='dynasty_id', colType='text', colLabel='朝代唯一编号')
        self.AddColumn(colName='name', colType='text', colLabel='标准朝代名')
        self.AddColumn(colName='another_name', colType='varchar', colLabel='别名')
        self.AddColumn(colName='start_year', colType='int', colLabel='朝代起始年')
        self.AddColumn(colName='end_year', colType='int', colLabel='朝代结束年')
        self.AddColumn(colName='note', colType='text', colLabel='说明')


# ============================================================
#  2. 作者表 (精简 + FK)
#    移除: dynasty(文本朝代名), style_summary, major_themes,
#          common_imagery, review_status
#    这些字段分别由 dynasty_id FK 和 author_tag 中间表替代
# ============================================================
class table_author(KBCP_EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('author')
        self.SetCompositePK(['author_id'])

        # 基础信息
        self.AddColumn(colName='author_id', colType='text', colLabel='诗人唯一编号')
        self.AddColumn(colName='name', colType='text', colLabel='标准姓名')
        self.AddColumn(colName='dynasty_id', colType='text', colLabel='朝代唯一编号')
        self.AddFK('dynasty_id', 'dynasty', 'dynasty_id')

        # 别名体系
        self.AddColumn(colName='courtesy_name', colType='text', colLabel='字')
        self.AddColumn(colName='art_name', colType='varchar', colLabel='号')
        self.AddColumn(colName='other_names', colType='varchar', colLabel='别名/异名')

        # 生平信息
        self.AddColumn(colName='birth_year', colType='int', colLabel='出生年')
        self.AddColumn(colName='death_year', colType='int', colLabel='卒年')
        self.AddColumn(colName='birth_place', colType='text', colLabel='籍贯/出生地')
        self.AddColumn(colName='bio', colType='text', colLabel='生平简介')
        self.AddColumn(colName='historical_role', colType='text', colLabel='文学史定位')

        # 代表作
        self.AddColumn(colName='representative_works', colType='varchar', colLabel='代表作品标题列表')
        self.AddColumn(colName='representative_poem_ids', colType='varchar', colLabel='代表作品ID列表')

        # 管理字段
        self.AddColumn(colName='created_at', colType='text', colLabel='建立时间')
        self.AddColumn(colName='updated_at', colType='text', colLabel='更新时间')


# ============================================================
#  3. 诗词表 (大幅精简 + FK)
#    移除: author(文本), dynasty(文本  →  由 FK 替代)
#    移除所有标签字段 (genre / form / meter / language_style / theme / style
#         / emotion / imagery / allusions / season / festival / review_status)
#         → 由 poem_tag 中间表替代
# ============================================================
class table_poem(KBCP_EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('poem')
        self.SetCompositePK(['poem_id'])

        # 基础
        self.AddColumn(colName='poem_id', colType='text', colLabel='作品唯一编号')
        self.AddColumn(colName='title', colType='text', colLabel='作品标题')
        self.AddColumn(colName='author_id', colType='text', colLabel='作者唯一编号')
        self.AddColumn(colName='dynasty_id', colType='text', colLabel='朝代唯一编号')

        # FK
        self.AddFK('author_id', 'author', 'author_id')
        self.AddFK('dynasty_id', 'dynasty', 'dynasty_id')

        # 结构化内容
        self.AddColumn(colName='content', colType='text', colLabel='作品全文')
        self.AddColumn(colName='paragraphs', colType='varchar', colLabel='按段落或联切分后的文本')
        self.AddColumn(colName='sentences', colType='varchar', colLabel='按句切分后的最小句单元')
        self.AddColumn(colName='line_count', colType='int', colLabel='行数/句数统计')
        self.AddColumn(colName='char_count', colType='int', colLabel='正文字数统计')

        # 扩展信息
        self.AddColumn(colName='description', colType='text', colLabel='客观简介')
        self.AddColumn(colName='translation', colType='text', colLabel='白话释义')
        self.AddColumn(colName='appreciation', colType='text', colLabel='赏析文本')
        self.AddColumn(colName='background', colType='text', colLabel='创作背景')
        self.AddColumn(colName='historical_context', colType='text', colLabel='历史语境说明')

        # 非受控检索字段 (保留作文本 JSON 数组)
        self.AddColumn(colName='keywords', colType='varchar', colLabel='检索关键词')
        self.AddColumn(colName='places_involved', colType='varchar', colLabel='涉及地点')
        self.AddColumn(colName='people_involved', colType='varchar', colLabel='涉及人物')
        self.AddColumn(colName='citation_text', colType='text', colLabel='标准引用文本')
        self.AddColumn(colName='aliases', colType='varchar', colLabel='别名/异名')
        self.AddColumn(colName='related_poem_ids', colType='varchar', colLabel='相关作品ID')

        # 管理字段
        self.AddColumn(colName='created_at', colType='text', colLabel='建立时间')
        self.AddColumn(colName='updated_at', colType='text', colLabel='更新时间')
        self.AddColumn(colName='data_version', colType='text', colLabel='数据版本号')


# ============================================================
#  4. 受控词表 (归一化: 每条记录一个词条)
#    旧结构: {vocab_id, name, key, value(JSON数组)}
#    新结构: {vocab_id, category, label, sort_order}
#      - category: 类别键, 如 'theme' / 'style' / 'genre' / 'form' / 'review_status'
#      - label:    中文显示名, 如 '豪放'、'五言绝句'、'未审核'
#      - sort_order: 排序序号 (可选)
# ============================================================
class table_vocab(KBCP_EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('vocab')
        self.SetCompositePK(['vocab_id'])

        self.AddColumn(colName='vocab_id', colType='text', colLabel='词汇唯一编号')
        self.AddColumn(colName='category', colType='text', colLabel='词汇类目键值')
        self.AddColumn(colName='label', colType='text', colLabel='词汇中文名')
        self.AddColumn(colName='sort_order', colType='int', colLabel='排序序号')


# ============================================================
#  5. 诗词标签中间表 (统一处理单值 + 多值标签)
#    覆盖: genre / form / meter / language_style / season / festival
#         theme / style / emotion / imagery / allusion / review_status
#    PK(poem_id, vocab_id) 保证同一标签不会被重复添加
# ============================================================
class table_poem_tag(KBCP_EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('poem_tag')
        self.SetCompositePK(['poem_id', 'vocab_id'])

        self.AddColumn(colName='poem_id', colType='text', colLabel='作品唯一编号')
        self.AddColumn(colName='vocab_id', colType='text', colLabel='词汇唯一编号')
        self.AddColumn(colName='tag_type', colType='text', colLabel='标签类别(冗余)')

        self.AddFK('poem_id', 'poem', 'poem_id', on_delete='CASCADE')
        self.AddFK('vocab_id', 'vocab', 'vocab_id')


# ============================================================
#  6. 作者标签中间表
#    覆盖: style_summary / major_theme / common_imagery / review_status
# ============================================================
class table_author_tag(KBCP_EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('author_tag')
        self.SetCompositePK(['author_id', 'vocab_id'])

        self.AddColumn(colName='author_id', colType='text', colLabel='诗人唯一编号')
        self.AddColumn(colName='vocab_id', colType='text', colLabel='词汇唯一编号')
        self.AddColumn(colName='tag_type', colType='text', colLabel='标签类别(冗余)')

        self.AddFK('author_id', 'author', 'author_id', on_delete='CASCADE')
        self.AddFK('vocab_id', 'vocab', 'vocab_id')


# ============================================================
#  7. 元数据记录表 (不变)
# ============================================================
class table_myschema(EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('myschema')
        tname = ['schema_id', 'table_name', 'column_label', 'column_name', 'type']
        tlabel = ['Schema唯一编号', '表名', '标准字段中文名', '标准字段键名', '类型']
        ttype = ['text', 'text', 'text', 'text', 'text']
        self.AddColumns(colNames=tname, colTypes=ttype, colLabels=tlabel)
