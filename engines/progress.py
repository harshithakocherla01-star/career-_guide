from datetime import datetime, timezone
from models import db, Milestone, UserSkill, ReadinessHistory, RoleSkill
from engines.scorer import ReadinessScorer

class ProgressTracker:
    def __init__(self):
        self.scorer = ReadinessScorer()

    def complete_milestone(self, user, milestone_id):
        """
        Marks milestone as completed, increases user skill levels for skills
        covered by this milestone, and records new readiness score snapshot.
        """
        milestone = db.session.get(Milestone, milestone_id)
        if not milestone or milestone.roadmap.user_id != user.id:
            return None, "Milestone not found or unauthorized"

        if milestone.status == 'completed':
            return milestone, "Already completed"

        milestone.status = 'completed'
        milestone.completed_at = datetime.now(timezone.utc)

        # Update skills covered by this milestone
        skill_ids = milestone.skill_ids
        for sid in skill_ids:
            # Find target required level from user's target role
            req = RoleSkill.query.filter_by(role_id=user.target_role_id, skill_id=sid).first()
            target_level = req.required_level if req else 3

            user_skill = UserSkill.query.filter_by(user_id=user.id, skill_id=sid).first()
            if not user_skill:
                # Started from missing, advance to initial competency
                new_lvl = min(2, target_level)
                user_skill = UserSkill(
                    user_id=user.id,
                    skill_id=sid,
                    level=new_lvl,
                    source='roadmap'
                )
                db.session.add(user_skill)
            else:
                # Level up by 1 level up to target_level
                if user_skill.level < target_level:
                    user_skill.level += 1
                    user_skill.source = 'roadmap'

        db.session.commit()

        # Recalculate readiness score
        score_data = self.record_score_snapshot(user)

        return milestone, score_data

    def uncomplete_milestone(self, user, milestone_id):
        """
        Reverts milestone back to pending.
        """
        milestone = db.session.get(Milestone, milestone_id)
        if not milestone or milestone.roadmap.user_id != user.id:
            return None, "Milestone not found or unauthorized"

        milestone.status = 'pending'
        milestone.completed_at = None
        db.session.commit()

        score_data = self.record_score_snapshot(user)
        return milestone, score_data

    def record_score_snapshot(self, user):
        """
        Calculates current score for user's target role and appends to ReadinessHistory.
        """
        if not user.target_role_id:
            return {'overall_score': 0.0, 'category_scores': {}, 'point_losses': []}

        reqs = RoleSkill.query.filter_by(role_id=user.target_role_id).all()
        user_skills = UserSkill.query.filter_by(user_id=user.id).all()

        score_result = self.scorer.calculate_score(reqs, user_skills)

        history_entry = ReadinessHistory(
            user_id=user.id,
            score=score_result['overall_score'],
            snapshot_json=score_result
        )
        db.session.add(history_entry)
        db.session.commit()

        return score_result
