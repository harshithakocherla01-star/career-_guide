from flask import Blueprint, request, jsonify
from models import db, Role, UserSkill
from blueprints.auth_helper import get_current_user, login_required

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    user = get_current_user()
    data = user.to_dict()
    data['skills_count'] = UserSkill.query.filter_by(user_id=user.id).count()
    data['has_resume'] = len(user.resumes) > 0
    return jsonify(data)

@profile_bp.route('/api/profile', methods=['PUT'])
@login_required
def update_profile():
    user = get_current_user()
    data = request.get_json() or {}

    if 'name' in data and data['name'].strip():
        user.name = data['name'].strip()

    if 'target_role_id' in data:
        role_id = data['target_role_id']
        if role_id:
            role = db.session.get(Role, role_id)
            if not role:
                return jsonify({'error': 'Target role not found'}), 404
            user.target_role_id = int(role_id)
        else:
            user.target_role_id = None

    if 'hours_per_week' in data:
        try:
            hpw = int(data['hours_per_week'])
            if hpw > 0:
                user.hours_per_week = hpw
        except ValueError:
            pass

    db.session.commit()
    return jsonify({
        'message': 'Profile updated successfully',
        'user': user.to_dict()
    })
