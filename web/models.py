"""
数据库模型 - 诗词库网站
基于 kbcp.db 数据库结构
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Dynasty(db.Model):
    """朝代模型"""
    __tablename__ = 'dynasty'
    
    dynasty_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 朝代名称
    another_name = db.Column(db.String(100))  # 别名
    start_year = db.Column(db.Integer)  # 起始年份
    end_year = db.Column(db.Integer)  # 结束年份
    note = db.Column(db.Text)  # 备注
    
    def to_dict(self):
        return {
            'dynasty_id': self.dynasty_id,
            'name': self.name,
            'another_name': self.another_name,
            'start_year': self.start_year,
            'end_year': self.end_year,
            'note': self.note
        }


class Author(db.Model):
    """作者模型"""
    __tablename__ = 'author'
    
    author_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # 姓名
    dynasty = db.Column(db.String(50))  # 朝代名称
    dynasty_id = db.Column(db.String(20))  # 朝代ID
    courtesy_name = db.Column(db.String(100))  # 字
    art_name = db.Column(db.String(100))  # 号
    other_names = db.Column(db.String(200))  # 其他称呼
    birth_year = db.Column(db.Integer)  # 出生年份
    death_year = db.Column(db.Integer)  # 去世年份
    birth_place = db.Column(db.String(200))  # 出生地
    bio = db.Column(db.Text)  # 生平简介
    style_summary = db.Column(db.Text)  # 风格概述
    major_themes = db.Column(db.String(500))  # 主要主题
    common_imagery = db.Column(db.String(500))  # 常见意象
    representative_works = db.Column(db.String(500))  # 代表作品
    representative_poem_ids = db.Column(db.String(500))  # 代表诗词ID
    historical_role = db.Column(db.Text)  # 历史地位
    created_at = db.Column(db.String(50))
    updated_at = db.Column(db.String(50))
    review_status = db.Column(db.String(20))
    
    def to_dict(self):
        return {
            'author_id': self.author_id,
            'name': self.name,
            'dynasty': self.dynasty,
            'dynasty_id': self.dynasty_id,
            'courtesy_name': self.courtesy_name,
            'art_name': self.art_name,
            'birth_year': self.birth_year,
            'death_year': self.death_year,
            'birth_place': self.birth_place,
            'bio': self.bio,
            'style_summary': self.style_summary
        }


class Poem(db.Model):
    """诗词模型"""
    __tablename__ = 'poem'
    
    poem_id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200), nullable=False)  # 标题
    author = db.Column(db.String(100))  # 作者名称
    dynasty = db.Column(db.String(50))  # 朝代名称
    content = db.Column(db.Text)  # 正文
    paragraphs = db.Column(db.String(1000))  # 段落
    sentences = db.Column(db.String(2000))  # 句子
    line_count = db.Column(db.Integer)  # 行数
    char_count = db.Column(db.Integer)  # 字符数
    genre = db.Column(db.String(50))  # 体裁
    form = db.Column(db.String(50))  # 形式
    meter = db.Column(db.String(100))  # 韵律
    language_style = db.Column(db.String(100))  # 语言风格
    description = db.Column(db.Text)  # 描述
    translation = db.Column(db.Text)  # 翻译
    appreciation = db.Column(db.Text)  # 赏析
    background = db.Column(db.Text)  # 背景
    historical_context = db.Column(db.Text)  # 历史背景
    theme = db.Column(db.String(200))  # 主题
    style = db.Column(db.String(100))  # 风格
    emotion = db.Column(db.String(200))  # 情感
    imagery = db.Column(db.String(500))  # 意象
    allusions = db.Column(db.String(500))  # 用典
    keywords = db.Column(db.String(500))  # 关键词
    season = db.Column(db.String(50))  # 季节
    festival = db.Column(db.String(100))  # 节日
    places_involved = db.Column(db.String(500))  # 涉及地点
    people_involved = db.Column(db.String(500))  # 涉及人物
    citation_text = db.Column(db.Text)  # 引用文本
    aliases = db.Column(db.String(200))  # 别名
    related_poem_ids = db.Column(db.String(500))  # 相关诗词ID
    created_at = db.Column(db.String(50))
    updated_at = db.Column(db.String(50))
    data_version = db.Column(db.String(20))
    review_status = db.Column(db.String(20))
    
    def to_dict(self):
        """转换为字典，包含所有可编辑字段"""
        return {
            'poem_id': self.poem_id,
            'title': self.title,
            'author': self.author,
            'dynasty': self.dynasty,
            'content': self.content or '',
            'paragraphs': self.paragraphs or '',
            'line_count': self.line_count,
            'char_count': self.char_count,
            'genre': self.genre or '',
            'form': self.form or '',
            'meter': self.meter or '',
            'language_style': self.language_style or '',
            'description': self.description or '',
            'translation': self.translation or '',
            'appreciation': self.appreciation or '',
            'background': self.background or '',
            'historical_context': self.historical_context or '',
            'theme': self.theme or '',
            'style': self.style or '',
            'emotion': self.emotion or '',
            'imagery': self.imagery or '',
            'allusions': self.allusions or '',
            'keywords': self.keywords or '',
            'season': self.season or '',
            'festival': self.festival or '',
            'places_involved': self.places_involved or '',
            'people_involved': self.people_involved or '',
            'citation_text': self.citation_text or '',
            'aliases': self.aliases or '',
            'related_poem_ids': self.related_poem_ids or ''
        }
    
    def to_simple_dict(self):
        """简化为树控件使用的字典"""
        return {
            'poem_id': self.poem_id,
            'title': self.title
        }
