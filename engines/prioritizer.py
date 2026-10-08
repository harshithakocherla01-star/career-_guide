from collections import defaultdict, deque

class MissingSkillPrioritizer:
    def __init__(self, skills_taxonomy=None):
        """
        skills_taxonomy: dict or list of skills containing id and prerequisites.
        """
        self.skills_dict = {}
        if skills_taxonomy:
            self.load_taxonomy(skills_taxonomy)

    def load_taxonomy(self, skills_taxonomy):
        items = skills_taxonomy.values() if isinstance(skills_taxonomy, dict) else skills_taxonomy
        for s in items:
            sid = s.id if hasattr(s, 'id') else s.get('id')
            self.skills_dict[sid] = s

    def prioritize(self, gaps, skills_taxonomy=None, default_hours_per_week=10):
        """
        gaps: list of gap dicts from gap_analyzer (partial or missing):
            [{'skill_id': str, 'skill_name': str, 'category': str, 'weight': float,
              'required_level': int, 'user_level': int, 'effort_weeks': float (optional)}, ...]
        
        Formula:
            priority = weight * (required_level - user_level) / effort_weeks
        
        Ordered so prerequisites come first using dependency graph (DAG).
        """
        if skills_taxonomy:
            self.load_taxonomy(skills_taxonomy)

        if not gaps:
            return []

        # 1. Calculate raw priority score for each item
        gap_items = {}
        for item in gaps:
            sid = item['skill_id']
            weight = float(item.get('weight', 1.0))
            req_level = float(item.get('required_level', 3))
            user_level = float(item.get('user_level', 0))
            level_diff = max(1.0, req_level - user_level)
            
            # Estimate effort in weeks if not provided
            # Standard estimate: 1 to 2 weeks per level delta
            effort_weeks = float(item.get('effort_weeks', max(1.0, round(level_diff * 1.5, 1))))
            priority = round(weight * (level_diff / effort_weeks), 3)

            # Get prerequisites from taxonomy
            prereqs = []
            if sid in self.skills_dict:
                skill_obj = self.skills_dict[sid]
                prereqs = skill_obj.prerequisites if hasattr(skill_obj, 'prerequisites') else skill_obj.get('prerequisites', [])

            gap_items[sid] = {
                'skill_id': sid,
                'skill_name': item.get('skill_name', sid),
                'category': item.get('category', 'Technical'),
                'weight': weight,
                'required_level': int(req_level),
                'user_level': int(user_level),
                'level_diff': int(level_diff),
                'effort_weeks': effort_weeks,
                'priority': priority,
                'prerequisites': prereqs or []
            }

        # 2. Dependency Graph (DAG) Kahn's topological sort with priority weighting
        # We only consider prerequisite dependencies that are also in the gap_items list!
        gap_skill_ids = set(gap_items.keys())
        
        in_degree = defaultdict(int)
        graph = defaultdict(list)  # prereq -> list of dependent skills

        for sid, data in gap_items.items():
            for p in data['prerequisites']:
                if p in gap_skill_ids:
                    graph[p].append(sid)
                    in_degree[sid] += 1

        # Skills with in_degree == 0 can be started immediately
        # We sort ready queue by priority descending so high-impact skills come first
        ready_queue = [sid for sid in gap_skill_ids if in_degree[sid] == 0]
        ready_queue.sort(key=lambda x: gap_items[x]['priority'], reverse=True)

        ordered_results = []
        visited = set()

        while ready_queue:
            # Pick highest priority skill from ready queue
            current = ready_queue.pop(0)
            ordered_results.append(gap_items[current])
            visited.add(current)

            # Reduce in-degree for dependents
            newly_ready = []
            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    newly_ready.append(neighbor)

            # Add newly ready skills and re-sort ready queue by priority descending
            ready_queue.extend(newly_ready)
            ready_queue.sort(key=lambda x: gap_items[x]['priority'], reverse=True)

        # In case of cycles, add any remaining unvisited items ordered by priority
        remaining = [gap_items[sid] for sid in gap_skill_ids if sid not in visited]
        remaining.sort(key=lambda x: x['priority'], reverse=True)
        ordered_results.extend(remaining)

        # Add sequence rank and explanation
        for idx, res in enumerate(ordered_results, 1):
            res['rank'] = idx
            res['explanation'] = (
                f"Rank #{idx}: {res['skill_name']} (Priority: {res['priority']}) - "
                f"Weight {res['weight']}, Gap {res['level_diff']} lvls, Est. {res['effort_weeks']} wks"
            )

        return ordered_results
