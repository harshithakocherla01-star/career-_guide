import logging
from flask import current_app, has_app_context
from services.ai_client import AIClient

logger = logging.getLogger(__name__)

class InterviewAgentError(Exception):
    """Raised when the configured provider cannot produce a usable response."""


class InterviewAgent:
    def __init__(self, client=None):
        config = current_app.config if has_app_context() else {}
        self.client = client or AIClient(
            anthropic_model=config.get('INTERVIEW_ANTHROPIC_MODEL', 'claude-sonnet-4-6'),
            gemini_model=config.get('INTERVIEW_GEMINI_MODEL', 'gemini-3.8-flash'),
            timeout=45
        )

    def _json_response(self, prompt, system_prompt):
        if not self.client.is_available():
            logger.warning('Interview AI requested but no GEMINI_API_KEY or ANTHROPIC_API_KEY is configured on the server')
            raise InterviewAgentError('No AI provider key is configured on the server. Add GEMINI_API_KEY or ANTHROPIC_API_KEY to the project .env file, then restart Flask.')
        raw = self.client.call_llm(prompt, system_prompt)
        if not raw:
            logger.error('Interview AI provider returned no response; check the preceding provider error log')
            raise InterviewAgentError('The AI provider request failed. Check the Flask backend log and try again.')
        parsed = self.client.parse_json_safely(raw)
        if not isinstance(parsed, dict):
            logger.warning('Interview AI provider response was not valid JSON')
            raise InterviewAgentError('The AI provider did not return a valid response. Please try again.')
        return parsed

    def opening(self, config, role_title):
        system = (
            'You are a professional, warm, adaptive virtual interviewer. Greet the candidate by first name if provided, '
            'introduce the interview briefly, then ask exactly one focused opening question. Never present multiple questions. '
            'Return strict JSON with one key: response (string).'
        )
        prompt = (
            f"Candidate: {config.get('candidate_name', 'Candidate')}\nRole: {role_title}\n"
            f"Experience: {config['experience_level']}\nType: {config['interview_type']}\n"
            f"Difficulty: {config['difficulty']}\nJob description: {config.get('job_description') or 'Not provided'}\n"
            'Start the interview with a brief greeting and one relevant first question.'
        )
        response = self._json_response(prompt, system).get('response')
        if not isinstance(response, str) or not response.strip():
            raise InterviewAgentError('The AI interviewer returned an empty opening question. Please try again.')
        return response.strip()

    def respond(self, config, role_title, transcript, candidate_text):
        system = (
            'You are one human-style interviewer conducting a live interview. Listen carefully to the newest candidate answer, '
            'respond naturally in one short sentence that shows you understood it, then ask exactly one useful next question. '
            'Use the transcript to ask contextual follow-ups, probe specifics and trade-offs, and avoid repeating any prior question. '
            'Vary between technical, behavioral, and problem-solving questions according to the configured interview type. '
            'Adjust difficulty to the candidate. Do not score, coach, or reveal ideal answers during the interview. '
            'Keep the complete spoken response under 70 words. Return strict JSON: {"response":"..."}.'
        )
        prompt = (
            f"Role: {role_title}\nExperience: {config['experience_level']}\n"
            f"Interview type: {config['interview_type']}\nDifficulty: {config['difficulty']}\n"
            f"Job description: {config.get('job_description') or 'Not provided'}\n"
            f"Transcript so far: {transcript}\nNewest candidate answer: {candidate_text}\n"
            'Acknowledge the answer and ask one contextual follow-up question.'
        )
        response = self._json_response(prompt, system).get('response')
        if not isinstance(response, str) or not response.strip():
            raise InterviewAgentError('The AI interviewer returned an empty response. Please try again.')
        return response.strip()

    def evaluate(self, config, role_title, transcript):
        system = (
            'You are an evidence-based interview evaluator. Evaluate only what is explicitly supported by the provided transcript. '
            'Do not infer confidence, knowledge, or communication traits without evidence. Give each dimension a score from 0 to 100, '
            'and an overall score from 0 to 100 based on the actual candidate answers. If evidence is limited, reflect that in scores '
            'and state the limitation. Return strict JSON with keys: overall_score (number), communication (number), technical_knowledge '
            '(number), problem_solving (number), confidence_clarity (number), summary (string), strengths (array of strings), '
            'weaknesses (array of strings), areas_to_improve (array of strings), recommended_topics (array of strings), '
            'next_practice_interview (string), closing_message (string). The closing_message should thank the candidate naturally '
            'for this specific conversation and say the interview is complete.'
        )
        prompt = f'Role: {role_title}\nConfiguration: {config}\nActual transcript: {transcript}\nEvaluate the candidate now.'
        report = self._json_response(prompt, system)
        numeric_keys = ('overall_score', 'communication', 'technical_knowledge', 'problem_solving', 'confidence_clarity')
        for key in numeric_keys:
            value = report.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 100:
                raise InterviewAgentError('The AI provider returned an invalid evaluation. Please retry the report.')
            report[key] = round(value)
        for key in ('strengths', 'weaknesses', 'areas_to_improve', 'recommended_topics'):
            if not isinstance(report.get(key), list):
                raise InterviewAgentError('The AI provider returned an incomplete evaluation. Please retry the report.')
        if not isinstance(report.get('summary'), str) or not report['summary'].strip():
            raise InterviewAgentError('The AI provider returned an incomplete evaluation. Please retry the report.')
        if not isinstance(report.get('next_practice_interview'), str):
            report['next_practice_interview'] = 'Practice another interview for this role.'
        if not isinstance(report.get('closing_message'), str) or not report['closing_message'].strip():
            raise InterviewAgentError('The AI provider returned an incomplete closing message. Please retry the report.')
        return report
