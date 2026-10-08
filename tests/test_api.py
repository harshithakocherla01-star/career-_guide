import unittest
import os
import sys
import json
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from models import db, User, Role, Skill, Milestone
from services.ai_client import AIClient

class TestAPIE2E(unittest.TestCase):
    def setUp(self):
        class TestConfig:
            TESTING = True
            SECRET_KEY = 'test-secret-key-32-bytes-long-for-testing!'
            JWT_SECRET_KEY = 'test-jwt-secret-key-32-bytes-long-for-testing!'
            SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))
            MAX_CONTENT_LENGTH = 16 * 1024 * 1024
            ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
            ANTHROPIC_API_KEY = ''
            GEMINI_API_KEY = ''

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            # Seed test data
            from data.seed import seed_database
            seed_database(self.app)

    def login(self, email, password):
        res = self.client.post('/api/auth/login', json={
            'email': email,
            'password': password
        })
        return res

    def test_auth_login_and_profile(self):
        # 1. Login with seeded candidate Alex
        res = self.login('alex@techtide.io', 'alex123')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        token = data['token']
        self.assertIsNotNone(token)

        # 2. Check profile with JWT
        headers = {'Authorization': f'Bearer {token}'}
        p_res = self.client.get('/api/profile', headers=headers)
        self.assertEqual(p_res.status_code, 200)
        profile = p_res.get_json()
        self.assertEqual(profile['email'], 'alex@techtide.io')
        self.assertEqual(profile['target_role_id'], 1)

    @patch('google.genai.Client')
    def test_gemini_sdk_uses_flask_config_and_configured_interview_model(self, mock_client_factory):
        mock_client = mock_client_factory.return_value
        mock_client.models.generate_content.return_value = SimpleNamespace(text='{"response":"Welcome."}')
        with self.app.app_context():
            self.app.config['GEMINI_API_KEY'] = 'test-server-key'
            self.app.config['INTERVIEW_GEMINI_MODEL'] = 'gemini-3.8-flash'
            from services.interview_agent import InterviewAgent
            agent = InterviewAgent()
            self.assertTrue(agent.client.is_available())
            self.assertEqual(agent.client.gemini_model, 'gemini-3.8-flash')
            result = agent.client._call_gemini('Say hello', 'You are an interviewer.')

        self.assertEqual(result, '{"response":"Welcome."}')
        mock_client_factory.assert_called_once()
        mock_client.models.generate_content.assert_called_once()
        sdk_call = mock_client.models.generate_content.call_args.kwargs
        self.assertEqual(sdk_call['model'], 'gemini-3.8-flash')
        self.assertEqual(sdk_call['contents'], 'Say hello')
        mock_client.close.assert_called_once()

    def test_resume_nlp_extraction(self):
        self.login('alex@techtide.io', 'alex123')

        resume_sample = """
        Alex Rivera
        Email: alex.test@example.com
        Full Stack Engineer with 3 years experience building apps in Python, Flask, and React.
        Extensive knowledge of Docker containerization and PostgreSQL databases.
        Built REST APIs and deployed scalable microservices.
        """
        res = self.client.post('/api/resume/upload', json={'raw_text': resume_sample})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['extracted_skills_count'] > 0)
        self.assertTrue(data['ats_score'] > 0)

        # Check extracted skills contain python and docker
        extracted_ids = [s['skill_id'] for s in data['parsed_data']['skills']]
        self.assertIn('python', extracted_ids)
        self.assertIn('docker', extracted_ids)

    def test_gap_analysis_and_scoring(self):
        self.login('alex@techtide.io', 'alex123')

        res = self.client.post('/api/analysis/run')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('score', data)
        self.assertIn('gaps', data)
        self.assertIn('priorities', data)
        self.assertTrue(0 <= data['score']['overall_score'] <= 100)

    def test_roadmap_generation_and_progress_tracking(self):
        self.login('alex@techtide.io', 'alex123')

        # 1. Generate roadmap
        gen_res = self.client.post('/api/roadmap/generate')
        self.assertEqual(gen_res.status_code, 200)
        roadmap = gen_res.get_json()['roadmap']
        self.assertTrue(len(roadmap['milestones']) > 0)

        first_milestone = roadmap['milestones'][0]
        self.assertEqual(first_milestone['status'], 'pending')

        # 2. Check off milestone 1 -> should increase skill levels and live score
        patch_res = self.client.patch(f"/api/milestones/{first_milestone['id']}", json={'status': 'completed'})
        self.assertEqual(patch_res.status_code, 200)
        patch_data = patch_res.get_json()
        self.assertEqual(patch_data['milestone']['status'], 'completed')
        self.assertIn('updated_score', patch_data)

    def test_interview_session_and_scoring(self):
        self.login('alex@techtide.io', 'alex123')

        # Start interview
        start_res = self.client.post('/api/interview/start')
        self.assertEqual(start_res.status_code, 200)
        data = start_res.get_json()
        session_id = data['session_id']
        self.assertTrue(len(data['questions']) >= 3)

        # Submit answer
        ans_res = self.client.post('/api/interview/answer', json={
            'session_id': session_id,
            'question_index': 0,
            'answer': 'The JavaScript event loop continuously monitors the call stack and message queue. When the call stack is empty, microtasks like promises are processed before macrotasks.'
        })
        self.assertEqual(ans_res.status_code, 200)
        eval_data = ans_res.get_json()['evaluation']
        self.assertTrue(1.0 <= eval_data['score'] <= 5.0)
        self.assertIn('strengths', eval_data)

    @patch('blueprints.interview.InterviewAgent.evaluate')
    @patch('blueprints.interview.InterviewAgent.respond', return_value='That sounds useful. How did you validate the design under load?')
    @patch('blueprints.interview.InterviewAgent.opening', return_value='Welcome, Alex. Tell me about a recent project you enjoyed building.')
    def test_configured_virtual_interview_persists_turns_and_report(self, _opening, _respond, mock_evaluate):
        mock_evaluate.return_value = {
            'overall_score': 82,
            'communication': 86,
            'technical_knowledge': 80,
            'problem_solving': 81,
            'confidence_clarity': 79,
            'summary': 'Clear answers with useful implementation detail.',
            'strengths': ['Explained implementation choices'],
            'weaknesses': ['Could quantify performance outcomes'],
            'areas_to_improve': ['Add measured outcomes to examples'],
            'recommended_topics': ['Load testing'],
            'next_practice_interview': 'Practice a system design interview.',
            'closing_message': 'Thank you for discussing your project. This interview is complete.'
        }
        self.login('alex@techtide.io', 'alex123')
        page = self.client.get('/interview')
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'Start Virtual Interview', page.data)
        start = self.client.post('/api/interview/start', json={
            'role_id': 1,
            'experience_level': 'Intermediate',
            'interview_type': 'Mixed',
            'duration_minutes': 10,
            'difficulty': 'Medium',
            'job_description': 'Build scalable web services.'
        })
        self.assertEqual(start.status_code, 200)
        session_id = start.get_json()['session_id']
        self.assertIn('Welcome, Alex', start.get_json()['initial_question'])

        turn = self.client.post('/api/interview/respond', json={
            'session_id': session_id,
            'response': 'I built a Flask API and used a load test to check its response time.'
        })
        self.assertEqual(turn.status_code, 200)
        self.assertIn('validate the design under load', turn.get_json()['interviewer_message']['text'])

        session = self.client.get(f'/api/interview/session/{session_id}')
        self.assertEqual(session.status_code, 200)
        messages = session.get_json()['messages']
        self.assertEqual([message['speaker'] for message in messages], ['interviewer', 'candidate', 'interviewer'])
        self.assertTrue(messages[0]['created_at'])

        ended = self.client.post('/api/interview/end', json={'session_id': session_id})
        self.assertEqual(ended.status_code, 200)
        self.assertEqual(ended.get_json()['report']['overall_score'], 82)
        self.assertTrue(ended.get_json()['closing_message']['text'].startswith('Thank you'))

        history = self.client.get('/api/interview/history').get_json()['interviews']
        matching = next(item for item in history if item['session_id'] == session_id)
        self.assertEqual(matching['overall_score'], 82)
        self.assertTrue(matching['has_report'])
        report = self.client.get(f'/api/interview/report/{session_id}')
        self.assertEqual(report.get_json()['report']['technical_knowledge'], 80)
        transcript = self.client.get(f'/api/interview/transcript/{session_id}')
        self.assertEqual(transcript.mimetype, 'text/plain')
        self.assertIn(b'Candidate:', transcript.data)

    def test_reportlab_pdf_download(self):
        self.login('alex@techtide.io', 'alex123')

        # Ensure roadmap exists first
        self.client.post('/api/roadmap/generate')

        # Download PDF
        pdf_res = self.client.get('/api/report/pdf')
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.mimetype, 'application/pdf')
        self.assertTrue(len(pdf_res.data) > 1000)

    def test_admin_analytics_and_crud(self):
        # Login as Admin
        self.login('admin@techtide.io', 'admin123')

        # 1. Get analytics
        a_res = self.client.get('/api/admin/analytics/skill-gaps')
        self.assertEqual(a_res.status_code, 200)
        a_data = a_res.get_json()
        self.assertTrue(a_data['total_candidates'] >= 1)

        # 2. Create new role
        role_res = self.client.post('/api/admin/roles', json={
            'title': 'AI Safety Researcher',
            'description': 'Researches alignment, red-teaming, and model safety benchmarks.',
            'domain': 'AI Research'
        })
        self.assertEqual(role_res.status_code, 201)

if __name__ == '__main__':
    unittest.main()
