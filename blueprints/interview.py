from flask import Blueprint, request, jsonify, Response
from datetime import datetime, timezone, timedelta
from models import db, Role, RoleSkill, UserSkill, InterviewSession, InterviewRun, InterviewMessage, InterviewReport
from engines.gap_analyzer import GapAnalyzer
from services.ai_client import AIClient
from services.interview_agent import InterviewAgent, InterviewAgentError
from blueprints.auth_helper import get_current_user, login_required

interview_bp = Blueprint('interview', __name__)

CURATED_QUESTION_BANK = {
    'javascript': [
        "Explain how the JavaScript Event Loop handles asynchronous callbacks, microtasks (Promises), and macrotasks (setTimeout).",
        "What are the key differences between closures, lexical scoping, and execution contexts in modern JavaScript?"
    ],
    'react': [
        "How does React's reconciliation algorithm (Virtual DOM diffing) work, and when should you reach for useMemo vs useCallback?",
        "Compare different state management patterns in React (Context API vs Redux vs Zustand) for enterprise-scale web apps."
    ],
    'docker': [
        "How do Docker multi-stage builds optimize production image sizes and reduce attack surfaces?",
        "Explain the difference between Docker bridge networks, host networking, and overlay networks in distributed setups."
    ],
    'postgresql': [
        "How do B-tree vs GIN indexes work in PostgreSQL, and how do you analyze an execution plan using EXPLAIN ANALYZE?",
        "Explain ACID transactions in PostgreSQL and how different isolation levels (Read Committed vs Serializable) prevent race conditions."
    ],
    'python': [
        "Explain Python's Global Interpreter Lock (GIL), its implications for CPU-bound vs I/O-bound tasks, and how to circumvent it.",
        "How do Python generators and the yield statement optimize memory usage when processing massive streams of data?"
    ],
    'rest_api': [
        "What makes an API truly RESTful (Richardson Maturity Model), and how do you handle idempotent actions and caching headers?",
        "How do you design a secure token-based authentication and refresh token rotation architecture for microservices?"
    ],
    'system_design': [
        "How would you design a distributed caching layer using Redis to prevent cache stampedes, cache penetration, and hot keys?",
        "Explain horizontal vs vertical scaling and how database sharding differs from read replication."
    ],
    'security_basics': [
        "Describe the OWASP Top 10 vulnerabilities (specifically SQL Injection, XSS, and CSRF) and effective mitigation strategies.",
        "How does public key cryptography work in SSL/TLS handshakes, and why are HTTPS certificates critical?"
    ],
    'linux': [
        "Explain how Linux file permissions, inode numbers, and process states (zombie vs orphan) work in server administration.",
        "What shell commands and system tools do you use to diagnose memory leaks, high CPU load, and network bottlenecks?"
    ]
}

