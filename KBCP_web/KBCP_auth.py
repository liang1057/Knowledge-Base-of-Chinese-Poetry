"""
认证模块 - KBCP 诗词库 v2.0
基于 Flask session + 用户表（raw SQL）
"""
import uuid
import datetime
from functools import wraps
from flask import session, request, jsonify, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text


def init_users_table(db):
    """确保 users 表存在，首次运行时创建默认 superadmin"""
    with db.engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT,
                updated_at TEXT
            )
        """))
        result = conn.execute(text("SELECT COUNT(*) FROM users"))
        if result.scalar() == 0:
            pwd = generate_password_hash('admin123')
            now = datetime.datetime.now().isoformat()
            conn.execute(
                text("INSERT INTO users (user_id, username, password_hash, role, created_at, updated_at) "
                     "VALUES (:uid, :uname, :pwd, :role, :now, :now)"),
                {'uid': 'U-00001', 'uname': 'admin', 'pwd': pwd,
                 'role': 'superadmin', 'now': now}
            )
        conn.commit()


def authenticate(db, username, password):
    """验证登录，成功返回用户 dict，失败返回 None"""
    result = db.session.execute(
        text("SELECT user_id, username, password_hash, role FROM users WHERE username = :name"),
        {'name': username}
    ).fetchone()
    if result and check_password_hash(result.password_hash, password):
        return {'user_id': result.user_id, 'username': result.username,
                'role': result.role}
    return None


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': '未登录'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': '未登录'}), 401
            return redirect(url_for('login'))
        if session.get('role') not in ('admin', 'superadmin'):
            if request.is_json:
                return jsonify({'error': '权限不足'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper


def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': '未登录'}), 401
            return redirect(url_for('login'))
        if session.get('role') != 'superadmin':
            if request.is_json:
                return jsonify({'error': '需要超级管理员权限'}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper
