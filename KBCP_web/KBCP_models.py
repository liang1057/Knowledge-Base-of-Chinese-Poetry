"""
SQLAlchemy ORM 模型 - KBCP 诗词库 v2.0
映射新 Schema 的 7 张表 + 用户表(通过 raw SQL 创建)
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ==================== 朝代 ====================
class Dynasty(db.Model):
    __tablename__ = 'dynasty'

    dynasty_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    another_name = db.Column(db.String(200))
    start_year = db.Column(db.Integer)
    end_year = db.Column(db.Integer)
    note = db.Column(db.Text)

    authors = db.relationship('Author', backref='dynasty_ref', lazy='dynamic')

    def to_dict(self):
        return {
            'dynasty_id': self.dynasty_id,
            'name': self.name,
            'another_name': self.another_name or '',
            'start_year': self.start_year,
            'end_year': self.end_year,
            'note': self.note or '',
        }


# ==================== 作者 ====================
class Author(db.Model):
    __tablename__ = 'author'

    author_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    dynasty_id = db.Column(db.String(50), db.ForeignKey('dynasty.dynasty_id'))
    courtesy_name = db.Column(db.String(100))
    art_name = db.Column(db.String(200))
    other_names = db.Column(db.String(200))
    birth_year = db.Column(db.Integer)
    death_year = db.Column(db.Integer)
    birth_place = db.Column(db.String(200))
    bio = db.Column(db.Text)
    historical_role = db.Column(db.Text)
    representative_works = db.Column(db.String(500))
    representative_poem_ids = db.Column(db.String(500))
    created_at = db.Column(db.String(50))
    updated_at = db.Column(db.String(50))

    poems = db.relationship('Poem', backref='author_ref', lazy='dynamic')

    def to_dict(self):
        return {
            'author_id': self.author_id,
            'name': self.name,
            'dynasty_id': self.dynasty_id,
            'courtesy_name': self.courtesy_name or '',
            'art_name': self.art_name or '',
            'other_names': self.other_names or '',
            'birth_year': self.birth_year,
            'death_year': self.death_year,
            'birth_place': self.birth_place or '',
            'bio': self.bio or '',
            'historical_role': self.historical_role or '',
            'representative_works': self.representative_works or '',
            'representative_poem_ids': self.representative_poem_ids or '',
            'created_at': self.created_at or '',
            'updated_at': self.updated_at or '',
        }


# ==================== 诗词 ====================
class Poem(db.Model):
    __tablename__ = 'poem'

    poem_id = db.Column(db.String(50), primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    author_id = db.Column(db.String(50), db.ForeignKey('author.author_id'))
    dynasty_id = db.Column(db.String(50), db.ForeignKey('dynasty.dynasty_id'))
    content = db.Column(db.Text)
    paragraphs = db.Column(db.String(1000))
    sentences = db.Column(db.String(2000))
    line_count = db.Column(db.Integer)
    char_count = db.Column(db.Integer)
    description = db.Column(db.Text)
    translation = db.Column(db.Text)
    appreciation = db.Column(db.Text)
    background = db.Column(db.Text)
    historical_context = db.Column(db.Text)
    keywords = db.Column(db.String(500))
    places_involved = db.Column(db.String(500))
    people_involved = db.Column(db.String(500))
    citation_text = db.Column(db.Text)
    aliases = db.Column(db.String(200))
    related_poem_ids = db.Column(db.String(500))
    created_at = db.Column(db.String(50))
    updated_at = db.Column(db.String(50))
    data_version = db.Column(db.String(20))

    tags = db.relationship('PoemTag', backref='poem_ref', lazy='dynamic',
                           cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'poem_id': self.poem_id,
            'title': self.title,
            'author_id': self.author_id,
            'dynasty_id': self.dynasty_id,
            'content': self.content or '',
            'paragraphs': self.paragraphs or '',
            'sentences': self.sentences or '',
            'line_count': self.line_count,
            'char_count': self.char_count,
            'description': self.description or '',
            'translation': self.translation or '',
            'appreciation': self.appreciation or '',
            'background': self.background or '',
            'historical_context': self.historical_context or '',
            'keywords': self.keywords or '',
            'places_involved': self.places_involved or '',
            'people_involved': self.people_involved or '',
            'citation_text': self.citation_text or '',
            'aliases': self.aliases or '',
            'related_poem_ids': self.related_poem_ids or '',
            'created_at': self.created_at or '',
            'updated_at': self.updated_at or '',
            'data_version': self.data_version or '',
        }

    def to_simple_dict(self):
        return {'poem_id': self.poem_id, 'title': self.title}


# ==================== 受控词表 ====================
class Vocab(db.Model):
    __tablename__ = 'vocab'

    vocab_id = db.Column(db.String(50), primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    label = db.Column(db.String(100), nullable=False)
    sort_order = db.Column(db.Integer)

    def to_dict(self):
        return {
            'vocab_id': self.vocab_id,
            'category': self.category,
            'label': self.label,
            'sort_order': self.sort_order,
        }


# ==================== 诗词标签中间表 ====================
class PoemTag(db.Model):
    __tablename__ = 'poem_tag'
    __table_args__ = (
        db.PrimaryKeyConstraint('poem_id', 'vocab_id'),
    )

    poem_id = db.Column(db.String(50), db.ForeignKey('poem.poem_id'))
    vocab_id = db.Column(db.String(50), db.ForeignKey('vocab.vocab_id'))
    tag_type = db.Column(db.String(50), nullable=False)

    vocab = db.relationship('Vocab', lazy='joined')

    def to_dict(self):
        return {
            'poem_id': self.poem_id,
            'vocab_id': self.vocab_id,
            'tag_type': self.tag_type,
            'label': self.vocab.label if self.vocab else '',
            'category': self.vocab.category if self.vocab else '',
        }


# ==================== 作者标签中间表 ====================
class AuthorTag(db.Model):
    __tablename__ = 'author_tag'
    __table_args__ = (
        db.PrimaryKeyConstraint('author_id', 'vocab_id'),
    )

    author_id = db.Column(db.String(50), db.ForeignKey('author.author_id'))
    vocab_id = db.Column(db.String(50), db.ForeignKey('vocab.vocab_id'))
    tag_type = db.Column(db.String(50), nullable=False)

    vocab = db.relationship('Vocab', lazy='joined')

    def to_dict(self):
        return {
            'author_id': self.author_id,
            'vocab_id': self.vocab_id,
            'tag_type': self.tag_type,
            'label': self.vocab.label if self.vocab else '',
            'category': self.vocab.category if self.vocab else '',
        }