@interview_bp.route('/api/interview/start', methods=['POST'])
@login_required
def start_interview():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    configured_run = bool(data)
    requested_role_id = data.get('role_id') or user.target_role_id
    if not requested_role_id:
        return jsonify({'error': 'Target role not set'}), 400

    role = db.session.get(Role, requested_role_id)
    if not role:
        return jsonify({'error': 'Selected role was not found'}), 400

    if configured_run:
        config = {
            'role_id': role.id,
            'experience_level': data.get('experience_level', 'Intermediate'),
            'interview_type': data.get('interview_type', 'Mixed'),
            'duration_minutes': data.get('duration_minutes', 20),
            'difficulty': data.get('difficulty', 'Medium'),
            'job_description': (data.get('job_description') or '').strip()[:5000],
            'candidate_name': user.name
        }
        if config['experience_level'] not in ('Beginner', 'Intermediate', 'Advanced'):
            return jsonify({'error': 'Invalid experience level'}), 400
        if config['interview_type'] not in ('Technical', 'HR', 'Behavioral', 'Mixed'):
            return jsonify({'error': 'Invalid interview type'}), 400
        if config['duration_minutes'] not in (10, 20, 30):
            return jsonify({'error': 'Interview duration must be 10, 20, or 30 minutes'}), 400
        if config['difficulty'] not in ('Easy', 'Medium', 'Hard'):
            return jsonify({'error': 'Invalid interview difficulty'}), 400
        try:
            opening = InterviewAgent().opening(config, role.title)
        except InterviewAgentError as exc:
            return jsonify({'error': str(exc)}), 503

        session = InterviewSession(user_id=user.id, role_id=role.id)
        session.questions_json = [opening]
        session.answers_json = []
        session.score = 0
        run = InterviewRun(user_id=user.id)
        run.config = config
        db.session.add(session)
        db.session.flush()
        run.session_id = session.id
        db.session.add(run)
        db.session.add(InterviewMessage(session_id=session.id, speaker='interviewer', text=opening))
        db.session.commit()
        return jsonify({
            'session_id': session.id,
            'role_title': role.title,
            'initial_question': opening,
            'status': run.status,
            'started_at': _iso_utc(run.started_at),
            'duration_minutes': config['duration_minutes'],
            'messages': [message.to_dict() for message in session.messages]
        })

    # Backward-compatible preparation and scoring route for existing clients.
    reqs = RoleSkill.query.filter_by(role_id=role.id).all()
    user_skills = UserSkill.query.filter_by(user_id=user.id).all()

    gap_analyzer = GapAnalyzer()
    gaps = gap_analyzer.analyze(reqs, user_skills)
    priority_gaps = gaps['missing'] + gaps['partial']
    top_gap_ids = [g['skill_id'] for g in priority_gaps[:3]]

    # Generate 4-5 questions
    questions = []
    ai_client = AIClient()

    if ai_client.is_available():
        system_prompt = "You are a senior technical interviewer. Generate 4 concise, high-impact interview questions tailored to the role and candidate skill gaps. Return a JSON list of strings."
        prompt = f"Role: {role.title}. Skills to probe: {top_gap_ids}. Return JSON: [\"Question 1\", \"Question 2\", ...]"
        raw = ai_client.call_llm(prompt, system_prompt)
        parsed = ai_client.parse_json_safely(raw)
        if isinstance(parsed, list) and len(parsed) >= 3:
            questions = parsed[:4]

    if not questions:
        # Grounded fallback questions
        for sid in top_gap_ids:
            if sid in CURATED_QUESTION_BANK:
                questions.append(CURATED_QUESTION_BANK[sid][0])
        # Add general role questions if needed
        if len(questions) < 4:
            for sid, q_list in CURATED_QUESTION_BANK.items():
                if q_list[0] not in questions:
                    questions.append(q_list[0])
                if len(questions) >= 4:
                    break

    session = InterviewSession(
        user_id=user.id,
        role_id=role.id
    )
    session.questions_json = questions[:1]
    session.answers_json = []
    session.score = 0.0
    db.session.add(session)
    db.session.commit()

    return jsonify({
        'session_id': session.id,
        'role_title': role.title,
        'questions': questions,
        'initial_question': questions[0],
        'total_questions': len(questions)
    })

@interview_bp.route('/api/interview/answer', methods=['POST'])
@login_required
def submit_answer():
    user = get_current_user()
    data = request.get_json() or {}
    session_id = data.get('session_id')
    q_index = data.get('question_index', 0)
    answer_text = data.get('answer', '').strip()

    session = db.session.get(InterviewSession, session_id)
    if not session or session.user_id != user.id:
        return jsonify({'error': 'Interview session not found'}), 404

    questions = session.questions_json
    if q_index >= len(questions):
        return jsonify({'error': 'Invalid question index'}), 400

    target_question = questions[q_index]

    # Evaluation (AI or deterministic rubric)
    eval_result = _evaluate_answer(target_question, answer_text, session.role.title if session.role else "Engineering")

    # Update session answers
    current_answers = session.answers_json
    # Replace or append
    while len(current_answers) <= q_index:
        current_answers.append(None)
    
    current_answers[q_index] = {
        'question': target_question,
        'answer': answer_text,
        'score': eval_result['score'],
        'strengths': eval_result['strengths'],
        'areas_for_improvement': eval_result['areas_for_improvement'],
        'ideal_key_points': eval_result['ideal_key_points']
    }
    session.answers_json = current_answers

    # Compute average score
    valid_scores = [a['score'] for a in current_answers if a and 'score' in a]
    if valid_scores:
        session.score = round(sum(valid_scores) / len(valid_scores), 1)

    db.session.commit()

    return jsonify({
        'evaluation': eval_result,
        'session_average_score': session.score,
        'answered_count': len([a for a in current_answers if a])
    })

