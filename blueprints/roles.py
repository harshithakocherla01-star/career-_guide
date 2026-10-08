from flask import Blueprint, jsonify
from models import db, Role, RoleSkill, Skill, UserSkill
from engines.recommender import RoleRecommender
from blueprints.auth_helper import get_current_user, login_required

roles_bp = Blueprint('roles', __name__)

@roles_bp.route('/api/roles', methods=['GET'])
def get_roles():
    roles = Role.query.all()
    return jsonify({
        'roles': [r.to_dict() for r in roles]
    })

@roles_bp.route('/api/roles/<int:role_id>', methods=['GET'])
def get_role(role_id):
    role = db.get_or_404(Role, role_id)
    skills = [rs.to_dict() for rs in role.role_skills]
    data = role.to_dict()
    data['requirements'] = skills
    return jsonify(data)

@roles_bp.route('/api/roles/<int:role_id>/skills', methods=['GET'])
def get_role_skills(role_id):
    role = db.get_or_404(Role, role_id)
    skills = [rs.to_dict() for rs in role.role_skills]
    return jsonify({
        'role_id': role_id,
        'role_title': role.title,
        'requirements': skills
    })

@roles_bp.route('/api/recommendations', methods=['GET'])
@login_required
def get_recommendations():
    user = get_current_user()
    user_skills = UserSkill.query.filter_by(user_id=user.id).all()
    all_roles = Role.query.all()
    all_skills = Skill.query.all()

    recommender = RoleRecommender(all_skills)
    recommendations = recommender.recommend(user_skills, all_roles, all_skills)

    return jsonify({
        'user_id': user.id,
        'target_role_id': user.target_role_id,
        'recommendations': recommendations
    })
