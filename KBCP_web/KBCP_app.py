"""
Flask 主程序 - KBCP 诗词库 v2.0
基于新 Schema，支持 FK + 中间表 + 归一化 vocab
四栏布局：朝代树 | 诗词列表 | 详情编辑器 | 标签面板
"""
import os
import sys
import json
import datetime
import time

# 将项目根目录加入导入路径（KBCP_DAL.py / KBCP_Assistant.py 等位于父目录）
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from flask import Flask, render_template, request, jsonify, redirect, url_for, session

from Prj_Poetry_China.KBCP_web.KBCP_models import Poem
from config import config
from KBCP_models import db, Dynasty, Author, Poem, Vocab, PoemTag, AuthorTag
from KBCP_auth import init_users_table, authenticate, login_required, admin_required, superadmin_required

from sqlalchemy import text, func

# AI 功能模块
from KBCP_DAL import SQLiteDAL
from KBCP_Assistant import answer_question, warmup as assistant_warmup
from KBCP_Recommend import recommend_by_poem

app = Flask(__name__)
app.config.from_object(config['default'])
db.init_app(app)

# ==================== 辅助函数 ====================

def get_author_count(dynasty_id):
    """获取某朝代的诗人数量 (用于删除前的检查)"""
    return Author.query.filter_by(dynasty_id=dynasty_id).count()


def get_dynasty_name(dynasty_id):
    d = Dynasty.query.get(dynasty_id)
    return d.name if d else ''


def get_author_name(author_id):
    a = Author.query.get(author_id)
    return a.name if a else ''


# ==================== 页面路由 ====================

@app.route('/')
def index():
    """首页 - 诗词浏览"""
    return render_template('KBCP_index.html')


@app.route('/login')
def login():
    return render_template('KBCP_login.html')


@app.route('/chat')
def chat_page():
    """AI 问答页面"""
    return render_template('KBCP_chat.html')


@app.route('/admin')
@admin_required
def admin_page():
    """管理后台"""
    dynasties = Dynasty.query.order_by(Dynasty.start_year).all()
    # 按 category 分组获取 vocab
    vocab_categories = db.session.query(
        Vocab.category, func.count(Vocab.vocab_id)
    ).group_by(Vocab.category).order_by(Vocab.category).all()
    # 标签分类英文 → 中文 映射
    CATEGORY_NAMES = {
        'theme': '主题', 'style': '风格', 'emotion': '情感',
        'imagery': '意象', 'genre': '体裁', 'form': '形式',
        'meter': '格律', 'language_style': '语言风格',
        'season': '季节', 'festival': '节令',
        'review_status': '审核状态', 'allusion': '典故',
    }
    return render_template('KBCP_admin.html',
                           dynasties=dynasties,
                           vocab_categories=vocab_categories,
                           category_names=CATEGORY_NAMES)


@app.route('/admin/users')
@superadmin_required
def admin_users():
    """用户管理"""
    return render_template('KBCP_admin.html', tab='users')


# ==================== 认证 API ====================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    user = authenticate(db, username, password)
    if user:
        session['user_id'] = user['user_id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({'status': 'success', 'user': user})
    return jsonify({'error': '用户名或密码错误'}), 401


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'status': 'success'})


@app.route('/api/me')
def api_me():
    if 'user_id' in session:
        return jsonify({
            'user_id': session['user_id'],
            'username': session['username'],
            'role': session['role'],
        })
    return jsonify({'error': '未登录'}), 401


# ==================== 树控件 API ====================

@app.route('/api/dynasties')
def api_dynasties():
    """朝代树一级节点 — 一次查询获取所有朝代的诗人数量"""
    dynasties = Dynasty.query.order_by(Dynasty.start_year).all()
    # 一次查询: 每个朝代的诗人数量
    author_counts = dict(
        db.session.query(Author.dynasty_id, func.count(Author.author_id))
        .group_by(Author.dynasty_id).all()
    )
    result = []
    for d in dynasties:
        ac = author_counts.get(d.dynasty_id, 0)
        result.append({
            'id': d.dynasty_id,
            'text': f'{d.name} ({ac}人)',
            'type': 'dynasty',
            'data': {'dynasty_name': d.name, 'author_count': ac},
        })
    return jsonify(result)


