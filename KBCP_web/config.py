"""
配置文件 - KBCP 诗词库网站 v2.0
基于新 Schema 的数据库路径
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kbcp-poetry-site-key-2026'

    # DB 指向 dataset/kbcp.db (由 KBCP_RAG_Poetry_DB.py 创建)
    DB_PATH = os.path.join(BASE_DIR, '..', 'dataset', 'kbcp.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
