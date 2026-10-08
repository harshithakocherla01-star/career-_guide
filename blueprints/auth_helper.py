import jwt
from functools import wraps
from flask import request, jsonify, session, current_app, g
from models import db, User

def generate_token(user):
    payload = {
        'user_id': user.id,
        'email': user.email,
        'role': user.role
    }
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

def decode_token(token):
    try:
        return jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    except Exception:
        return None

def get_current_user():
    """
    Checks session or Authorization header for authenticated user.
    """
    if hasattr(g, 'current_user') and g.current_user:
        return g.current_user

    # 1. Check Flask Session
    user_id = session.get('user_id')
    if user_id:
        user = db.session.get(User, user_id)
        if user:
            g.current_user = user
            return user

    # 2. Check JWT Authorization Header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1].strip()
        data = decode_token(token)
        if data and 'user_id' in data:
            user = db.session.get(User, data['user_id'])
            if user:
                g.current_user = user
                return user

    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            from flask import redirect, url_for
            return redirect(url_for('web.login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required'}), 401
            from flask import redirect, url_for
            return redirect(url_for('web.login_page'))
        if user.role != 'admin':
            return jsonify({'error': 'Administrator access required'}), 403
        return f(*args, **kwargs)
    return decorated_function
