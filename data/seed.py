import os
import json
import sys

# Ensure parent directory is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models import db, User, Skill, Role, RoleSkill, Resource, Project, UserSkill, ReadinessHistory
from engines.scorer import ReadinessScorer

def load_json(filename):
    filepath = os.path.join(os.path.dirname(__file__), filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def seed_database(app):
    with app.app_context():
        db.create_all()

        # 1. Seed Skills
        if Skill.query.count() == 0:
            skills_data = load_json('skills.json')
            for s in skills_data:
                skill = Skill(
                    id=s['id'],
                    name=s['name'],
                    category=s['category']
                )
                skill.synonyms = s.get('synonyms', [])
                skill.prerequisites = s.get('prerequisites', [])
                db.session.add(skill)
            db.session.commit()
            print(f"Seeded {len(skills_data)} skills.")

        # 2. Seed Roles
        if Role.query.count() == 0:
            roles_data = load_json('roles.json')
            for r in roles_data:
                role = Role(
                    id=r['id'],
                    title=r['title'],
                    description=r['description'],
                    domain=r['domain']
                )
                db.session.add(role)
            db.session.commit()
            print(f"Seeded {len(roles_data)} roles.")

        # 3. Seed RoleSkills
        if RoleSkill.query.count() == 0:
            role_skills_data = load_json('role_skills.json')
            for rs in role_skills_data:
                mapping = RoleSkill(
                    role_id=rs['role_id'],
                    skill_id=rs['skill_id'],
                    weight=rs['weight'],
                    required_level=rs['required_level']
                )
                db.session.add(mapping)
            db.session.commit()
            print(f"Seeded {len(role_skills_data)} role skill mappings.")

        # 4. Seed Resources
        if Resource.query.count() == 0:
            resources_data = load_json('resources.json')
            for res in resources_data:
                r = Resource(
                    skill_id=res['skill_id'],
                    title=res['title'],
                    url=res['url'],
                    type=res.get('type', 'doc'),
                    is_free=res.get('is_free', True),
                    hours=float(res.get('hours', 4.0))
                )
                db.session.add(r)
            db.session.commit()
            print(f"Seeded {len(resources_data)} resources.")

        # 5. Seed Projects
        if Project.query.count() == 0:
            projects_data = load_json('projects.json')
            for p in projects_data:
                proj = Project(
                    skill_id=p['skill_id'],
                    title=p['title'],
                    difficulty=p.get('difficulty', 'intermediate'),
                    description=p['description']
                )
                db.session.add(proj)
            db.session.commit()
            print(f"Seeded {len(projects_data)} projects.")

        # 6. Seed Default Users if none exist
        if User.query.count() == 0:
            # Admin User
            admin = User(
                name="Admin User",
                email="admin@techtide.io",
                role="admin",
                hours_per_week=20
            )
            admin.set_password("admin123")
            db.session.add(admin)

            # Sample Candidate User (Alex Rivera)
            alex = User(
                name="Alex Rivera",
                email="alex@techtide.io",
                role="user",
                target_role_id=1,  # Full Stack Web Developer
                hours_per_week=12
            )
            alex.set_password("alex123")
            db.session.add(alex)
            db.session.commit()

            # Seed initial skills for Alex
            initial_skills = [
                ("javascript", 3, "resume"),
                ("html_css", 4, "resume"),
                ("git", 3, "resume"),
                ("sql", 2, "resume"),
                ("python", 2, "resume")
            ]
            for sid, lvl, src in initial_skills:
                us = UserSkill(
                    user_id=alex.id,
                    skill_id=sid,
                    level=lvl,
                    source=src
                )
                db.session.add(us)
            db.session.commit()

            # Calculate and save initial readiness score
            scorer = ReadinessScorer()
            reqs = RoleSkill.query.filter_by(role_id=alex.target_role_id).all()
            user_skills = UserSkill.query.filter_by(user_id=alex.id).all()
            score_data = scorer.calculate_score(reqs, user_skills)

            hist = ReadinessHistory(
                user_id=alex.id,
                score=score_data['overall_score'],
                snapshot_json=score_data
            )
            db.session.add(hist)
            db.session.commit()
            print(f"Seeded default users (Admin: admin@techtide.io / Candidate: alex@techtide.io).")

if __name__ == '__main__':
    from flask import Flask
    from config import Config
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    seed_database(app)
