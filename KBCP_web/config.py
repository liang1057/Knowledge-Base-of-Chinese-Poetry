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

    # Agent 中枢：是否让 LLM 参与主题词近义扩展
    #   True  = 主题查询（如"思乡的诗"）时，LLM 将主题词扩展为近义标签集合再召回
    #   False = 仅用 vocab 表做确定性映射（如 月亮→月），不额外调用 LLM
    # CLI 模式读不到本配置时，会回退读取 KBCP_LLM_config.ini 的 [agent].llm_near_synonym
    LLM_NEAR_SYNONYM = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