@interview_bp.route('/api/interview/turn', methods=['POST'])
@login_required
def interview_turn():
    """Continue a spoken or typed interview as a real conversational turn."""
    user = get_current_user()
    data = request.get_json() or {}
    session = db.session.get(InterviewSession, data.get('session_id'))
    answer = (data.get('answer') or '').strip()
    if not session or session.user_id != user.id:
        return jsonify({'error': 'Interview session not found'}), 404
    if not answer:
        return jsonify({'error': 'Please provide an answer'}), 400
    if len(answer) > 12000:
        return jsonify({'error': 'Answer is too long'}), 400

    history = session.answers_json or []
    previous_questions = session.questions_json or []
    question = previous_questions[-1] if previous_questions else 'Tell me about your experience.'
    role_title = session.role.title if session.role else 'Engineering'
    evaluation = _evaluate_answer(question, answer, role_title)
    history.append({
        'question': question,
        'answer': answer,
        'score': evaluation['score'],
        'strengths': evaluation['strengths'],
        'areas_for_improvement': evaluation['areas_for_improvement'],
        'ideal_key_points': evaluation['ideal_key_points']
    })

    turn_count = len(history)
    finished = turn_count >= 6
    ai_client = AIClient()
    interviewer_reply = None
    if ai_client.is_available():
        system_prompt = (
            'You are a warm but rigorous human-style technical interviewer. Conduct a natural live interview. '
            'Respond briefly to what the candidate just said, then ask exactly one relevant follow-up question. '
            'Probe vague claims, ask for examples or trade-offs, and adapt to previous turns. Do not give scores, '
            'feedback, or ideal answers during the interview. Return strict JSON: {"response": "..."}.'
        )
        transcript = []
        for item in history:
            transcript.extend([
                {'role': 'interviewer', 'text': item['question']},
                {'role': 'candidate', 'text': item['answer']}
            ])
        if previous_questions and len(previous_questions) > len(history):
            transcript.insert(0, {'role': 'interviewer', 'text': previous_questions[0]})
        prompt = f'Role: {role_title}\nInterview transcript: {transcript}\n\nReply as the interviewer with a concise acknowledgement and one follow-up question.'
        raw = ai_client.call_llm(prompt, system_prompt)
        parsed = ai_client.parse_json_safely(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get('response'), str):
            interviewer_reply = parsed['response'].strip()

    if not interviewer_reply:
        if evaluation['score'] < 3:
            interviewer_reply = 'Thanks for sharing that. Could you walk me through a concrete example and explain what you personally did?'
        elif turn_count == 1:
            interviewer_reply = 'That gives me a useful starting point. What trade-offs did you consider, and why did you choose that approach?'
        else:
            interviewer_reply = 'I see. How would you handle a failure or performance issue in that design?'
    if finished:
        interviewer_reply = 'Thanks, that covers the interview. I appreciate you walking me through your thinking. Select “Finish interview” to see your feedback.'

    questions = list(previous_questions)
    questions.append(interviewer_reply)
    session.questions_json = questions
    session.answers_json = history
    session.score = round(sum(item['score'] for item in history) / len(history), 1)
    db.session.commit()
    return jsonify({
        'response': interviewer_reply,
        'evaluation': evaluation,
        'session_average_score': session.score,
        'turn_count': turn_count,
        'finished': finished
    })


def _iso_utc(value):
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _owned_run(session_id, user_id):
    return InterviewRun.query.filter_by(session_id=session_id, user_id=user_id).first()


def _run_transcript(session_id):
    return InterviewMessage.query.filter_by(session_id=session_id).order_by(InterviewMessage.created_at, InterviewMessage.id).all()


def _run_is_expired(run):
    started = run.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    duration = int(run.config.get('duration_minutes', 20))
    return datetime.now(timezone.utc) >= started + timedelta(minutes=duration)


