"""
诗词库网站 - Flask 主程序
支持左侧树形导航 + 中部诗词展示 + 右侧属性表
"""
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, redirect, url_for
from config import config
from models import db, Dynasty, Author, Poem

from RAG_Poetry_DB import GenerateEntity
from RAG_Poem_Schema import *

# 创建Flask应用
app = Flask(__name__)
app.config.from_object(config['default'])

# 初始化数据库
db.init_app(app)


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页 - 诗词展示页面"""
    dynasties = Dynasty.query.order_by(Dynasty.start_year.asc()).all()
    return render_template('index.html', dynasties=dynasties)


@app.route('/manage')
def manage():
    """内容管理页面"""
    dynasties = Dynasty.query.order_by(Dynasty.start_year.asc()).all()
    return render_template('manage.html', dynasties=dynasties)


# ==================== 树控件 API ====================

@app.route('/api/dynasties')
def get_dynasties():
    """获取所有朝代（用于树控件一级节点）"""
    dynasties = Dynasty.query.order_by(Dynasty.start_year.asc()).all()
    return jsonify([{
        'id': d.dynasty_id,
        'name': d.name,
        'type': 'dynasty'
    } for d in dynasties])


@app.route('/api/authors/<dynasty_id>')
def get_authors(dynasty_id):
    """获取某朝代的作者列表（用于树控件二级节点）"""
    authors = Author.query.filter_by(dynasty_id=dynasty_id).order_by(Author.author_id.asc()).all()
    # 获取朝代名称
    dynasty = Dynasty.query.get(dynasty_id)
    dynasty_name = dynasty.name if dynasty else ''
    return jsonify([{
        'id': a.author_id,
        'name': a.name,
        'dynasty_id': a.dynasty_id,
        'dynasty_name': dynasty_name,
        'type': 'author'
    } for a in authors])


@app.route('/api/poems/<author_id>')
def get_poems(author_id):
    """获取某作者的诗词列表（用于树控件三级节点）"""
    # 获取作者信息
    author = Author.query.get(author_id)
    if not author:
        return jsonify([])
    
    # 通过作者名称查询诗词
    poems = Poem.query.filter_by(author=author.name).order_by(Poem.poem_id.asc()).all()
    return jsonify([{
        'poem_id': p.poem_id if p.poem_id else p.title,  # 如果poem_id为空，使用title
        'title': p.title,
        'author': p.author or author.name,
        'type': 'poem'
    } for p in poems])


# ==================== 诗词详情 API ====================

@app.route('/api/poem/detail')
def get_poem():
    """获取诗词详情（通过 ?title= 参数查询，避免URL特殊字符问题）"""
    title = request.args.get('title', '')
    author_name = request.args.get('author', '')  # 可选：限定作者，解决同名诗词问题
    
    if not title:
        return jsonify({'error': '缺少 title 参数'}), 400
    
    # 通过 title 查找诗词（优先带作者限定）
    if author_name:
        poem = Poem.query.filter_by(title=title, author=author_name).first()
    else:
        poem = Poem.query.filter_by(title=title).first()
    
    if not poem:
        return jsonify({'error': '诗词不存在', 'title': title}), 404
    
    # 获取作者信息（通过作者名称匹配）
    author = Author.query.filter_by(name=poem.author).first() if poem.author else None
    
    return jsonify({
        'poem': poem.to_dict(),
        'author': author.to_dict() if author else None
    })


@app.route('/api/poem/save', methods=['POST'])
def save_poem():
    """保存诗词修改（title 从 body 传递，避免 URL 特殊字符问题）"""
    data = request.json
    
    # title 作为唯一标识（从 body 读取）
    title = data.get('title', '')
    author_name = data.get('author_name', '')  # 可选：限定作者
    
    if not title:
        return jsonify({'error': '缺少 title 参数'}), 400
    
    # 使用原生 SQL 更新（避免空字符串主键问题）
    # 如果有作者限定，同时过滤作者
    if author_name:
        update_sql = '''
            UPDATE poem SET 
                content = :content,
                appreciation = :appreciation,
                description = :description,
                translation = :translation,
                background = :background,
                historical_context = :historical_context,
                genre = :genre,
                form = :form,
                meter = :meter,
                theme = :theme,
                style = :style,
                emotion = :emotion,
                imagery = :imagery,
                allusions = :allusions,
                keywords = :keywords,
                season = :season,
                festival = :festival,
                places_involved = :places_involved,
                people_involved = :people_involved,
                updated_at = :updated_at
            WHERE title = :title AND author = :author_name
        '''
    else:
        update_sql = '''
            UPDATE poem SET 
                content = :content,
                appreciation = :appreciation,
                description = :description,
                translation = :translation,
                background = :background,
                historical_context = :historical_context,
                genre = :genre,
                form = :form,
                meter = :meter,
                theme = :theme,
                style = :style,
                emotion = :emotion,
                imagery = :imagery,
                allusions = :allusions,
                keywords = :keywords,
                season = :season,
                festival = :festival,
                places_involved = :places_involved,
                people_involved = :people_involved,
                updated_at = :updated_at
            WHERE title = :title
        '''
    
    params = {
        'title': title,
        'author_name': author_name,
        'content': data.get('content', ''),
        'appreciation': data.get('appreciation', ''),
        'description': data.get('description', ''),
        'translation': data.get('translation', ''),
        'background': data.get('background', ''),
        'historical_context': data.get('historical_context', ''),
        'genre': data.get('genre', ''),
        'form': data.get('form', ''),
        'meter': data.get('meter', ''),
        'theme': data.get('theme', ''),
        'style': data.get('style', ''),
        'emotion': data.get('emotion', ''),
        'imagery': data.get('imagery', ''),
        'allusions': data.get('allusions', ''),
        'keywords': data.get('keywords', ''),
        'season': data.get('season', ''),
        'festival': data.get('festival', ''),
        'places_involved': data.get('places_involved', ''),
        'people_involved': data.get('people_involved', ''),
        'updated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    result = db.session.execute(db.text(update_sql), params)
    db.session.commit()
    
    if result.rowcount == 0:
        return jsonify({'error': '诗词不存在或无更改', 'title': title}), 404
    
    return jsonify({'status': 'success', 'message': '保存成功', 'rows_updated': result.rowcount})


# ==================== 作者管理 API ====================

@app.route('/api/author/<author_id>')
def get_author(author_id):
    """获取作者详情"""
    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': '作者不存在'}), 404
    return jsonify({'author': author.to_dict()})


@app.route('/api/author/add', methods=['POST'])
def add_author():
    """添加新作者"""
    data = request.json
    
    # 计算新作者ID：朝代ID + 本朝最大序号 + 1
    dynasty_id = data.get('dynasty_id')
    dynasty = Dynasty.query.get(dynasty_id)
    if not dynasty:
        return jsonify({'error': '朝代不存在'}), 400
    
    # 获取该朝代最大作者编号
    last_author = Author.query.filter(
        Author.dynasty_id == dynasty_id
    ).order_by(Author.author_id.desc()).first()
    
    if last_author:
        # 提取序号部分并加1
        try:
            last_num = int(last_author.author_id.replace(dynasty_id, ''))
            new_num = last_num + 1
        except:
            new_num = 1
    else:
        new_num = 1
    
    new_author_id = dynasty_id + str(new_num)
    
    new_author = Author(
        author_id=new_author_id,
        name=data.get('name'),
        dynasty=dynasty.name,
        dynasty_id=dynasty_id,
        bio=data.get('bio', ''),
        created_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        updated_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    db.session.add(new_author)
    db.session.commit()
    
    return jsonify({'status': 'success', 'author_id': new_author_id})


@app.route('/api/author/edit/<author_id>', methods=['POST'])
def edit_author(author_id):
    """编辑作者信息"""
    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': '作者不存在'}), 404
    
    data = request.json
    
    author.name = data.get('name', author.name)
    author.courtesy_name = data.get('courtesy_name', author.courtesy_name)
    author.art_name = data.get('art_name', author.art_name)
    author.bio = data.get('bio', author.bio)
    author.style_summary = data.get('style_summary', author.style_summary)
    author.updated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    db.session.commit()
    return jsonify({'status': 'success', 'message': '保存成功'})


@app.route('/api/author/delete/<author_id>', methods=['POST'])
def delete_author(author_id):
    """删除作者（级联删除其所有诗词）"""
    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': '作者不存在'}), 404
    
    # 先删除该作者的所有诗词（通过作者名称匹配）
    Poem.query.filter_by(author=author.name).delete()
    
    # 再删除作者
    db.session.delete(author)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': '删除成功'})


# ==================== 诗词管理 API ====================

@app.route('/api/poem/add', methods=['POST'])
def add_poem():
    """添加新诗词"""
    data = request.json
    
    author_id = data.get('author_id')
    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': '作者不存在'}), 400
    
    # 计算新诗词ID
    last_poem = Poem.query.filter_by(author=author.name).order_by(Poem.poem_id.desc()).first()
    if last_poem:
        try:
            # poem_id 格式：author_id + 序号
            parts = last_poem.poem_id.split(author_id)
            if len(parts) == 2:
                last_num = int(parts[1]) if parts[1] else 1
                new_num = last_num + 1
            else:
                new_num = 1
        except:
            new_num = 1
    else:
        new_num = 1
    
    new_poem_id = author_id + str(new_num)
    
    new_poem = Poem(
        poem_id=new_poem_id,
        title=data.get('title', '无题'),
        author=author.name,
        dynasty=author.dynasty,
        content=data.get('content', ''),
        appreciation=data.get('appreciation', ''),
        created_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        updated_at=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    
    db.session.add(new_poem)
    db.session.commit()
    
    return jsonify({'status': 'success', 'poem_id': new_poem_id})


@app.route('/api/poem/delete', methods=['POST'])
def delete_poem():
    """删除诗词（title 从 body 传递）"""
    data = request.json
    title = data.get('title', '')
    author_name = data.get('author_name', '')
    
    if not title:
        return jsonify({'error': '缺少 title 参数'}), 400
    
    # 通过 title（+作者）查找诗词
    if author_name:
        poem = Poem.query.filter_by(title=title, author=author_name).first()
    else:
        poem = Poem.query.filter_by(title=title).first()
    
    if not poem:
        return jsonify({'error': '诗词不存在'}), 404
    
    db.session.delete(poem)
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': '删除成功'})


# ==================== 搜索 API ====================

@app.route('/api/search')
def search():
    """搜索诗词"""
    keyword = request.args.get('q', '')
    search_type = request.args.get('type', 'poem')  # poem, author, dynasty
    
    if not keyword:
        return jsonify({'results': []})
    
    results = []
    
    if search_type == 'poem':
        poems = Poem.query.filter(
            db.or_(
                Poem.title.like(f'%{keyword}%'),
                Poem.content.like(f'%{keyword}%'),
                Poem.author.like(f'%{keyword}%')
            )
        ).limit(50).all()
        results = [{'type': 'poem', 'id': p.poem_id, 'title': p.title, 'author': p.author} for p in poems]
    
    elif search_type == 'author':
        authors = Author.query.filter(
            db.or_(
                Author.name.like(f'%{keyword}%'),
                Author.bio.like(f'%{keyword}%')
            )
        ).limit(50).all()
        results = [{'type': 'author', 'id': a.author_id, 'name': a.name, 'dynasty': a.dynasty} for a in authors]
    
    return jsonify({'results': results})


# ==================== 统计 API ====================

@app.route('/api/stats')
def get_stats():
    """获取统计数据"""
    dynasty_count = Dynasty.query.count()
    author_count = Author.query.count()
    poem_count = Poem.query.count()
    
    return jsonify({
        'dynasty_count': dynasty_count,
        'author_count': author_count,
        'poem_count': poem_count
    })


# ==================== 启动应用 ====================

if __name__ == '__main__':
    print("=" * 50)
    print("诗词库网站启动中...")
    print(f"数据库: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print("=" * 50)
    # conn = Conn(dbName='./db/kbcp.db')
    #app.run(host='0.0.0.0', port=5001, debug=True)

    import sys
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])  # 配置文件中是5081，用于持久化运行
        print(f"诗词库网站 port: {port}")
    else:
        port = 8080  # 默认端口号，用于调试
    app.run(host='0.0.0.0', port=port, debug=False)

