from flask import Blueprint, request, jsonify, session
from models import db, User
from blueprints.auth_helper import generate_token, get_current_user, login_required

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    target_role_id = data.get('target_role_id')
    hours_per_week = data.get('hours_per_week', 10)

    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'An account with this email already exists'}), 409

    user = User(
        name=name,
        email=email,
        target_role_id=int(target_role_id) if target_role_id else None,
        hours_per_week=int(hours_per_week) if hours_per_week else 10,
        role='user'
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = generate_token(user)
    session['user_id'] = user.id

    return jsonify({
        'message': 'Registration successful',
        'user': user.to_dict(),
        'token': token
    }), 201

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid email or password'}), 401

    token = generate_token(user)
    session['user_id'] = user.id

    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(),
        'token': token
    })

@auth_bp.route('/api/auth/logout', methods=['POST', 'GET'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out successfully'})

@auth_bp.route('/api/auth/me', methods=['GET'])
@login_required
def me():
    user = get_current_user()
    return jsonify({'user': user.to_dict()})