@interview_bp.route('/api/interview/respond', methods=['POST'])
@login_required
def respond_to_interview():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    session = db.session.get(InterviewSession, data.get('session_id'))
    if not session or session.user_id != user.id:
        return jsonify({'error': 'Interview session not found'}), 404
    run = _owned_run(session.id, user.id)
    if not run:
        return jsonify({'error': 'This session does not support live interviewer turns'}), 409
    if run.status != 'active':
        return jsonify({'error': 'This interview has ended. Start a new interview to continue.'}), 409
    if _run_is_expired(run):
        run.status = 'expired'
        run.ended_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'error': 'The interview time has ended. End the interview to generate your report.'}), 410

    candidate_text = (data.get('response') or '').strip()
    if not candidate_text:
        return jsonify({'error': 'We did not receive an answer. Please try speaking again or type your response.'}), 400
    if len(candidate_text) > 12000:
        return jsonify({'error': 'Please keep each answer under 12,000 characters.'}), 400

    messages = _run_transcript(session.id)
    transcript = [{'speaker': message.speaker, 'text': message.text} for message in messages]
    try:
        reply = InterviewAgent().respond(run.config, session.role.title, transcript, candidate_text)
    except InterviewAgentError as exc:
        return jsonify({'error': str(exc)}), 503

    candidate_message = InterviewMessage(session_id=session.id, speaker='candidate', text=candidate_text)
    interviewer_message = InterviewMessage(session_id=session.id, speaker='interviewer', text=reply)
    db.session.add_all([candidate_message, interviewer_message])
    questions = session.questions_json or []
    questions.append(reply)
    session.questions_json = questions
    db.session.commit()
    return jsonify({
        'messages': [candidate_message.to_dict(), interviewer_message.to_dict()],
        'candidate_message': candidate_message.to_dict(),
        'interviewer_message': interviewer_message.to_dict(),
        'question_number': len([message for message in messages if message.speaker == 'interviewer']) + 1
    })


@interview_bp.route('/api/interview/end', methods=['POST'])
@login_required
def end_interview():
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    session = db.session.get(InterviewSession, data.get('session_id'))
    if not session or session.user_id != user.id:
        return jsonify({'error': 'Interview session not found'}), 404
    run = _owned_run(session.id, user.id)
    if not run:
        return jsonify({'error': 'Interview session not found'}), 404
    existing = InterviewReport.query.filter_by(session_id=session.id).first()
    if existing:
        return jsonify({'session_id': session.id, 'status': run.status, 'report': existing.report})

    messages = _run_transcript(session.id)
    transcript = [{'speaker': message.speaker, 'text': message.text} for message in messages]
    if not any(message.speaker == 'candidate' for message in messages):
        return jsonify({'error': 'Answer at least one interview question before ending to receive an evaluation.'}), 400
    try:
        report_data = InterviewAgent().evaluate(run.config, session.role.title, transcript)
    except InterviewAgentError as exc:
        return jsonify({'error': str(exc)}), 503

    report = InterviewReport(session_id=session.id)
    report.report = report_data
    db.session.add(report)
    closing = InterviewMessage(session_id=session.id, speaker='interviewer', text=report_data['closing_message'])
    db.session.add(closing)
    run.status = 'expired' if run.status == 'expired' or _run_is_expired(run) else 'completed'
    run.ended_at = datetime.now(timezone.utc)
    session.score = round(report_data['overall_score'] / 20, 1)
    session.completed_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'session_id': session.id, 'status': run.status, 'report': report_data, 'closing_message': closing.to_dict()})


@interview_bp.route('/api/interview/history', methods=['GET'])
@login_required
def interview_history():
    user = get_current_user()
    runs = InterviewRun.query.filter_by(user_id=user.id).order_by(InterviewRun.started_at.desc()).limit(30).all()
    items = []
    for run in runs:
        session = db.session.get(InterviewSession, run.session_id)
        report = InterviewReport.query.filter_by(session_id=run.session_id).first()
        items.append({
            'session_id': run.session_id,
            'role_title': session.role.title if session and session.role else 'Interview',
            'status': run.status,
            'started_at': _iso_utc(run.started_at),
            'duration_minutes': run.config.get('duration_minutes'),
            'overall_score': report.report.get('overall_score') if report else None,
            'has_report': report is not None
        })
    return jsonify({'interviews': items})


