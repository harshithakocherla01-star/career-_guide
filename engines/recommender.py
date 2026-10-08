import numpy as np

class RoleRecommender:
    def __init__(self, all_skills=None):
        self.skill_ids = []
        if all_skills:
            self.load_skills(all_skills)

    def load_skills(self, all_skills):
        items = all_skills.values() if isinstance(all_skills, dict) else all_skills
        self.skill_ids = sorted([s.id if hasattr(s, 'id') else s['id'] for s in items])

    def recommend(self, user_skills, roles, all_skills=None):
        """
        user_skills: list of UserSkill or dict {skill_id: level}
        roles: list of Role objects (with role_skills)
        all_skills: list of all Skill objects in taxonomy
        
        Returns:
            list of ranked role matches:
            [
                {
                    'role_id': int,
                    'title': str,
                    'domain': str,
                    'match_percentage': float,
                    'unlock_skills': [
                        {'skill_id': str, 'skill_name': str, 'weight': float, 'gain': float}, ...
                    ]
                },
                ...
            ]
        """
        if all_skills:
            self.load_skills(all_skills)

        if not self.skill_ids:
            return []

        skill_index_map = {sid: idx for idx, sid in enumerate(self.skill_ids)}
        N = len(self.skill_ids)

        # 1. Build User Vector
        user_vector = np.zeros(N, dtype=np.float64)
        user_skill_map = {}
        if isinstance(user_skills, dict):
            user_skill_map = user_skills
        elif isinstance(user_skills, list):
            for item in user_skills:
                sid = item.skill_id if hasattr(item, 'skill_id') else item.get('skill_id')
                lvl = item.level if hasattr(item, 'level') else item.get('level', 1)
                user_skill_map[sid] = lvl

        for sid, lvl in user_skill_map.items():
            if sid in skill_index_map:
                user_vector[skill_index_map[sid]] = float(lvl)

        user_norm = np.linalg.norm(user_vector)

        recommendations = []

        for role in roles:
            role_id = role.id if hasattr(role, 'id') else role.get('id')
            role_title = role.title if hasattr(role, 'title') else role.get('title')
            domain = role.domain if hasattr(role, 'domain') else role.get('domain', 'General')
            reqs = role.role_skills if hasattr(role, 'role_skills') else role.get('role_skills', [])

            role_vector = np.zeros(N, dtype=np.float64)
            missing_or_partial_skills = []

            for req in reqs:
                sid = req.skill_id if hasattr(req, 'skill_id') else req.get('skill_id')
                weight = float(req.weight if hasattr(req, 'weight') else req.get('weight', 1.0))
                req_level = float(req.required_level if hasattr(req, 'required_level') else req.get('required_level', 3))
                sname = (req.skill.name if hasattr(req, 'skill') and req.skill else None) or \
                        (req.skill_name if hasattr(req, 'skill_name') else sid)

                if sid in skill_index_map:
                    role_vector[skill_index_map[sid]] = weight * req_level

                u_lvl = float(user_skill_map.get(sid, 0))
                if u_lvl < req_level:
                    impact = weight * (req_level - u_lvl)
                    missing_or_partial_skills.append({
                        'skill_id': sid,
                        'skill_name': sname,
                        'weight': weight,
                        'impact': impact,
                        'required_level': int(req_level),
                        'user_level': int(u_lvl)
                    })

            role_norm = np.linalg.norm(role_vector)

            if user_norm > 0 and role_norm > 0:
                dot_product = float(np.dot(user_vector, role_vector))
                cos_sim = dot_product / (user_norm * role_norm)
                # Map to [0, 100]
                match_pct = round(max(0.0, min(100.0, cos_sim * 100.0)), 1)
            else:
                match_pct = 0.0

            # Rank unlock skills by impact
            missing_or_partial_skills.sort(key=lambda x: x['impact'], reverse=True)
            top_unlock_skills = missing_or_partial_skills[:3]

            recommendations.append({
                'role_id': role_id,
                'title': role_title,
                'domain': domain,
                'match_percentage': match_pct,
                'unlock_skills': top_unlock_skills
            })

        # Rank all roles by match percentage descending
        recommendations.sort(key=lambda x: x['match_percentage'], reverse=True)
        return recommendations
