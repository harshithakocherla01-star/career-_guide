class ReadinessScorer:
    def __init__(self):
        pass

    def calculate_score(self, role_requirements, user_skills):
        """
        Calculates career-readiness score based on:
        score = 100 * SUM( weight_i * min(user_level_i / required_level_i, 1) ) / SUM( weight_i )

        Also computes:
        - Per-category score breakdown
        - Exact point losses for missing and partial skills with explanations
        """
        # Build user_skill_map {skill_id: level}
        user_skill_map = {}
        if isinstance(user_skills, dict):
            user_skill_map = user_skills
        elif isinstance(user_skills, list):
            for item in user_skills:
                if hasattr(item, 'skill_id'):
                    user_skill_map[item.skill_id] = item.level
                elif isinstance(item, dict):
                    user_skill_map[item.get('skill_id')] = item.get('level', 1)

        total_weight = 0.0
        weighted_achieved = 0.0
        
        category_weights = {}
        category_achieved = {}
        
        point_losses = []

        for req in role_requirements:
            sid = req.skill_id if hasattr(req, 'skill_id') else req.get('skill_id')
            sname = (req.skill.name if hasattr(req, 'skill') and req.skill else None) or \
                    (req.skill_name if hasattr(req, 'skill_name') else None) or \
                    req.get('skill_name', sid)
            cat = (req.skill.category if hasattr(req, 'skill') and req.skill else None) or \
                  (req.category if hasattr(req, 'category') else None) or \
                  req.get('category', 'Technical')
            weight = float(req.weight if hasattr(req, 'weight') else req.get('weight', 1.0))
            req_level = float(req.required_level if hasattr(req, 'required_level') else req.get('required_level', 3))
            
            user_level = float(user_skill_map.get(sid, 0))
            ratio = min(user_level / req_level, 1.0)

            total_weight += weight
            weighted_achieved += weight * ratio

            # Category tracking
            category_weights[cat] = category_weights.get(cat, 0.0) + weight
            category_achieved[cat] = category_achieved.get(cat, 0.0) + (weight * ratio)

        if total_weight <= 0:
            return {
                'overall_score': 0.0,
                'category_scores': {},
                'point_losses': [],
                'formula': "score = 100 * SUM(weight_i * min(user_level / required_level, 1)) / SUM(weight_i)"
            }

        overall_score = round(100.0 * (weighted_achieved / total_weight), 1)

        # Calculate exact point losses
        for req in role_requirements:
            sid = req.skill_id if hasattr(req, 'skill_id') else req.get('skill_id')
            sname = (req.skill.name if hasattr(req, 'skill') and req.skill else None) or \
                    (req.skill_name if hasattr(req, 'skill_name') else None) or \
                    req.get('skill_name', sid)
            cat = (req.skill.category if hasattr(req, 'skill') and req.skill else None) or \
                  (req.category if hasattr(req, 'category') else None) or \
                  req.get('category', 'Technical')
            weight = float(req.weight if hasattr(req, 'weight') else req.get('weight', 1.0))
            req_level = float(req.required_level if hasattr(req, 'required_level') else req.get('required_level', 3))
            user_level = float(user_skill_map.get(sid, 0))
            ratio = min(user_level / req_level, 1.0)

            if ratio < 1.0:
                loss = round(100.0 * (weight * (1.0 - ratio) / total_weight), 1)
                if loss > 0.0:
                    status_text = "Missing" if user_level == 0 else f"Partial (Level {int(user_level)}/{int(req_level)})"
                    explanation = f"{status_text} {sname} (weight {weight}) costs {loss} pts"
                    point_losses.append({
                        'skill_id': sid,
                        'skill_name': sname,
                        'category': cat,
                        'weight': weight,
                        'user_level': int(user_level),
                        'required_level': int(req_level),
                        'points_lost': loss,
                        'explanation': explanation
                    })

        # Sort point losses by points lost descending
        point_losses.sort(key=lambda x: x['points_lost'], reverse=True)

        # Calculate category scores
        category_scores = {}
        for cat, w in category_weights.items():
            if w > 0:
                category_scores[cat] = round(100.0 * (category_achieved[cat] / w), 1)
            else:
                category_scores[cat] = 0.0

        return {
            'overall_score': overall_score,
            'category_scores': category_scores,
            'point_losses': point_losses,
            'formula': "score = 100 * SUM(weight_i * min(user_level_i / required_level_i, 1)) / SUM(weight_i)"
        }
