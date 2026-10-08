import math
from flask import Blueprint, request, jsonify
from models import db, Role, RoleSkill, Skill, UserSkill, Roadmap, Milestone, Resource, Project
from engines.gap_analyzer import GapAnalyzer
from engines.prioritizer import MissingSkillPrioritizer
from engines.progress import ProgressTracker
from services.ai_client import AIClient
from blueprints.auth_helper import get_current_user, login_required

roadmap_bp = Blueprint('roadmap', __name__)

@roadmap_bp.route('/api/roadmap/generate', methods=['POST'])
@login_required
def generate_roadmap():
    user = get_current_user()
    if not user.target_role_id:
        return jsonify({'error': 'Target role not set'}), 400

    role = db.session.get(Role, user.target_role_id)
    if not role:
        return jsonify({'error': 'Target role not found'}), 404

    weekly_budget = float(user.hours_per_week or 10)

    # 1. ANALYZE
    reqs = RoleSkill.query.filter_by(role_id=role.id).all()
    user_skills = UserSkill.query.filter_by(user_id=user.id).all()
    all_skills = Skill.query.all()

    gap_analyzer = GapAnalyzer()
    gap_results = gap_analyzer.analyze(reqs, user_skills)
    all_gaps = gap_results['partial'] + gap_results['missing']

    if not all_gaps:
        return jsonify({
            'message': 'No skill gaps detected! You already meet all role requirements.',
            'roadmap': None
        })

    prioritizer = MissingSkillPrioritizer(all_skills)
    ordered_gaps = prioritizer.prioritize(all_gaps, all_skills, weekly_budget)

    # Collect available resources and projects from DB
    gap_sids = [g['skill_id'] for g in ordered_gaps]
    db_resources = Resource.query.filter(Resource.skill_id.in_(gap_sids)).all()
    db_projects = Project.query.filter(Project.skill_id.in_(gap_sids)).all()

    resources_by_skill = {}
    for r in db_resources:
        resources_by_skill.setdefault(r.skill_id, []).append(r.to_dict())

    projects_by_skill = {}
    for p in db_projects:
        projects_by_skill.setdefault(p.skill_id, []).append(p.to_dict())

    # 2. PLAN & REVISE (Agentic Roadmap Loop)
    roadmap_plan = None
    ai_client = AIClient()

    # Try AI generation if available, bounded retries
    if ai_client.is_available():
        for attempt in range(2):
            candidate_plan = _generate_ai_plan(ai_client, role.title, ordered_gaps, weekly_budget, resources_by_skill, projects_by_skill)
            if candidate_plan and _self_check_plan(candidate_plan, ordered_gaps, weekly_budget, db_resources):
                roadmap_plan = candidate_plan
                break

    # Grounded fallback if AI unavailable or validation failed
    if not roadmap_plan:
        roadmap_plan = _generate_grounded_plan(ordered_gaps, weekly_budget, resources_by_skill, projects_by_skill)

    # 3. Save Roadmap and Milestones to DB
    # Deactivate or delete old roadmaps for this role to maintain clean tracking
    old_roadmaps = Roadmap.query.filter_by(user_id=user.id, role_id=role.id).all()
    for old_r in old_roadmaps:
        db.session.delete(old_r)

    new_roadmap = Roadmap(
        user_id=user.id,
        role_id=role.id
    )
    new_roadmap.generated_json = roadmap_plan
    db.session.add(new_roadmap)
    db.session.flush()

    for m_data in roadmap_plan.get('milestones', []):
        m = Milestone(
            roadmap_id=new_roadmap.id,
            week=m_data.get('week', 1),
            title=m_data.get('title', 'Learning Milestone'),
            status='pending'
        )
        m.skill_ids = m_data.get('skill_ids', [])
        db.session.add(m)

    db.session.commit()

    return jsonify({
        'message': 'Personalized career roadmap generated successfully',
        'roadmap': new_roadmap.to_dict()
    })

