import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

def get_utc_now():
    return datetime.now(timezone.utc)

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user' | 'admin'
    target_role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)
    hours_per_week = db.Column(db.Integer, default=10)
    created_at = db.Column(db.DateTime, default=get_utc_now)

    # Relationships
    target_role = db.relationship('Role', backref='interested_users', foreign_keys=[target_role_id])
    resumes = db.relationship('Resume', backref='user', cascade='all, delete-orphan', lazy=True)
    user_skills = db.relationship('UserSkill', backref='user', cascade='all, delete-orphan', lazy=True)
    roadmaps = db.relationship('Roadmap', backref='user', cascade='all, delete-orphan', lazy=True)
    interview_sessions = db.relationship('InterviewSession', backref='user', cascade='all, delete-orphan', lazy=True)
    readiness_history = db.relationship('ReadinessHistory', backref='user', cascade='all, delete-orphan', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return self.name

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'target_role_id': self.target_role_id,
            'target_role_title': self.target_role.title if self.target_role else None,
            'hours_per_week': self.hours_per_week,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Skill(db.Model):
    __tablename__ = 'skills'

    id = db.Column(db.String(64), primary_key=True)  # canonical ID like 'python', 'docker'
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(64), nullable=False)  # 'Technical', 'Tools', 'Databases', 'Architecture', etc.
    _synonyms = db.Column('synonyms', db.Text, default='[]')
    _prerequisites = db.Column('prerequisites', db.Text, default='[]')

    @property
    def synonyms(self):
        return json.loads(self._synonyms or '[]')

    @synonyms.setter
    def synonyms(self, val):
        self._synonyms = json.dumps(val or [])

    @property
    def prerequisites(self):
        return json.loads(self._prerequisites or '[]')

    @prerequisites.setter
    def prerequisites(self, val):
        self._prerequisites = json.dumps(val or [])

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'synonyms': self.synonyms,
            'prerequisites': self.prerequisites
        }


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=False)
    domain = db.Column(db.String(100), nullable=False)  # e.g., 'Web Development', 'AI / ML', 'DevOps'

    role_skills = db.relationship('RoleSkill', backref='role', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'domain': self.domain,
            'skills_count': len(self.role_skills)
        }


class RoleSkill(db.Model):
    __tablename__ = 'role_skills'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    skill_id = db.Column(db.String(64), db.ForeignKey('skills.id'), nullable=False)
    weight = db.Column(db.Float, default=1.0)  # importance weight, e.g. 0.1 to 1.0
    required_level = db.Column(db.Integer, default=3)  # 1 to 5 scale

    skill = db.relationship('Skill', backref='role_mappings', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'role_id': self.role_id,
            'skill_id': self.skill_id,
            'skill_name': self.skill.name if self.skill else self.skill_id,
            'category': self.skill.category if self.skill else 'General',
            'weight': self.weight,
            'required_level': self.required_level
        }


