from collections import Counter
from flask import Blueprint, jsonify
from models import db, User, Role, RoleSkill, UserSkill, Milestone, ReadinessHistory
from engines.gap_analyzer import GapAnalyzer
from engines.scorer import ReadinessScorer
from blueprints.auth_helper import admin_required

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/api/admin/analytics/skill-gaps', methods=['GET'])
@admin_required
def get_skill_gaps_analytics():
    candidates = User.query.filter_by(role='user').all()
    gap_analyzer = GapAnalyzer()
    scorer = ReadinessScorer()

    missing_counter = Counter()
    partial_counter = Counter()
    role_scores = {}
    role_candidates = {}

    for candidate in candidates:
        if not candidate.target_role_id:
            continue
        role_id = candidate.target_role_id
        reqs = RoleSkill.query.filter_by(role_id=role_id).all()
        u_skills = UserSkill.query.filter_by(user_id=candidate.id).all()

        analysis = gap_analyzer.analyze(reqs, u_skills)
        for m in analysis['missing']:
            missing_counter[m['skill_name']] += 1
        for p in analysis['partial']:
            partial_counter[p['skill_name']] += 1

        score_res = scorer.calculate_score(reqs, u_skills)
        role_title = reqs[0].role.title if reqs else f"Role {role_id}"
        role_scores.setdefault(role_title, []).append(score_res['overall_score'])
        role_candidates[role_title] = role_candidates.get(role_title, 0) + 1

    # Format averages
    avg_role_readiness = {}
    for r_title, scores in role_scores.items():
        avg_role_readiness[r_title] = round(sum(scores) / len(scores), 1)

    # Milestones completed
    total_milestones = Milestone.query.count()
    completed_milestones = Milestone.query.filter_by(status='completed').count()

    return jsonify({
        'total_candidates': len(candidates),
        'top_missing_skills': [{'skill': k, 'count': v} for k, v in missing_counter.most_common(8)],
        'top_partial_skills': [{'skill': k, 'count': v} for k, v in partial_counter.most_common(8)],
        'avg_readiness_by_role': avg_role_readiness,
        'candidates_by_role': role_candidates,
        'milestones_stats': {
            'total': total_milestones,
            'completed': completed_milestones,
            'completion_rate': round((completed_milestones / total_milestones * 100), 1) if total_milestones > 0 else 0.0
        }
    })

@analytics_bp.route('/api/admin/analytics/top-missing-skills', methods=['GET'])
@admin_required
def get_top_missing_skills():
    candidates = User.query.filter_by(role='user').all()
    gap_analyzer = GapAnalyzer()
    missing_counter = Counter()

    for candidate in candidates:
        if candidate.target_role_id:
            reqs = RoleSkill.query.filter_by(role_id=candidate.target_role_id).all()
            u_skills = UserSkill.query.filter_by(user_id=candidate.id).all()
            analysis = gap_analyzer.analyze(reqs, u_skills)
            for m in analysis['missing']:
                missing_counter[m['skill_name']] += 1

    return jsonify({
        'top_missing_skills': [{'skill': k, 'frequency': v} for k, v in missing_counter.most_common(10)]
    })
