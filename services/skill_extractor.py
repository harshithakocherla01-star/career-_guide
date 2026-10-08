import re
import json
from engines.normalizer import SkillNormalizer
from services.ai_client import AIClient

class SkillExtractor:
    def __init__(self, skills_taxonomy=None):
        self.normalizer = SkillNormalizer(skills_taxonomy)
        self.ai_client = AIClient()
        self.skills_taxonomy = skills_taxonomy or []

    def set_taxonomy(self, skills_taxonomy):
        self.skills_taxonomy = skills_taxonomy
        self.normalizer.load_taxonomy(skills_taxonomy)

    def extract(self, resume_text):
        """
        Extracts structured data from resume text.
        Attempts LLM extraction first if configured; falls back to rule-based engine.
        Returns a dictionary matching the specification.
        """
        if not resume_text or not resume_text.strip():
            return self._empty_result()

        # If LLM is available, attempt AI extraction
        if self.ai_client.is_available():
            ai_result = self._extract_with_llm(resume_text)
            if ai_result and ai_result.get('skills'):
                return ai_result

        # Resilient rule-based extraction
        return self._extract_with_rules(resume_text)

    def _extract_with_llm(self, resume_text):
        system_prompt = (
            "You are an expert ATS and resume skill extraction engine. "
            "Analyze the candidate's resume and return a STRICT JSON object with these keys:\n"
            "1. 'skills': list of objects [{'name': str, 'level': 1-5, 'evidence': str}]\n"
            "2. 'education': list of objects [{'degree': str, 'institution': str, 'year': str}]\n"
            "3. 'projects': list of objects [{'title': str, 'description': str, 'technologies': [str]}]\n"
            "4. 'experience': list of objects [{'role': str, 'company': str, 'duration': str, 'highlights': [str]}]\n"
            "5. 'ats_score': float from 0 to 100\n"
            "6. 'ats_feedback': list of strings with actionable suggestions\n"
            "Only return valid JSON without markdown fences."
        )
        prompt = f"Resume Content:\n\n{resume_text[:4000]}"
        raw_output = self.ai_client.call_llm(prompt, system_prompt)
        parsed = self.ai_client.parse_json_safely(raw_output)

        if isinstance(parsed, dict) and 'skills' in parsed:
            # Normalize skills using canonical taxonomy
            raw_skills = parsed.get('skills', [])
            normalized_skills = self.normalizer.normalize_extracted_skills(raw_skills)
            parsed['skills'] = normalized_skills
            return parsed

        return None

    def _extract_with_rules(self, text):
        """
        Deterministic, rule-based extraction engine with regex and keyword patterns.
        """
        extracted_skills_dict = {}
        text_lower = text.lower()

        # 1. Skill keyword matching against taxonomy
        items = self.skills_taxonomy.values() if isinstance(self.skills_taxonomy, dict) else self.skills_taxonomy
        for skill in items:
            sid = skill.id if hasattr(skill, 'id') else skill.get('id')
            sname = skill.name if hasattr(skill, 'name') else skill.get('name')
            synonyms = skill.synonyms if hasattr(skill, 'synonyms') else skill.get('synonyms', [])

            keywords = [sname, sid] + list(synonyms)
            for kw in keywords:
                if not kw or len(kw.strip()) < 2:
                    continue
                # Word boundary search
                escaped_kw = re.escape(kw.strip())
                pattern = r'(?:\b|(?<=[^a-zA-Z0-9]))' + escaped_kw + r'(?:\b|(?=[^a-zA-Z0-9]))'
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Find sentence or line as evidence
                    start = max(0, match.start() - 60)
                    end = min(len(text), match.end() + 60)
                    evidence = text[start:end].replace('\n', ' ').strip()
                    
                    # Estimate level from evidence context
                    level = self._estimate_level(evidence)
                    
                    if sid not in extracted_skills_dict or level > extracted_skills_dict[sid]['level']:
                        extracted_skills_dict[sid] = {
                            'skill_id': sid,
                            'skill_name': sname,
                            'raw_name': kw,
                            'level': level,
                            'evidence': f"...{evidence}..."
                        }
                    break

        # 2. Extract Contact Info
        emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)
        phones = re.findall(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        linkedin = re.findall(r'linkedin\.com/in/[\w\-]+', text, re.IGNORECASE)
        github = re.findall(r'github\.com/[\w\-]+', text, re.IGNORECASE)

        contact = {
            'email': emails[0] if emails else None,
            'phone': phones[0] if phones else None,
            'linkedin': linkedin[0] if linkedin else None,
            'github': github[0] if github else None
        }

        # 3. Extract Education
        education = []
        edu_keywords = ['bachelor', 'master', 'b.tech', 'b.e.', 'm.tech', 'ph.d', 'degree', 'bs', 'ms', 'computer science']
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_l = line.lower()
            if any(k in line_l for k in edu_keywords):
                context = " ".join(lines[max(0, i-1):min(len(lines), i+2)]).strip()
                if len(context) > 10 and not any(e['institution'] in context for e in education if e.get('institution')):
                    education.append({
                        'degree': line.strip(),
                        'institution': 'Academic Institution / University',
                        'year': self._extract_year(context)
                    })
                if len(education) >= 2:
                    break

        # 4. Extract Projects
        projects = []
        proj_headings = ['projects', 'academic projects', 'personal projects', 'key projects']
        for i, line in enumerate(lines):
            if any(h == line.strip().lower() for h in proj_headings):
                # Grab next few lines
                for j in range(i+1, min(len(lines), i+8)):
                    sub = lines[j].strip()
                    if len(sub) > 15 and not sub.lower().startswith('skills'):
                        projects.append({
                            'title': sub[:50],
                            'description': sub,
                            'technologies': []
                        })
                    if len(projects) >= 3:
                        break
                break

        # 5. ATS Score & Feedback
        ats_score, ats_feedback = self._calculate_ats_score(text, contact, extracted_skills_dict, education, projects)

        return {
            'skills': list(extracted_skills_dict.values()),
            'contact': contact,
            'education': education,
            'projects': projects,
            'experience': [],
            'ats_score': ats_score,
            'ats_feedback': ats_feedback
        }

    @staticmethod
    def _estimate_level(evidence_text):
        e = evidence_text.lower()
        if any(w in e for w in ['architect', 'expert', 'lead', 'staff', 'principal', '5+ years', '6 years', '7 years']):
            return 5
        if any(w in e for w in ['senior', 'advanced', 'proficient', '3 years', '4 years', 'production', 'optimized']):
            return 4
        if any(w in e for w in ['developed', 'built', 'created', 'designed', 'implemented', 'worked with', '2 years']):
            return 3
        if any(w in e for w in ['familiar', 'used', 'knowledge', 'basic', 'junior', '1 year', 'assisted']):
            return 2
        return 3

    @staticmethod
    def _extract_year(text):
        match = re.search(r'\b(20[0-2][0-9]|199[0-9])\b', text)
        return match.group(0) if match else "2024"

    @staticmethod
    def _calculate_ats_score(text, contact, skills, education, projects):
        score = 0.0
        feedback = []

        # Contact check (20 pts)
        if contact.get('email'):
            score += 10
        else:
            feedback.append("Missing explicit email address in contact header.")

        if contact.get('phone') or contact.get('github') or contact.get('linkedin'):
            score += 10
        else:
            feedback.append("Include links to your GitHub or LinkedIn profile for recruiter trust.")

        # Skills count (35 pts)
        skill_count = len(skills)
        if skill_count >= 10:
            score += 35
        elif skill_count >= 5:
            score += 25
            feedback.append("Add more specific technical tools, libraries, and frameworks.")
        else:
            score += 15
            feedback.append("Resume contains relatively few recognizable technical keywords.")

        # Education (15 pts)
        if education:
            score += 15
        else:
            score += 5
            feedback.append("Ensure degree and academic background are clearly demarcated.")

        # Projects / Action Verbs (30 pts)
        action_verbs = ['developed', 'built', 'designed', 'implemented', 'optimized', 'managed', 'created', 'engineered']
        has_verbs = any(v in text.lower() for v in action_verbs)
        if has_verbs:
            score += 20
        else:
            feedback.append("Use strong action verbs (e.g. Architected, Optimized, Implemented).")

        # Metrics / Quantifiable results
        has_metrics = bool(re.search(r'\b\d+%\b|\b\$\d+|\b\d+x\b|\b\d+\s*(users|clients|ms|seconds)', text, re.IGNORECASE))
        if has_metrics:
            score += 10
        else:
            feedback.append("Add quantifiable metrics to project outcomes (e.g. 'improved latency by 30%').")

        if not feedback:
            feedback.append("Strong resume structure with clear keyword density and quantifiable achievements.")

        return round(score, 1), feedback

    def _empty_result(self):
        return {
            'skills': [],
            'contact': {},
            'education': [],
            'projects': [],
            'experience': [],
            'ats_score': 0.0,
            'ats_feedback': ["No resume text provided."]
        }