class UserSkill(db.Model):
    __tablename__ = 'user_skills'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    skill_id = db.Column(db.String(64), db.ForeignKey('skills.id'), nullable=False)
    level = db.Column(db.Integer, default=1)  # 1 to 5 scale
    source = db.Column(db.String(32), default='resume')  # 'resume' | 'self' | 'roadmap'
    updated_at = db.Column(db.DateTime, default=get_utc_now, onupdate=get_utc_now)

    skill = db.relationship('Skill', backref='user_mappings', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'skill_id': self.skill_id,
            'skill_name': self.skill.name if self.skill else self.skill_id,
            'category': self.skill.category if self.skill else 'General',
            'level': self.level,
            'source': self.source,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Resume(db.Model):
    __tablename__ = 'resumes'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    raw_text = db.Column(db.Text, nullable=False)
    _parsed_json = db.Column('parsed_json', db.Text, default='{}')
    resume_score = db.Column(db.Float, default=0.0)  # ATS score
    created_at = db.Column(db.DateTime, default=get_utc_now)

    @property
    def parsed_json(self):
        return json.loads(self._parsed_json or '{}')

    @parsed_json.setter
    def parsed_json(self, val):
        self._parsed_json = json.dumps(val or {})

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'resume_score': self.resume_score,
            'parsed_data': self.parsed_json,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Roadmap(db.Model):
    __tablename__ = 'roadmaps'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    _generated_json = db.Column('generated_json', db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=get_utc_now)

    role = db.relationship('Role', backref='roadmaps', lazy=True)
    milestones = db.relationship('Milestone', backref='roadmap', cascade='all, delete-orphan', lazy=True, order_by='Milestone.week')

    @property
    def generated_json(self):
        return json.loads(self._generated_json or '{}')

    @generated_json.setter
    def generated_json(self, val):
        self._generated_json = json.dumps(val or {})

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'role_id': self.role_id,
            'role_title': self.role.title if self.role else None,
            'details': self.generated_json,
            'milestones': [m.to_dict() for m in self.milestones],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Milestone(db.Model):
    __tablename__ = 'milestones'

    id = db.Column(db.Integer, primary_key=True)
    roadmap_id = db.Column(db.Integer, db.ForeignKey('roadmaps.id'), nullable=False)
    week = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    _skill_ids = db.Column('skill_ids', db.Text, default='[]')
    status = db.Column(db.String(32), default='pending')  # 'pending' | 'completed'
    completed_at = db.Column(db.DateTime, nullable=True)

    @property
    def skill_ids(self):
        return json.loads(self._skill_ids or '[]')

    @skill_ids.setter
    def skill_ids(self, val):
        self._skill_ids = json.dumps(val or [])

    def to_dict(self):
        return {
            'id': self.id,
            'roadmap_id': self.roadmap_id,
            'week': self.week,
            'title': self.title,
            'skill_ids': self.skill_ids,
            'status': self.status,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class Resource(db.Model):
    __tablename__ = 'resources'

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.String(64), db.ForeignKey('skills.id'), nullable=False)
    title = db.Column(db.String(250), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    type = db.Column(db.String(50), default='doc')  # 'course' | 'doc' | 'video' | 'article'
    is_free = db.Column(db.Boolean, default=True)
    hours = db.Column(db.Float, default=4.0)

    skill = db.relationship('Skill', backref='resources', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'skill_id': self.skill_id,
            'skill_name': self.skill.name if self.skill else self.skill_id,
            'title': self.title,
            'url': self.url,
            'type': self.type,
            'is_free': self.is_free,
            'hours': self.hours
        }


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.String(64), db.ForeignKey('skills.id'), nullable=False)
    title = db.Column(db.String(250), nullable=False)
    difficulty = db.Column(db.String(32), default='intermediate')  # 'beginner' | 'intermediate' | 'advanced'
    description = db.Column(db.Text, nullable=False)

    skill = db.relationship('Skill', backref='projects', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'skill_id': self.skill_id,
            'skill_name': self.skill.name if self.skill else self.skill_id,
            'title': self.title,
            'difficulty': self.difficulty,
            'description': self.description
        }


class InterviewSession(db.Model):
    __tablename__ = 'interview_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    _questions_json = db.Column('questions_json', db.Text, default='[]')
    _answers_json = db.Column('answers_json', db.Text, default='[]')
    score = db.Column(db.Float, default=0.0)
    completed_at = db.Column(db.DateTime, default=get_utc_now)

    role = db.relationship('Role', backref='interview_sessions', lazy=True)

    @property
    def questions_json(self):
        return json.loads(self._questions_json or '[]')

    @questions_json.setter
    def questions_json(self, val):
        self._questions_json = json.dumps(val or [])

    @property
    def answers_json(self):
        return json.loads(self._answers_json or '[]')

    @answers_json.setter
    def answers_json(self, val):
        self._answers_json = json.dumps(val or [])

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'role_id': self.role_id,
            'role_title': self.role.title if self.role else None,
            'questions': self.questions_json,
            'answers': self.answers_json,
            'score': self.score,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class InterviewRun(db.Model):
    """Configuration and lifecycle metadata for a conversational interview."""
    __tablename__ = 'interview_runs'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id'), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    config_json = db.Column(db.Text, nullable=False, default='{}')
    status = db.Column(db.String(20), nullable=False, default='active')  # active | completed | expired
    started_at = db.Column(db.DateTime, nullable=False, default=get_utc_now)
    ended_at = db.Column(db.DateTime, nullable=True)

    interview = db.relationship('InterviewSession', backref=db.backref('run', uselist=False, cascade='all, delete-orphan'))

    @property
    def config(self):
        return json.loads(self.config_json or '{}')

    @config.setter
    def config(self, value):
        self.config_json = json.dumps(value or {})


class InterviewMessage(db.Model):
    """Persisted final transcript messages; partial captions remain client-side."""
    __tablename__ = 'interview_messages'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id'), nullable=False, index=True)
    speaker = db.Column(db.String(20), nullable=False)  # interviewer | candidate
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=get_utc_now)

    interview = db.relationship('InterviewSession', backref=db.backref('messages', cascade='all, delete-orphan', order_by='InterviewMessage.created_at'))

    def to_dict(self):
        created = self.created_at
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return {
            'id': self.id,
            'speaker': self.speaker,
            'text': self.text,
            'created_at': created.isoformat() if created else None
        }


class InterviewReport(db.Model):
    """AI generated evaluation grounded in a completed interview transcript."""
    __tablename__ = 'interview_reports'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id'), unique=True, nullable=False)
    report_json = db.Column(db.Text, nullable=False, default='{}')
    created_at = db.Column(db.DateTime, nullable=False, default=get_utc_now)

    interview = db.relationship('InterviewSession', backref=db.backref('report', uselist=False, cascade='all, delete-orphan'))

    @property
    def report(self):
        return json.loads(self.report_json or '{}')

    @report.setter
    def report(self, value):
        self.report_json = json.dumps(value or {})


class ReadinessHistory(db.Model):
    __tablename__ = 'readiness_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    _snapshot_json = db.Column('snapshot_json', db.Text, default='{}')
    date = db.Column(db.DateTime, default=get_utc_now)

    @property
    def snapshot_json(self):
        return json.loads(self._snapshot_json or '{}')

    @snapshot_json.setter
    def snapshot_json(self, val):
        self._snapshot_json = json.dumps(val or {})

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'score': self.score,
            'snapshot': self.snapshot_json,
            'date': self.date.strftime('%Y-%m-%d %H:%M') if self.date else None
        }
