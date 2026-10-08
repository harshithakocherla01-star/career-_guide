import os
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, current_app
from models import db, Resume, Skill, UserSkill, RoleSkill
from services.resume_parser import ResumeParser
from services.skill_extractor import SkillExtractor
from engines.scorer import ReadinessScorer
from blueprints.auth_helper import get_current_user, login_required

resume_bp = Blueprint('resume', __name__)

@resume_bp.route('/api/resume/upload', methods=['POST'])
@login_required
def upload_resume():
    user = get_current_user()
    raw_text = ""

    # Check if file uploaded
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1].lower().replace('.', '')
            if ext not in current_app.config['ALLOWED_EXTENSIONS']:
                return jsonify({'error': f'Unsupported file type. Allowed: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}'}), 400

            os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], f"user_{user.id}_{filename}")
            file.save(save_path)

            try:
                raw_text = ResumeParser.extract_text(save_path)
            except Exception as e:
                return jsonify({'error': f'Failed to parse file: {str(e)}'}), 400

    # Or check if JSON body with text
    elif request.is_json:
        data = request.get_json() or {}
        raw_text = data.get('raw_text', '').strip()

    if not raw_text:
        return jsonify({'error': 'No file uploaded or text provided'}), 400

    # Load taxonomy
    all_skills = Skill.query.all()
    extractor = SkillExtractor(all_skills)
    parsed = extractor.extract(raw_text)

    # Save Resume record
    resume = Resume(
        user_id=user.id,
        raw_text=raw_text,
        resume_score=parsed.get('ats_score', 0.0)
    )
    resume.parsed_json = parsed
    db.session.add(resume)

    # Sync extracted skills to UserSkill table
    extracted_skills = parsed.get('skills', [])
    for s_info in extracted_skills:
        sid = s_info.get('skill_id')
        lvl = int(s_info.get('level', 3))
        
        user_skill = UserSkill.query.filter_by(user_id=user.id, skill_id=sid).first()
        if user_skill:
            if lvl > user_skill.level:
                user_skill.level = lvl
                user_skill.source = 'resume'
        else:
            new_us = UserSkill(
                user_id=user.id,
                skill_id=sid,
                level=lvl,
                source='resume'
            )
            db.session.add(new_us)

    db.session.commit()

    # Recalculate score if target role set
    score_summary = None
    if user.target_role_id:
        from engines.progress import ProgressTracker
        tracker = ProgressTracker()
        score_summary = tracker.record_score_snapshot(user)

    return jsonify({
        'message': 'Resume processed and skills extracted successfully',
        'resume_id': resume.id,
        'ats_score': resume.resume_score,
        'extracted_skills_count': len(extracted_skills),
        'parsed_data': parsed,
        'score_summary': score_summary
    })

@resume_bp.route('/api/resume/analysis', methods=['GET'])
@login_required
def get_resume_analysis():
    user = get_current_user()
    latest_resume = Resume.query.filter_by(user_id=user.id).order_by(Resume.created_at.desc()).first()
    if not latest_resume:
        return jsonify({'message': 'No resume uploaded yet', 'has_resume': False}), 200

    return jsonify({
        'has_resume': True,
        'resume': latest_resume.to_dict(),
        'created_at': latest_resume.created_at.isoformat()
    })

@resume_bp.route('/api/resume/skills', methods=['GET'])
@login_required
def get_user_skills():
    user = get_current_user()
    skills = UserSkill.query.filter_by(user_id=user.id).all()
    return jsonify({
        'skills': [s.to_dict() for s in skills]
    })

@resume_bp.route('/api/resume/skills', methods=['POST'])
@login_required
def add_user_skill():
    user = get_current_user()
    data = request.get_json() or {}
    skill_id = data.get('skill_id', '').strip().lower()
    level = int(data.get('level', 3))

    skill = db.session.get(Skill, skill_id)
    if not skill:
        return jsonify({'error': f'Skill "{skill_id}" not found in taxonomy'}), 404

    user_skill = UserSkill.query.filter_by(user_id=user.id, skill_id=skill_id).first()
    if user_skill:
        user_skill.level = max(1, min(5, level))
        user_skill.source = 'self'
    else:
        user_skill = UserSkill(
            user_id=user.id,
            skill_id=skill_id,
            level=max(1, min(5, level)),
            source='self'
        )
        db.session.add(user_skill)

    db.session.commit()

    # Update score
    if user.target_role_id:
        from engines.progress import ProgressTracker
        ProgressTracker().record_score_snapshot(user)

    return jsonify({
        'message': 'Skill updated successfully',
        'skill': user_skill.to_dict()
    })

@resume_bp.route('/api/resume/skills/<skill_id>', methods=['DELETE'])
@login_required
def delete_user_skill(skill_id):
    user = get_current_user()
    user_skill = UserSkill.query.filter_by(user_id=user.id, skill_id=skill_id).first()
    if user_skill:
        db.session.delete(user_skill)
        db.session.commit()
        if user.target_role_id:
            from engines.progress import ProgressTracker
            ProgressTracker().record_score_snapshot(user)
        return jsonify({'message': 'Skill removed'})
    return jsonify({'error': 'Skill not found'}), 404
