import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engines.normalizer import SkillNormalizer
from engines.gap_analyzer import GapAnalyzer
from engines.scorer import ReadinessScorer
from engines.prioritizer import MissingSkillPrioritizer
from engines.recommender import RoleRecommender

class TestEngines(unittest.TestCase):
    def setUp(self):
        self.taxonomy = [
            {'id': 'python', 'name': 'Python', 'category': 'Languages', 'synonyms': ['py', 'python3'], 'prerequisites': []},
            {'id': 'pandas', 'name': 'Pandas', 'category': 'Data Science', 'synonyms': ['pandas-df'], 'prerequisites': ['python']},
            {'id': 'scikit_learn', 'name': 'Scikit-Learn', 'category': 'Machine Learning', 'synonyms': ['sklearn'], 'prerequisites': ['pandas']},
            {'id': 'docker', 'name': 'Docker', 'category': 'DevOps', 'synonyms': ['docker-compose', 'containerization'], 'prerequisites': []},
            {'id': 'react', 'name': 'React', 'category': 'Frontend', 'synonyms': ['reactjs', 'react.js'], 'prerequisites': []}
        ]

    def test_normalizer(self):
        norm = SkillNormalizer(self.taxonomy)
        self.assertEqual(norm.normalize("ReactJS"), "react")
        self.assertEqual(norm.normalize("react.js"), "react")
        self.assertEqual(norm.normalize("python3"), "python")
        self.assertEqual(norm.normalize("sklearn"), "scikit_learn")
        self.assertIsNone(norm.normalize("nonexistent_skill_xyz"))

    def test_gap_analyzer(self):
        analyzer = GapAnalyzer()
        reqs = [
            {'skill_id': 'python', 'skill_name': 'Python', 'category': 'Languages', 'weight': 1.0, 'required_level': 4},
            {'skill_id': 'pandas', 'skill_name': 'Pandas', 'category': 'Data Science', 'weight': 0.8, 'required_level': 3},
            {'skill_id': 'docker', 'skill_name': 'Docker', 'category': 'DevOps', 'weight': 0.7, 'required_level': 3}
        ]
        # User has Python level 4 (matched), Pandas level 2 (partial), Docker level 0 (missing)
        user_skills = {'python': 4, 'pandas': 2}
        
        result = analyzer.analyze(reqs, user_skills)
        self.assertEqual(len(result['matched']), 1)
        self.assertEqual(result['matched'][0]['skill_id'], 'python')
        self.assertEqual(len(result['partial']), 1)
        self.assertEqual(result['partial'][0]['skill_id'], 'pandas')
        self.assertEqual(len(result['missing']), 1)
        self.assertEqual(result['missing'][0]['skill_id'], 'docker')

    def test_readiness_scorer_and_point_losses(self):
        scorer = ReadinessScorer()
        reqs = [
            {'skill_id': 'python', 'skill_name': 'Python', 'category': 'Languages', 'weight': 1.0, 'required_level': 4},
            {'skill_id': 'docker', 'skill_name': 'Docker', 'category': 'DevOps', 'weight': 1.0, 'required_level': 4}
        ]
        # Total weight = 2.0. Python: min(4/4, 1) = 1.0. Docker: min(0/4, 1) = 0.0.
        # Score = 100 * (1.0 * 1.0 + 1.0 * 0) / 2.0 = 50.0
        user_skills = {'python': 4}
        res = scorer.calculate_score(reqs, user_skills)

        self.assertEqual(res['overall_score'], 50.0)
        self.assertEqual(len(res['point_losses']), 1)
        self.assertEqual(res['point_losses'][0]['skill_id'], 'docker')
        self.assertEqual(res['point_losses'][0]['points_lost'], 50.0)
        self.assertIn("Missing Docker", res['point_losses'][0]['explanation'])

    def test_prioritizer_dag_ordering(self):
        prioritizer = MissingSkillPrioritizer(self.taxonomy)
        gaps = [
            {'skill_id': 'scikit_learn', 'skill_name': 'Scikit-Learn', 'category': 'ML', 'weight': 1.0, 'required_level': 4, 'user_level': 0, 'effort_weeks': 2.0},
            {'skill_id': 'pandas', 'skill_name': 'Pandas', 'category': 'Data Science', 'weight': 0.8, 'required_level': 3, 'user_level': 0, 'effort_weeks': 1.5},
            {'skill_id': 'python', 'skill_name': 'Python', 'category': 'Languages', 'weight': 0.9, 'required_level': 4, 'user_level': 0, 'effort_weeks': 2.0}
        ]
        # Scikit-Learn requires Pandas; Pandas requires Python.
        # Regardless of weights, Python MUST come before Pandas, and Pandas MUST come before Scikit-Learn!
        ordered = prioritizer.prioritize(gaps, self.taxonomy)
        sids = [item['skill_id'] for item in ordered]
        
        python_idx = sids.index('python')
        pandas_idx = sids.index('pandas')
        sklearn_idx = sids.index('scikit_learn')

        self.assertTrue(python_idx < pandas_idx, "Python must precede Pandas")
        self.assertTrue(pandas_idx < sklearn_idx, "Pandas must precede Scikit-Learn")

    def test_recommender_cosine_similarity(self):
        recommender = RoleRecommender(self.taxonomy)
        
        class MockRole:
            def __init__(self, id, title, domain, role_skills):
                self.id = id
                self.title = title
                self.domain = domain
                self.role_skills = role_skills

        role_py = MockRole(1, "Python Developer", "Backend", [
            {'skill_id': 'python', 'skill_name': 'Python', 'weight': 1.0, 'required_level': 4},
            {'skill_id': 'pandas', 'skill_name': 'Pandas', 'weight': 0.8, 'required_level': 3}
        ])

        role_fe = MockRole(2, "Frontend Developer", "Frontend", [
            {'skill_id': 'react', 'skill_name': 'React', 'weight': 1.0, 'required_level': 4}
        ])

        # Candidate knows Python well
        user_skills = {'python': 4, 'pandas': 3}
        recs = recommender.recommend(user_skills, [role_py, role_fe], self.taxonomy)

        # Python Developer must be ranked first with higher match percentage
        self.assertEqual(recs[0]['role_id'], 1)
        self.assertTrue(recs[0]['match_percentage'] > recs[1]['match_percentage'])

if __name__ == '__main__':
    unittest.main()
