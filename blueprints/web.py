from flask import Blueprint, render_template, redirect, url_for, session, g
from models import User, Role, Skill, UserSkill, Resume, Roadmap, Milestone
from blueprints.auth_helper import get_current_user, login_required, admin_required

web_bp = Blueprint('web', __name__)

@web_bp.before_request
def load_user():
    g.user = get_current_user()

@web_bp.route('/')
def home():
    roles = Role.query.all()
    skills_count = Skill.query.count()
    return render_template('index.html', user=g.user, roles=roles, skills_count=skills_count)

@web_bp.route('/login')
def login_page():
    if g.user:
        return redirect(url_for('web.dashboard_page'))
    return render_template('login.html')

@web_bp.route('/register')
def register_page():
    if g.user:
        return redirect(url_for('web.dashboard_page'))
    roles = Role.query.all()
    return render_template('register.html', roles=roles)

@web_bp.route('/dashboard')
@login_required
def dashboard_page():
    roles = Role.query.all()
    return render_template('dashboard.html', user=g.user, roles=roles)

@web_bp.route('/resume')
@login_required
def resume_page():
    skills = Skill.query.all()
    return render_template('resume.html', user=g.user, skills=skills)

@web_bp.route('/gap-analysis')
@login_required
def gap_analysis_page():
    return render_template('gap_analysis.html', user=g.user)

@web_bp.route('/roadmap')
@login_required
def roadmap_page():
    return render_template('roadmap.html', user=g.user)

@web_bp.route('/recommendations')
@login_required
def recommendations_page():
    return render_template('recommendations.html', user=g.user)

@web_bp.route('/roles')
@login_required
def roles_page():
    return recommendations_page()

@web_bp.route('/interview')
@login_required
def interview_page():
    roles = Role.query.order_by(Role.title.asc()).all()
    return render_template('interview.html', user=g.user, roles=roles)

@web_bp.route('/admin')
@admin_required
def admin_page():
    roles = Role.query.all()
    skills = Skill.query.all()
    return render_template('admin.html', user=g.user, roles=roles, skills=skills)
