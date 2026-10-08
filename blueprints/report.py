from flask import Blueprint, send_file, jsonify
from models import db, Role, RoleSkill, UserSkill, Roadmap
from engines.scorer import ReadinessScorer
from engines.gap_analyzer import GapAnalyzer
from services.pdf_generator import CareerReportPDFGenerator
from blueprints.auth_helper import get_current_user, login_required

report_bp = Blueprint('report', __name__)

@report_bp.route('/api/report/pdf', methods=['GET'])
@login_required
def download_pdf_report():
    user = get_current_user()
    if not user.target_role_id:
        return jsonify({'error': 'Please select a target role before downloading a career report'}), 400

    role = db.session.get(Role, user.target_role_id)
    if not role:
        return jsonify({'error': 'Target role not found'}), 404

    reqs = RoleSkill.query.filter_by(role_id=role.id).all()
    user_skills = UserSkill.query.filter_by(user_id=user.id).all()

    # 1. Scorer & Gap calculations
    scorer = ReadinessScorer()
    score_data = scorer.calculate_score(reqs, user_skills)

    gap_analyzer = GapAnalyzer()
    gap_data = gap_analyzer.analyze(reqs, user_skills)

    # 2. Get Roadmap data if exists
    roadmap_obj = Roadmap.query.filter_by(user_id=user.id, role_id=role.id).order_by(Roadmap.created_at.desc()).first()
    roadmap_data = roadmap_obj.to_dict() if roadmap_obj else None

    # 3. Generate PDF
    generator = CareerReportPDFGenerator()
    pdf_buffer = generator.generate(
        user=user,
        target_role=role,
        score_data=score_data,
        gap_data=gap_data,
        roadmap_data=roadmap_data
    )

    clean_role_name = role.title.lower().replace(" ", "_")
    filename = f"career_roadmap_{clean_role_name}_{user.id}.pdf"

    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
