# -*- coding: utf-8 -*-
# @Time    : 2026/04/16
# @Author  : Leon
# @Email   : liang1057@163.com
# @File    : RAG_Poem_Schema.py
# @Project : 中华诗词知识库 Knowledge Base of Chinese Poetry (KBCP)
# @Description: Define the schema for the RAG model.
# @Reference: https://github.com/liang1057/Knowledge-Base-of-Chinese-Poetry
# @Update:   Leon 2026/04/17
# @Version: 0.0.1

'''

'''

from importlib import import_module
from data_entity import *
from opencc import OpenCC
sc2tc = OpenCC('s2t')  # 简体转繁体
tc2sc = OpenCC('t2s')  # 繁体转简体

# 诗词表
class table_poem(EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('poem')

        # 基础信息
        self.AddColumn(colName='poem_id', colType='text', colLabel='作品唯一编号')   # 建议使用'朝代唯一编号-作者唯一编号-诗词编号'如'A-12345-678901'
        self.AddColumn(colName='title', colType='text', colLabel='作品标题')        # 去除首尾空格；保留规范标题；不能为空字符串
        self.AddColumn(colName='author', colType='text', colLabel='作者姓名')       # 使用标准作者名，不使用别名乱写
        self.AddColumn(colName='dynasty', colType='text', colLabel='朝代唯一编号')  # 必须能对应到 dynasty 对象

        # 结构化内容
        self.AddColumn(colName='content', colType='text', colLabel='作品全文')    # 只存正文，不混入注释、网站说明、目录等
        self.AddColumn(colName='paragraphs', colType='varchar', colLabel='按段落或联切分后的文本')  # 比如词的上下阙。没有分段的，也要写上全文。否则编程繁琐
        self.AddColumn(colName='sentences', colType='varchar', colLabel='按句切分后的最小句单元') # 按行切分和按句切分
        self.AddColumn(colName='line_count', colType='int', colLabel='行数/句数统计')  # 统计行数或句数，全库规则统一
        self.AddColumn(colName='char_count', colType='int', colLabel='正文字数统计')  # 统计正文汉字数，可不含标点；全库规则统一

        # 文学属性
        self.AddColumn(colName='genre', colType='text', colLabel='大类体裁')   # 必须能对应到 vocab 对象，`诗`、`词`、`曲`、`赋`、`其他`
        self.AddColumn(colName='form', colType='varchar', colLabel='具体形式') # 必须能对应到 vocab 对象，如`五言绝句`、`七言绝句`、`七言律诗`、`七言长诗`、`词牌名`、`曲牌名`、`赋体名`、`其他`
        self.AddColumn(colName='meter', colType='text', colLabel='格式说明/格律补充') # 必须能对应到 vocab 对象，如`平水韵`、`中华新韵`、`其他`
        self.AddColumn(colName='language_style', colType='text', colLabel='语言风格类型') # 必须能对应到 vocab 对象，如`典雅`、`豪放`、`婉约`、`幽默`、`讽刺`、`其他`

        # 扩展信息
        self.AddColumn(colName='description', colType='text', colLabel='客观简介') # 建议 50–120 字，概括内容、主题、情感，不写太主观
        self.AddColumn(colName='translation', colType='text', colLabel='白话释义') # 用现代汉语解释原意
        self.AddColumn(colName='appreciation', colType='text', colLabel='赏析文本') # 如赏析、评注、解读、注释等
        self.AddColumn(colName='background', colType='text', colLabel='创作背景')   # 写作背景、情境、时代背景；不确定时可空
        self.AddColumn(colName='historical_context', colType='text', colLabel='历史语境说明') # 更偏学术背景说明， 暂时为空

        # 知识增强与标签体系
        self.AddColumn(colName='theme', colType='varchar', colLabel='主题标签')  # 必须能对应到 vocab 对象，如`山水`、`田园`、`爱情`、`离别`、`咏史`、`咏物`、`咏怀`、`其他`
        self.AddColumn(colName='style', colType='varchar', colLabel='风格标签')  # 必须能对应到 vocab 对象，如`豪放`、`婉约`、`幽默`、`讽刺`、`典雅`、`其他`
        self.AddColumn(colName='emotion', colType='varchar', colLabel='情感标签') # 必须能对应到 vocab 对象，如`喜悦`、`哀愁`、`愤怒`、`悲伤`、`其他`
        self.AddColumn(colName='imagery', colType='varchar', colLabel='意象标签') # 必须能对应到 vocab 对象，如`["月","霜"]`
        self.AddColumn(colName='allusions', colType='varchar', colLabel='典故标签/典故项')  # 可先存典故名，后续再扩展为对象， 暂时为空

        # 检索优化
        self.AddColumn(colName='keywords', colType='varchar', colLabel='检索关键词') # 可由规则+模型生成，控制在 0~10 个
        self.AddColumn(colName='season', colType='text', colLabel='季节标签')  # 必须能对应到 vocab 对象，如`春`、`夏`、`秋`、`冬`、`其他`
        self.AddColumn(colName='festival', colType='text', colLabel='节令标签')  # 必须能对应到 vocab 对象，如`春节`、`中秋节`、`端午节`、`其他`
        self.AddColumn(colName='places_involved', colType='varchar', colLabel='涉及地点') # 比如山水、城市、乡村、寺庙、园林、其他
        self.AddColumn(colName='people_involved', colType='varchar', colLabel='涉及人物') # 如诗人、历史人物、神话人物、其他

        # RAG相关字段
        # 下面这些内容，暂时不做，未来需要思考是单独做一个表还是用其他方式来做，也可能需要存入向量库更合适。
        # self.AddColumn(colName='related', colType='varchar', colLabel='相关作品')  #
        # self.AddColumn(colName='similar', colType='varchar', colLabel='相似作品')  #
        # self.AddColumn(colName='related_author', colType='varchar', colLabel='相关作者')  #
        # self.AddColumn(colName='related_dynasty', colType='varchar', colLabel='相关朝代')  #
        # self.AddColumn(colName='related_genre', colType='varchar', colLabel='相关体裁')  #
        # self.AddColumn(colName='related_form', colType='varchar', colLabel='相关形式')  #
        # self.AddColumn(colName='related_meter', colType='varchar', colLabel='相关格式')  #
        self.AddColumn(colName='citation_text', colType='text', colLabel='标准引用文本')  # 建议引用原文，保留标点符号
        self.AddColumn(colName='aliases', colType='varchar', colLabel='别名/异名')  # 比如作品名、作者名、朝代名、其他
        self.AddColumn(colName='related_poem_ids', colType='varchar', colLabel='相关作品ID')  # 比如作品名、作者名、朝代名、其他


        # 管理字段
        self.AddColumn(colName='created_at', colType='text', colLabel='建立时间')
        self.AddColumn(colName='updated_at', colType='text', colLabel='更新时间')
        self.AddColumn(colName='data_version', colType='text', colLabel='数据版本号') # 暂时为空，每个版本的数据格式有所不同，如果有必要需要在md文件或版本文件中记录。
        self.AddColumn(colName='review_status', colType='text', colLabel='审核状态')  # 必须能对应到 vocab 对象，暂时为空，需要审核的，可以在这里标注一下，方便后续审核。

# 作者表
class table_author(EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('author')
        # 基础信息
        self.AddColumn(colName='author_id', colType='text', colLabel='诗人唯一编号') # 全库唯一
        self.AddColumn(colName='name', colType='text', colLabel='标准姓名')         # 可以重名，但应使用标准名，不能用别号
        self.AddColumn(colName='dynasty', colType='text', colLabel='所属朝代')      # 必须能对应到 dynasty 对象，如`唐`、`宋`
        self.AddColumn(colName='dynasty_id', colType='text', colLabel='朝代唯一编号') # 必须能对应到 dynasty 对象，如`T`、`S`

        # 别名体系
        self.AddColumn(colName='courtesy_name', colType='text', colLabel='字')
        self.AddColumn(colName='art_name', colType='varchar', colLabel='号')   # 可以有多个， 如['东坡居士']
        self.AddColumn(colName='other_names', colType='varchar', colLabel='别名/异名')  # 如 ['苏东坡', '苏轼', '苏子瞻']

        # 生平信息
        self.AddColumn(colName='birth_year', colType='int', colLabel='出生年')
        self.AddColumn(colName='death_year', colType='int', colLabel='卒年')
        self.AddColumn(colName='birth_place', colType='text', colLabel='籍贯/出生地')
        self.AddColumn(colName='bio', colType='text', colLabel='生平简介')

        # 文学特征
        self.AddColumn(colName='style_summary', colType='varchar', colLabel='风格概括') # 来自 style 词表
        self.AddColumn(colName='major_themes', colType='varchar', colLabel='常见主题')  # 来自 style 词表
        self.AddColumn(colName='common_imagery', colType='varchar', colLabel='常见意象') # 来自 style 词表
        self.AddColumn(colName='representative_works', colType='varchar', colLabel='代表作品标题列表')
        self.AddColumn(colName='representative_poem_ids', colType='varchar', colLabel='代表作品ID列表')
        self.AddColumn(colName='historical_role', colType='text', colLabel='文学史定位') # 如“盛唐浪漫主义代表诗人”，这个可以为空

        # 管理字段
        self.AddColumn(colName='created_at', colType='text', colLabel='建立时间')
        self.AddColumn(colName='updated_at', colType='text', colLabel='更新时间')
        self.AddColumn(colName='review_status', colType='text', colLabel='审核状态')

# 朝代表
class table_dynasty(EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('dynasty')
        # 基础信息
        self.AddColumn(colName='dynasty_id', colType='text', colLabel='朝代唯一编号') # 如 'A'
        self.AddColumn(colName='name', colType='text', colLabel='标准朝代名')   # '先秦' 【注意】，这里是用于诗词的
        self.AddColumn(colName='another_name', colType='varchar', colLabel='别名') # 如['夏','商', '周', '东周', '西周','春秋','战国' ]
        self.AddColumn(colName='start_year', colType='int', colLabel='朝代起始年')
        self.AddColumn(colName='end_year', colType='int', colLabel='朝代结束年')
        self.AddColumn(colName='note', colType='text', colLabel='说明')


# 词汇表
class table_vocab(EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('vocab')
        # 词汇体系
        self.AddColumn(colName='vocab_id', colType='text', colLabel='词汇唯一编号')
        self.AddColumn(colName='name', colType='text', colLabel='标准词汇类目名')
        self.AddColumn(colName='key', colType='text', colLabel='标准词汇类目键值')
        self.AddColumn(colName='value', colType='text', colLabel='内容')

# 元数据记录表
class table_myschema(EntityBase):
    def __init__(self):
        super().__init__()
        self.SetTableName('myschema')
        tname = ['schema_id', 'table_name', 'column_label', 'column_name', 'type']
        tlabel = ['Schema唯一编号', '表名', '标准字段中文名', '标准字段键名', '类型']
        ttype = ['text', 'text', 'text', 'text', 'text']
        self.AddColumns(colNames=tname, colTypes=ttype, colLabels=tlabel)