@interview_bp.route('/api/interview/session/<int:session_id>', methods=['GET'])
@login_required
def get_interview_session(session_id):
    user = get_current_user()
    session = db.session.get(InterviewSession, session_id)
    run = _owned_run(session_id, user.id)
    if not session or session.user_id != user.id or not run:
        return jsonify({'error': 'Interview session not found'}), 404
    if run.status == 'active' and _run_is_expired(run):
        run.status = 'expired'
        run.ended_at = datetime.now(timezone.utc)
        db.session.commit()
    report = InterviewReport.query.filter_by(session_id=session.id).first()
    return jsonify({
        'session_id': session.id,
        'role_title': session.role.title if session.role else 'Interview',
        'config': run.config,
        'status': run.status,
        'started_at': _iso_utc(run.started_at),
        'ended_at': _iso_utc(run.ended_at),
        'messages': [message.to_dict() for message in _run_transcript(session.id)],
        'report': report.report if report else None
    })


@interview_bp.route('/api/interview/report/<int:session_id>', methods=['GET'])
@login_required
def interview_report(session_id):
    user = get_current_user()
    session = db.session.get(InterviewSession, session_id)
    if not session or session.user_id != user.id:
        return jsonify({'error': 'Interview session not found'}), 404
    report = InterviewReport.query.filter_by(session_id=session.id).first()
    if not report:
        return jsonify({'error': 'No evaluation report exists for this interview'}), 404
    return jsonify({'session_id': session.id, 'report': report.report})


@interview_bp.route('/api/interview/transcript/<int:session_id>', methods=['GET'])
@login_required
def download_transcript(session_id):
    user = get_current_user()
    session = db.session.get(InterviewSession, session_id)
    run = _owned_run(session_id, user.id)
    if not session or session.user_id != user.id or not run:
        return jsonify({'error': 'Interview session not found'}), 404
    lines = [f"Interview transcript — {session.role.title if session.role else 'Interview'}", '']
    for message in _run_transcript(session.id):
        label = 'AI Interviewer' if message.speaker == 'interviewer' else 'Candidate'
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if message.created_at else ''
        lines.extend([f'[{timestamp}] {label}:', message.text, ''])
    return Response('\n'.join(lines), mimetype='text/plain; charset=utf-8', headers={
        'Content-Disposition': f'attachment; filename=interview-{session.id}-transcript.txt'
    })

def _evaluate_answer(question, answer, role_title):
    ai_client = AIClient()
    if ai_client.is_available() and len(answer) > 20:
        system_prompt = (
            "You are a technical hiring manager. Evaluate the candidate's answer on a scale of 1 to 5. "
            "Return strict JSON with keys: 'score' (float 1.0-5.0), 'strengths' (str), "
            "'areas_for_improvement' (str), 'ideal_key_points' (list of str)."
        )
        prompt = f"Role: {role_title}\nQuestion: {question}\nCandidate Answer: {answer}"
        raw = ai_client.call_llm(prompt, system_prompt)
        parsed = ai_client.parse_json_safely(raw)
        if isinstance(parsed, dict) and 'score' in parsed:
            return parsed

    # Deterministic rule-based evaluation rubric
    word_count = len(answer.split())
    if word_count < 15:
        score = 1.5
        strengths = "Attempted an initial response."
        areas = "The answer is too brief. Provide architectural context, concrete technical terms, and real-world trade-offs."
    elif word_count < 45:
        score = 3.0
        strengths = "Identified the primary concept and addressed the prompt directly."
        areas = "Include specific implementation details, edge cases, and performance considerations."
    elif word_count < 90:
        score = 4.0
        strengths = "Clear, articulate explanation covering mechanisms, trade-offs, and best practices."
        areas = "To reach perfection (5/5), elaborate on production reliability, failure modes, and monitoring."
    else:
        score = 4.8
        strengths = "Comprehensive, senior-level response demonstrating deep architectural understanding."
        areas = "Maintain high-level executive clarity while discussing low-level mechanics."

    return {
        'score': score,
        'strengths': strengths,
        'areas_for_improvement': areas,
        'ideal_key_points': [
            "Clear technical definition and architecture diagram/flow",
            "Real-world trade-offs (e.g. latency vs consistency, memory vs CPU)",
            "Edge cases and production failure modes"
        ]
    }

@interview_bp.route('/api/interview/summary', methods=['GET'])
@login_required
def get_interview_summary():
    user = get_current_user()
    session = InterviewSession.query.filter_by(user_id=user.id).order_by(InterviewSession.completed_at.desc()).first()
    if not session:
        return jsonify({'message': 'No interview sessions recorded'}), 200

    return jsonify({
        'session': session.to_dict()
    })
