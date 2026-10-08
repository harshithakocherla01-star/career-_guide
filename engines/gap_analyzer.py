class GapAnalyzer:
    def __init__(self):
        pass

    def analyze(self, role_requirements, user_skills):
        """
        role_requirements: list of RoleSkill objects or dicts:
            [{'skill_id': str, 'skill_name': str, 'category': str, 'weight': float, 'required_level': int}, ...]
        user_skills: list of UserSkill objects or dict of {skill_id: level}
            or [{'skill_id': str, 'level': int}, ...]
        
        Returns:
            {
                'matched': [...],
                'partial': [...],
                'missing': [...],
                'summary': {
                    'total_skills': int,
                    'matched_count': int,
                    'partial_count': int,
                    'missing_count': int,
                    'match_rate': float
                }
            }
        """
        # Convert user_skills into a lookup dict {skill_id: level}
        user_skill_map = {}
        if isinstance(user_skills, dict):
            user_skill_map = user_skills
        elif isinstance(user_skills, list):
            for item in user_skills:
                if hasattr(item, 'skill_id'):
                    user_skill_map[item.skill_id] = item.level
                elif isinstance(item, dict):
                    user_skill_map[item.get('skill_id')] = item.get('level', 1)

        matched = []
        partial = []
        missing = []

        for req in role_requirements:
            sid = req.skill_id if hasattr(req, 'skill_id') else req.get('skill_id')
            sname = (req.skill.name if hasattr(req, 'skill') and req.skill else None) or \
                    (req.skill_name if hasattr(req, 'skill_name') else None) or \
                    req.get('skill_name', sid)
            cat = (req.skill.category if hasattr(req, 'skill') and req.skill else None) or \
                  (req.category if hasattr(req, 'category') else None) or \
                  req.get('category', 'Technical')
            weight = req.weight if hasattr(req, 'weight') else req.get('weight', 1.0)
            req_level = req.required_level if hasattr(req, 'required_level') else req.get('required_level', 3)
            
            user_level = user_skill_map.get(sid, 0)
            gap = max(0, req_level - user_level)

            item_data = {
                'skill_id': sid,
                'skill_name': sname,
                'category': cat,
                'weight': weight,
                'required_level': req_level,
                'user_level': user_level,
                'gap': gap
            }

            if user_level >= req_level:
                item_data['status'] = 'matched'
                matched.append(item_data)
            elif user_level > 0:
                item_data['status'] = 'partial'
                partial.append(item_data)
            else:
                item_data['status'] = 'missing'
                missing.append(item_data)

        total = len(role_requirements)
        match_rate = round((len(matched) + 0.5 * len(partial)) / total * 100, 1) if total > 0 else 0.0

        return {
            'matched': matched,
            'partial': partial,
            'missing': missing,
            'summary': {
                'total_skills': total,
                'matched_count': len(matched),
                'partial_count': len(partial),
                'missing_count': len(missing),
                'match_rate': match_rate
            }
        }
