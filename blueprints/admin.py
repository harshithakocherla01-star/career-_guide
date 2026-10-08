from flask import Blueprint, request, jsonify
from models import db, Role, Skill, RoleSkill, Resource, Project
from blueprints.auth_helper import admin_required

admin_bp = Blueprint('admin', __name__)

# --- ROLES CRUD ---
@admin_bp.route('/api/admin/roles', methods=['GET'])
@admin_required
def admin_get_roles():
    roles = Role.query.all()
    return jsonify({'roles': [r.to_dict() for r in roles]})

@admin_bp.route('/api/admin/roles', methods=['POST'])
@admin_required
def admin_create_role():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    domain = data.get('domain', 'General').strip()

    if not title or not description:
        return jsonify({'error': 'Title and description are required'}), 400

    role = Role(title=title, description=description, domain=domain)
    db.session.add(role)
    db.session.commit()
    return jsonify({'message': 'Role created successfully', 'role': role.to_dict()}), 201

@admin_bp.route('/api/admin/roles/<int:role_id>', methods=['PUT'])
@admin_required
def admin_update_role(role_id):
    role = db.get_or_404(Role, role_id)
    data = request.get_json() or {}

    if 'title' in data:
        role.title = data['title']
    if 'description' in data:
        role.description = data['description']
    if 'domain' in data:
        role.domain = data['domain']

    db.session.commit()
    return jsonify({'message': 'Role updated successfully', 'role': role.to_dict()})

@admin_bp.route('/api/admin/roles/<int:role_id>', methods=['DELETE'])
@admin_required
def admin_delete_role(role_id):
    role = db.get_or_404(Role, role_id)
    db.session.delete(role)
    db.session.commit()
    return jsonify({'message': 'Role deleted successfully'})


# --- SKILLS CRUD ---
@admin_bp.route('/api/admin/skills', methods=['GET'])
@admin_required
def admin_get_skills():
    skills = Skill.query.all()
    return jsonify({'skills': [s.to_dict() for s in skills]})

@admin_bp.route('/api/admin/skills', methods=['POST'])
@admin_required
def admin_create_skill():
    data = request.get_json() or {}
    sid = data.get('id', '').strip().lower()
    name = data.get('name', '').strip()
    category = data.get('category', 'Technical').strip()
    synonyms = data.get('synonyms', [])
    prereqs = data.get('prerequisites', [])

    if not sid or not name:
        return jsonify({'error': 'Skill id and name are required'}), 400

    if db.session.get(Skill, sid):
        return jsonify({'error': 'Skill ID already exists'}), 409

    skill = Skill(id=sid, name=name, category=category)
    skill.synonyms = synonyms
    skill.prerequisites = prereqs
    db.session.add(skill)
    db.session.commit()
    return jsonify({'message': 'Skill created successfully', 'skill': skill.to_dict()}), 201


# --- ROLE-SKILLS MAPPING CRUD ---
@admin_bp.route('/api/admin/role-skills', methods=['POST'])
@admin_required
def admin_add_role_skill():
    data = request.get_json() or {}
    role_id = data.get('role_id')
    skill_id = data.get('skill_id')
    weight = float(data.get('weight', 1.0))
    required_level = int(data.get('required_level', 3))

    if not role_id or not skill_id:
        return jsonify({'error': 'role_id and skill_id are required'}), 400

    existing = RoleSkill.query.filter_by(role_id=role_id, skill_id=skill_id).first()
    if existing:
        existing.weight = weight
        existing.required_level = required_level
    else:
        mapping = RoleSkill(
            role_id=role_id,
            skill_id=skill_id,
            weight=weight,
            required_level=required_level
        )
        db.session.add(mapping)

    db.session.commit()
    return jsonify({'message': 'Role skill requirement updated successfully'})

@admin_bp.route('/api/admin/role-skills/<int:mapping_id>', methods=['DELETE'])
@admin_required
def admin_delete_role_skill(mapping_id):
    mapping = db.get_or_404(RoleSkill, mapping_id)
    db.session.delete(mapping)
    db.session.commit()
    return jsonify({'message': 'Role skill requirement deleted successfully'})


# --- RESOURCES CRUD ---
@admin_bp.route('/api/admin/resources', methods=['POST'])
@admin_required
def admin_create_resource():
    data = request.get_json() or {}
    skill_id = data.get('skill_id')
    title = data.get('title')
    url = data.get('url')
    res_type = data.get('type', 'doc')
    is_free = bool(data.get('is_free', True))
    hours = float(data.get('hours', 4.0))

    if not skill_id or not title or not url:
        return jsonify({'error': 'skill_id, title, and url are required'}), 400

    resource = Resource(
        skill_id=skill_id,
        title=title,
        url=url,
        type=res_type,
        is_free=is_free,
        hours=hours
    )
    db.session.add(resource)
    db.session.commit()
    return jsonify({'message': 'Resource added successfully', 'resource': resource.to_dict()}), 201
