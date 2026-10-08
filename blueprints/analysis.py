from flask import Blueprint, jsonify, request
from models import db, Role, RoleSkill, Skill, UserSkill, ReadinessHistory
from engines.gap_analyzer import GapAnalyzer
from engines.scorer import ReadinessScorer
from engines.prioritizer import MissingSkillPrioritizer
from blueprints.auth_helper import get_current_user, login_required

analysis_bp = Blueprint('analysis', __name__)

@analysis_bp.route('/api/analysis/run', methods=['POST'])
@login_required
def run_analysis():
    user = get_current_user()
    if not user.target_role_id:
        return jsonify({'error': 'Please select a target career role first'}), 400

    role = db.session.get(Role, user.target_role_id)
    if not role:
        return jsonify({'error': 'Target role not found'}), 404

    reqs = RoleSkill.query.filter_by(role_id=role.id).all()
    user_skills = UserSkill.query.filter_by(user_id=user.id).all()
    all_skills = Skill.query.all()

    # 1. Gap Analysis
    gap_analyzer = GapAnalyzer()
    gap_results = gap_analyzer.analyze(reqs, user_skills)

    # 2. Readiness Scoring
    scorer = ReadinessScorer()
    score_results = scorer.calculate_score(reqs, user_skills)

    # 3. Prioritization
    all_gaps = gap_results['partial'] + gap_results['missing']
    prioritizer = MissingSkillPrioritizer(all_skills)
    prioritized_skills = prioritizer.prioritize(all_gaps, all_skills, user.hours_per_week)

    # Record history snapshot
    history_entry = ReadinessHistory(
        user_id=user.id,
        score=score_results['overall_score'],
        snapshot_json={
            'role_id': role.id,
            'role_title': role.title,
            'score': score_results['overall_score'],
            'category_scores': score_results['category_scores'],
            'matched_count': gap_results['summary']['matched_count'],
            'partial_count': gap_results['summary']['partial_count'],
            'missing_count': gap_results['summary']['missing_count']
        }
    )
    db.session.add(history_entry)
    db.session.commit()

    return jsonify({
        'target_role': role.to_dict(),
        'score': score_results,
        'gaps': gap_results,
        'priorities': prioritized_skills
    })

@analysis_bp.route('/api/analysis/gaps', methods=['GET'])
@login_required
def get_gaps():
    user = get_current_user()
    if not user.target_role_id:
        return jsonify({'error': 'No target role selected'}), 400

    reqs = RoleSkill.query.filter_by(role_id=user.target_role_id).all()
    user_skills = UserSkill.query.filter_by(user_id=user.id).all()

    gap_analyzer = GapAnalyzer()
    results = gap_analyzer.analyze(reqs, user_skills)
    return jsonify(results)

@analysis_bp.route('/api/analysis/score', methods=['GET'])
@login_required
def get_score():
    user = get_current_user()
    if not user.target_role_id:
        return jsonify({'error': 'No target role selected'}), 400

    reqs = RoleSkill.query.filter_by(role_id=user.target_role_id).all()
    user_skills = UserSkill.query.filter_by(user_id=user.id).all()

    scorer = ReadinessScorer()
    results = scorer.calculate_score(reqs, user_skills)
    return jsonify(results)

@analysis_bp.route('/api/analysis/priorities', methods=['GET'])
@login_required
def get_priorities():
    user = get_current_user()
    if not user.target_role_id:
        return jsonify({'error': 'No target role selected'}), 400

    reqs = RoleSkill.query.filter_by(role_id=user.target_role_id).all()
    user_skills = UserSkill.query.filter_by(user_id=user.id).all()
    all_skills = Skill.query.all()

    gap_analyzer = GapAnalyzer()
    gap_results = gap_analyzer.analyze(reqs, user_skills)

    all_gaps = gap_results['partial'] + gap_results['missing']
    prioritizer = MissingSkillPrioritizer(all_skills)
    prioritized_skills = prioritizer.prioritize(all_gaps, all_skills, user.hours_per_week)

    return jsonify({
        'priorities': prioritized_skills
    })

@analysis_bp.route('/api/analysis/history', methods=['GET'])
@login_required
def get_history():
    user = get_current_user()
    history = ReadinessHistory.query.filter_by(user_id=user.id).order_by(ReadinessHistory.date.asc()).all()
    return jsonify({
        'history': [h.to_dict() for h in history]
    })
