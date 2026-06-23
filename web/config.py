"""
配置文件 - 诗词库网站
"""
import os

# 获取当前文件所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    """基础配置"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'poetry-site-secret-key-2026'
    DEBUG = True
    
    # 数据库配置 - 使用已有的kbcp.db
    DB_PATH = os.path.join(BASE_DIR, 'db', 'kbcp.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # 分页配置
    ITEMS_PER_PAGE = 20  # 树控件懒加载每页加载数量


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