def _generate_grounded_plan(ordered_gaps, weekly_budget, resources_by_skill, projects_by_skill):
    """
    Deterministic planning engine that packs gap skills into weekly milestones
    respecting weekly study hours and prerequisite order.
    """
    milestones = []
    current_week = 1
    current_week_skills = []
    current_week_resources = []
    current_week_hours = 0.0

    for gap in ordered_gaps:
        sid = gap['skill_id']
        sname = gap['skill_name']
        skill_res = resources_by_skill.get(sid, [])
        skill_projs = projects_by_skill.get(sid, [])

        res_to_take = skill_res[:2] if skill_res else []
        hours_for_skill = sum(r['hours'] for r in res_to_take) or 4.0

        if current_week_hours + hours_for_skill > weekly_budget * 1.2 and current_week_skills:
            # Finalize current milestone
            chosen_proj = None
            for s in current_week_skills:
                if projects_by_skill.get(s):
                    chosen_proj = projects_by_skill[s][0]
                    break

            milestones.append({
                'week': current_week,
                'title': f"Mastering {', '.join(current_week_skills)}",
                'skill_ids': list(current_week_skills),
                'details': {
                    'resources': list(current_week_resources),
                    'project': chosen_proj,
                    'total_hours': round(current_week_hours, 1)
                }
            })
            current_week += 1
            current_week_skills = []
            current_week_resources = []
            current_week_hours = 0.0

        current_week_skills.append(sid)
        current_week_resources.extend(res_to_take)
        current_week_hours += hours_for_skill

    # Final milestone
    if current_week_skills:
        chosen_proj = None
        for s in current_week_skills:
            if projects_by_skill.get(s):
                chosen_proj = projects_by_skill[s][0]
                break

        milestones.append({
            'week': current_week,
            'title': f"Capstone & {', '.join(current_week_skills)}",
            'skill_ids': list(current_week_skills),
            'details': {
                'resources': list(current_week_resources),
                'project': chosen_proj,
                'total_hours': round(current_week_hours, 1)
            }
        })

    return {
        'total_weeks': len(milestones),
        'weekly_budget': weekly_budget,
        'milestones': milestones
    }

def _generate_ai_plan(ai_client, role_title, ordered_gaps, weekly_budget, resources_by_skill, projects_by_skill):
    prompt = f"""
    Create a week-by-week learning plan for role: {role_title}.
    Weekly budget: {weekly_budget} hours.
    Ordered gaps: {[g['skill_name'] + ' (id: ' + g['skill_id'] + ')' for g in ordered_gaps]}
    Available resources: {resources_by_skill}
    Available projects: {projects_by_skill}

    Return strict JSON:
    {{
      "total_weeks": int,
      "weekly_budget": {weekly_budget},
      "milestones": [
        {{
          "week": 1,
          "title": "Title",
          "skill_ids": ["skill_id"],
          "details": {{
            "resources": [{{"title": "...", "url": "...", "hours": 4}}],
            "project": {{"title": "...", "description": "..."}},
            "total_hours": 8.0
          }}
        }}
      ]
    }}
    """
    raw = ai_client.call_llm(prompt)
    return ai_client.parse_json_safely(raw)

def _self_check_plan(plan, ordered_gaps, weekly_budget, db_resources):
    if not isinstance(plan, dict) or 'milestones' not in plan:
        return False
    milestones = plan['milestones']
    if not milestones:
        return False

    valid_urls = {r.url for r in db_resources}
    for m in milestones:
        # Check resources exist in database
        res_list = m.get('details', {}).get('resources', [])
        for r in res_list:
            if r.get('url') and r['url'] not in valid_urls:
                return False  # Hallucinated resource!
    return True

@roadmap_bp.route('/api/roadmap', methods=['GET'])
@login_required
def get_roadmap():
    user = get_current_user()
    if not user.target_role_id:
        return jsonify({'message': 'Target role not set', 'roadmap': None}), 200

    roadmap = Roadmap.query.filter_by(user_id=user.id, role_id=user.target_role_id).order_by(Roadmap.created_at.desc()).first()
    if not roadmap:
        return jsonify({'message': 'No roadmap generated yet', 'roadmap': None}), 200

    data = roadmap.to_dict()
    completed_count = sum(1 for m in data['milestones'] if m['status'] == 'completed')
    total_count = len(data['milestones'])
    data['progress_percentage'] = round((completed_count / total_count * 100), 1) if total_count > 0 else 0.0

    return jsonify({'roadmap': data})

@roadmap_bp.route('/api/milestones/<int:milestone_id>', methods=['PATCH'])
@login_required
def toggle_milestone(milestone_id):
    user = get_current_user()
    data = request.get_json() or {}
    desired_status = data.get('status')  # 'completed' or 'pending'

    tracker = ProgressTracker()
    milestone = db.session.get(Milestone, milestone_id)
    if not milestone or milestone.roadmap.user_id != user.id:
        return jsonify({'error': 'Milestone not found'}), 404

    if desired_status == 'completed' or (not desired_status and milestone.status != 'completed'):
        m, score_data = tracker.complete_milestone(user, milestone_id)
    else:
        m, score_data = tracker.uncomplete_milestone(user, milestone_id)

    return jsonify({
        'message': f"Milestone marked as {m.status}",
        'milestone': m.to_dict(),
        'updated_score': score_data
    })