@app.route('/api/authors/<dynasty_id>')
def api_authors(dynasty_id):
    """作者树二级节点 — 一次聚合查询 替代 N+1"""
    rows = db.session.query(
        Author, func.count(Poem.poem_id).label('poem_count')
    ).outerjoin(Poem, Author.author_id == Poem.author_id)\
     .filter(Author.dynasty_id == dynasty_id)\
     .group_by(Author.author_id)\
     .order_by(Author.author_id).all()

    result = []
    for author, poem_count in rows:
        result.append({
            'id': author.author_id,
            'text': f'{author.name} ({poem_count}首)',
            'type': 'author',
            'data': {
                'author_name': author.name,
                'dynasty_id': author.dynasty_id,
                'poem_count': poem_count,
            },
        })
    return jsonify(result)


@app.route('/api/poems/<author_id>')
def api_poems(author_id):
    """诗词列表"""
    poems = Poem.query.filter_by(author_id=author_id)\
        .order_by(Poem.poem_id).all()
    return jsonify([p.to_simple_dict() for p in poems])


# ==================== 诗词详情 API ====================

@app.route('/api/poem/detail')
def api_poem_detail():
    poem_id = request.args.get('poem_id', '')
    if not poem_id:
        return jsonify({'error': '缺少 poem_id'}), 400

    try:
        poem = Poem.query.get(poem_id)
        #poem.appreciation = poem.description
        if not poem:
            return jsonify({'error': '诗词不存在'}), 404

        author = Author.query.get(poem.author_id)
        dynasty = Dynasty.query.get(poem.dynasty_id)

        tags = PoemTag.query.filter_by(poem_id=poem_id).all()
        tag_list = [t.to_dict() for t in tags]

        return jsonify({
            'poem': poem.to_dict(),
            'author': author.to_dict() if author else None,
            'dynasty_name': dynasty.name if dynasty else '',
            'tags': tag_list,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 标签 API ====================

@app.route('/api/vocab/<category>')
def api_vocab(category):
    """获取某类受控词表"""
    items = Vocab.query.filter_by(category=category)\
        .order_by(Vocab.sort_order).all()
    return jsonify([item.to_dict() for item in items])


@app.route('/api/vocab/categories')
def api_vocab_categories():
    """获取所有 vocab 类别（用于标签选择器）"""
    rows = db.session.query(Vocab.category).distinct().order_by(Vocab.category).all()
    return jsonify([r[0] for r in rows])


@app.route('/api/poem/tags', methods=['GET'])
def api_poem_tags():
    poem_id = request.args.get('poem_id', '')
    if not poem_id:
        return jsonify({'error': '缺少 poem_id'}), 400
    tags = PoemTag.query.filter_by(poem_id=poem_id).all()
    return jsonify([t.to_dict() for t in tags])


@app.route('/api/poem/tag/add', methods=['POST'])
@admin_required
def api_poem_tag_add():
    data = request.json
    poem_id = data.get('poem_id', '')
    vocab_ids = data.get('vocab_ids', [])  # 支持批量

    if not poem_id or not vocab_ids:
        return jsonify({'error': '参数不完整'}), 400

    added = 0
    for vid in vocab_ids:
        # 查 vocab 获取 tag_type
        vocab = Vocab.query.get(vid)
        if not vocab:
            continue
        # 去重
        existing = PoemTag.query.filter_by(
            poem_id=poem_id, vocab_id=vid
        ).first()
        if existing:
            continue
        pt = PoemTag(poem_id=poem_id, vocab_id=vid, tag_type=vocab.category)
        db.session.add(pt)
        added += 1

    db.session.commit()
    return jsonify({'status': 'success', 'added': added})


@app.route('/api/poem/tag/remove', methods=['POST'])
@admin_required
def api_poem_tag_remove():
    data = request.json
    poem_id = data.get('poem_id', '')
    vocab_id = data.get('vocab_id', '')

    tag = PoemTag.query.filter_by(poem_id=poem_id, vocab_id=vocab_id).first()
    if not tag:
        return jsonify({'error': '标签不存在'}), 404

    db.session.delete(tag)
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/api/poem/tag/clear', methods=['POST'])
@admin_required
def api_poem_tag_clear():
    data = request.json
    poem_id = data.get('poem_id', '')

    PoemTag.query.filter_by(poem_id=poem_id).delete()
    db.session.commit()
    return jsonify({'status': 'success'})


# ==================== 诗词 CRUD ====================

@app.route('/api/poem/save', methods=['POST'])
@admin_required
def api_poem_save():
    data = request.json
    poem_id = data.get('poem_id', '')

    poem = Poem.query.get(poem_id)
    if not poem:
        return jsonify({'error': '诗词不存在'}), 404

    # 可编辑字段
    editable = ['content', 'appreciation', 'translation', 'description',
                'background', 'historical_context', 'keywords',
                'places_involved', 'people_involved', 'citation_text', 'aliases']
    for field in editable:
        if field in data:
            setattr(poem, field, data[field])

    poem.updated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/api/poem/add', methods=['POST'])
@admin_required
def api_poem_add():
    data = request.json
    author_id = data.get('author_id', '')
    title = data.get('title', '').strip()

    if not author_id or not title:
        return jsonify({'error': '缺少必填项'}), 400

    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': '作者不存在'}), 400

    # 生成新 poem_id
    last = Poem.query.filter_by(author_id=author_id)\
        .order_by(Poem.poem_id.desc()).first()
    if last:
        parts = last.poem_id.split('_')
        seq = int(parts[-1]) + 1 if len(parts) > 1 else 1
    else:
        seq = 0
    poem_id = f'{author_id}_{seq:05d}'

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    poem = Poem(
        poem_id=poem_id,
        title=title,
        author_id=author_id,
        dynasty_id=author.dynasty_id,
        content=data.get('content', ''),
        appreciation=data.get('appreciation', ''),
        created_at=now,
        updated_at=now,
        data_version='2.0',
    )
    db.session.add(poem)

    # 默认标签: genre='诗', review_status='未审核'
    genre = Vocab.query.filter_by(category='genre', label='诗').first()
    status = Vocab.query.filter_by(category='review_status', label='未审核').first()
    if genre:
        db.session.add(PoemTag(poem_id=poem_id, vocab_id=genre.vocab_id, tag_type='genre'))
    if status:
        db.session.add(PoemTag(poem_id=poem_id, vocab_id=status.vocab_id, tag_type='review_status'))

    db.session.commit()
    return jsonify({'status': 'success', 'poem_id': poem_id})


@app.route('/api/poem/delete', methods=['POST'])
@admin_required
def api_poem_delete():
    data = request.json
    poem_id = data.get('poem_id', '')

    poem = Poem.query.get(poem_id)
    if not poem:
        return jsonify({'error': '诗词不存在'}), 404

    db.session.delete(poem)  # cascade 会自动删除 poem_tag
    db.session.commit()
    return jsonify({'status': 'success'})


# ==================== 作者 CRUD ====================

@app.route('/api/author/<author_id>')
def api_author(author_id):
    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': '作者不存在'}), 404
    return jsonify({'author': author.to_dict()})


@app.route('/api/author/add', methods=['POST'])
@admin_required
def api_author_add():
    data = request.json
    dynasty_id = data.get('dynasty_id', '')
    name = data.get('name', '').strip()

    if not dynasty_id or not name:
        return jsonify({'error': '缺少必填项'}), 400

    dynasty = Dynasty.query.get(dynasty_id)
    if not dynasty:
        return jsonify({'error': '朝代不存在'}), 400

    # 生成 author_id
    last = Author.query.filter_by(dynasty_id=dynasty_id)\
        .order_by(Author.author_id.desc()).first()
    seq = 1
    if last:
        try:
            seq = int(last.author_id.replace(dynasty_id, '')) + 1
        except:
            seq = 1
    author_id = f'{dynasty_id}{seq:04d}'

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    author = Author(
        author_id=author_id,
        name=name,
        dynasty_id=dynasty_id,
        created_at=now,
        updated_at=now,
    )
    db.session.add(author)
    db.session.commit()
    return jsonify({'status': 'success', 'author_id': author_id})


@app.route('/api/author/edit/<author_id>', methods=['POST'])
@admin_required
def api_author_edit(author_id):
    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': '作者不存在'}), 404

    data = request.json
    for field in ['name', 'courtesy_name', 'art_name', 'other_names',
                   'birth_year', 'death_year', 'birth_place', 'bio',
                   'historical_role']:
        if field in data:
            setattr(author, field, data[field])

    author.updated_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/api/author/delete/<author_id>', methods=['POST'])
@admin_required
def api_author_delete(author_id):
    author = Author.query.get(author_id)
    if not author:
        return jsonify({'error': '作者不存在'}), 404

    # 级联删除诗词
    Poem.query.filter_by(author_id=author_id).delete()
    AuthorTag.query.filter_by(author_id=author_id).delete()
    db.session.delete(author)
    db.session.commit()
    return jsonify({'status': 'success'})


# ==================== 朝代 CRUD ====================

@app.route('/api/dynasty/add', methods=['POST'])
@admin_required
def api_dynasty_add():
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': '朝代名不能为空'}), 400

    # 自动生成 dynasty_id
    last = Dynasty.query.order_by(Dynasty.dynasty_id.desc()).first()
    if last:
        try:
            seq = ord(last.dynasty_id[-1]) + 1
        except:
            seq = ord('A')
    else:
        seq = ord('A')
    dynasty_id = chr(seq)

    dynasty = Dynasty(
        dynasty_id=dynasty_id,
        name=name,
        start_year=data.get('start_year'),
        end_year=data.get('end_year'),
        note=data.get('note', ''),
    )
    db.session.add(dynasty)
    db.session.commit()
    return jsonify({'status': 'success', 'dynasty_id': dynasty_id})


@app.route('/api/dynasty/edit/<dynasty_id>', methods=['POST'])
@admin_required
def api_dynasty_edit(dynasty_id):
    dynasty = Dynasty.query.get(dynasty_id)
    if not dynasty:
        return jsonify({'error': '朝代不存在'}), 404

    data = request.json
    for field in ['name', 'another_name', 'start_year', 'end_year', 'note']:
        if field in data:
            setattr(dynasty, field, data[field])

    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/api/dynasty/delete/<dynasty_id>', methods=['POST'])
@admin_required
def api_dynasty_delete(dynasty_id):
    # 检查是否有作者
    if get_author_count(dynasty_id) > 0:
        return jsonify({'error': '该朝代下还有作者，无法删除'}), 400

    dynasty = Dynasty.query.get(dynasty_id)
    if not dynasty:
        return jsonify({'error': '朝代不存在'}), 404

    db.session.delete(dynasty)
    db.session.commit()
    return jsonify({'status': 'success'})


# ==================== 受控词表管理 ====================

@app.route('/api/vocab/add', methods=['POST'])
@admin_required
def api_vocab_add():
    data = request.json
    category = data.get('category', '')
    label = data.get('label', '').strip()

    if not category or not label:
        return jsonify({'error': '参数不完整'}), 400

    # 检查重复
    existing = Vocab.query.filter_by(category=category, label=label).first()
    if existing:
        return jsonify({'error': '该词条已存在'}), 400

    # 生成 vocab_id
    prefix_map = {
        'theme': 'THM', 'style': 'STY', 'emotion': 'EMO', 'imagery': 'IMG',
        'genre': 'GEN', 'form': 'FRM', 'meter': 'MET', 'language_style': 'LGS',
        'season': 'SES', 'festival': 'FES', 'review_status': 'RVS', 'allusion': 'ALU',
    }
    prefix = prefix_map.get(category, 'GEN')
    last = Vocab.query.filter(Vocab.vocab_id.like(f'V-{prefix}-%'))\
        .order_by(Vocab.vocab_id.desc()).first()
    seq = 1
    if last:
        try:
            seq = int(last.vocab_id.split('-')[-1]) + 1
        except:
            seq = 1
    vocab_id = f'V-{prefix}-{seq:03d}'

    max_order = db.session.query(func.max(Vocab.sort_order))\
        .filter_by(category=category).scalar() or 0

    vocab = Vocab(vocab_id=vocab_id, category=category,
                  label=label, sort_order=max_order + 1)
    db.session.add(vocab)
    db.session.commit()
    return jsonify({'status': 'success', 'vocab_id': vocab_id})


@app.route('/api/vocab/delete/<vocab_id>', methods=['POST'])
@admin_required
def api_vocab_delete(vocab_id):
    # 检查是否被引用
    poem_tag_count = PoemTag.query.filter_by(vocab_id=vocab_id).count()
    author_tag_count = AuthorTag.query.filter_by(vocab_id=vocab_id).count()
    if poem_tag_count > 0 or author_tag_count > 0:
        return jsonify({
            'error': f'该词条被 {poem_tag_count + author_tag_count} 个标签引用，请先解除引用'
        }), 400

    vocab = Vocab.query.get(vocab_id)
    if not vocab:
        return jsonify({'error': '词条不存在'}), 404

    db.session.delete(vocab)
    db.session.commit()
    return jsonify({'status': 'success'})


# ==================== 搜索 API ====================

@app.route('/api/search')
def api_search():
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify({'results': []})

    like = f'%{keyword}%'
    poems = Poem.query.filter(
        db.or_(Poem.title.like(like), Poem.content.like(like))
    ).limit(50).all()

    results = []
    for p in poems:
        author_name = get_author_name(p.author_id)
        results.append({
            'type': 'poem',
            'poem_id': p.poem_id,
            'title': p.title,
            'author': author_name,
        })
    return jsonify({'results': results})


# ==================== 统计 API ====================

@app.route('/api/stats')
def api_stats():
    return jsonify({
        'dynasty_count': Dynasty.query.count(),
        'author_count': Author.query.count(),
        'poem_count': Poem.query.count(),
        'vocab_count': Vocab.query.count(),
        'tag_count': PoemTag.query.count(),
    })


# ==================== 用户管理 API (superadmin) ====================

@app.route('/api/users')
@superadmin_required
def api_users():
    rows = db.session.execute(
        text("SELECT user_id, username, role, created_at, updated_at FROM users ORDER BY created_at")
    ).fetchall()
    return jsonify([{
        'user_id': r.user_id, 'username': r.username,
        'role': r.role, 'created_at': r.created_at,
    } for r in rows])


@app.route('/api/user/add', methods=['POST'])
@superadmin_required
def api_user_add():
    from werkzeug.security import generate_password_hash
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400

    # 检查重复
    existing = db.session.execute(
        text("SELECT user_id FROM users WHERE username = :name"),
        {'name': username}
    ).fetchone()
    if existing:
        return jsonify({'error': '用户名已存在'}), 400

    user_id = f'U-{uuid.uuid4().hex[:8].upper()}'
    pwd_hash = generate_password_hash(password)
    now = datetime.datetime.now().isoformat()

    db.session.execute(
        text("INSERT INTO users (user_id, username, password_hash, role, created_at, updated_at) "
             "VALUES (:uid, :uname, :pwd, :role, :now, :now)"),
        {'uid': user_id, 'uname': username, 'pwd': pwd_hash,
         'role': role, 'now': now}
    )
    db.session.commit()
    return jsonify({'status': 'success', 'user_id': user_id})


@app.route('/api/user/delete/<user_id>', methods=['POST'])
@superadmin_required
def api_user_delete(user_id):
    if user_id == session.get('user_id'):
        return jsonify({'error': '不能删除自己'}), 400

    db.session.execute(
        text("DELETE FROM users WHERE user_id = :uid"),
        {'uid': user_id}
    )
    db.session.commit()
    return jsonify({'status': 'success'})



# ==================== AI 功能 API ====================

def _is_useful_answer(a: str) -> bool:
    """判断历史回答是否有效（过滤掉失败/空白/错误提示）"""
    if not a or not a.strip():
        return False
    s = a.strip()
    if s.startswith('（') or s.startswith('所有 LLM') or s.startswith('所有 Agent') or s.startswith('未配置'):
        return False
    return True


@app.route('/api/ai/ask')
def api_ai_ask():
    """RAG 智能问答（带多轮对话记忆）"""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': '缺少问题'}), 400

    # 从 session 读取历史
    history = session.get('chat_history', [])
    if not isinstance(history, list):
        history = []

    try:
        # 清洗并过滤历史：丢弃失败/空回答，避免污染模型上下文
        history_for_ai = []
        import re as _re
        for entry in history:
            a = entry.get('a', '')
            a = _re.sub(r'⏱\s*[\d.]+s', '', a).strip()
            if not _is_useful_answer(a):
                continue  # 跳过失败/空白的历史记录
            history_for_ai.append({
                'q': entry.get('q', ''),
                'a': a,
                'entity': entry.get('entity', ''),
            })

        t0 = time.time()
        answer = answer_question(
            q,
            history=history_for_ai,
            llm_near_synonym=config['default'].LLM_NEAR_SYNONYM,
        )
        elapsed = round(time.time() - t0, 1)

        # 提取本轮实体并存入历史
        from KBCP_AliasMapper import AliasMapper
        mapper = AliasMapper()
        alias_result = mapper.resolve(q)
        entity = ''
        if alias_result.get('matches'):
            for orig, std, etype, eid in alias_result['matches']:
                if etype in ('author', 'poem'):
                    entity = std
                    break

        # 保存到 session 历史（最多保留 10 轮）
        history.append({
            'q': q,
            'a': answer[:500],
            'entity': entity,
        })
        if len(history) > 10:
            history = history[-10:]
        session['chat_history'] = history

        return jsonify({'question': q, 'answer': answer, 'elapsed': elapsed})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai/clear_history')
def api_ai_clear_history():
    """清空当前会话的对话历史"""
    session.pop('chat_history', None)
    return jsonify({'status': 'ok', 'message': '对话历史已清空'})


def _dal_for_ai():
    """创建一个独立 DAL 实例供 AI 路由使用"""
    import os
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', 'dataset', 'kbcp.db')
    return SQLiteDAL(db_path=db_path)


@app.route('/api/ai/recommend')
def api_ai_recommend():
    """语义推荐"""
    poem_id = request.args.get('poem_id', '').strip()
    limit = request.args.get('limit', 10, type=int)
    if not poem_id:
        return jsonify({'error': '缺少 poem_id'}), 400
    dal = _dal_for_ai()
    try:
        recs = recommend_by_poem(dal, poem_id, top_k=limit)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

    poem = Poem.query.get(poem_id)
    current = {'poem_id': poem_id, 'title': poem.title if poem else ''}
    return jsonify({'current': current, 'recommendations': recs})


@app.route('/api/ai/portrait/<author_id>')
def api_ai_portrait(author_id):
    """诗人风格画像"""
    dal = _dal_for_ai()
    try:
        data = dal.get_poet_portrait_data(author_id)
        return jsonify(data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ==================== 启动 ====================

if __name__ == '__main__':
    with app.app_context():
        # 外键支持
        with db.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = ON"))
        # 初始化用户表
        init_users_table(db)

    # 预热 RAG 索引（首次加载模型需要几秒）
    print("[启动] 预热 RAG 索引...")
    import threading
    threading.Thread(target=assistant_warmup, daemon=True).start()

    import sys
    if '--port' in sys.argv:
        port = int(sys.argv[sys.argv.index('--port') + 1])  # 配置文件中是5081，用于持久化运行
        print(f"量身诗词 port: {port}")
    else:
        port = 5082  # 默认端口号，用于调试
    app.run(host='0.0.0.0', port=port, debug=False)

