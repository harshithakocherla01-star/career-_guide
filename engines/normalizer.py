import re

class SkillNormalizer:
    def __init__(self, skills_taxonomy=None):
        """
        skills_taxonomy: dict of {skill_id: {'name': str, 'synonyms': [str, ...], ...}}
        or list of Skill objects / dicts.
        """
        self.canonical_map = {}
        self.synonym_map = {}
        if skills_taxonomy:
            self.load_taxonomy(skills_taxonomy)

    def load_taxonomy(self, skills_taxonomy):
        self.canonical_map = {}
        self.synonym_map = {}
        
        # Accept either dict or list of skills
        items = skills_taxonomy.values() if isinstance(skills_taxonomy, dict) else skills_taxonomy
        for skill in items:
            sid = skill.id if hasattr(skill, 'id') else skill.get('id')
            sname = skill.name if hasattr(skill, 'name') else skill.get('name')
            synonyms = skill.synonyms if hasattr(skill, 'synonyms') else skill.get('synonyms', [])
            
            canonical_key = self._clean_token(sid)
            self.canonical_map[canonical_key] = sid
            self.synonym_map[self._clean_token(sname)] = sid
            
            for syn in synonyms:
                self.synonym_map[self._clean_token(syn)] = sid

    @staticmethod
    def _clean_token(text):
        if not text:
            return ""
        # Lowercase and strip special characters, leaving alphanumerics
        # Keep '+' for C++ etc.
        text = str(text).strip().lower()
        text = text.replace('.js', 'js').replace('.net', 'net')
        text = re.sub(r'[\s\-_\./]+', '', text)
        return text

    def normalize(self, raw_name):
        """
        Normalizes any skill name/variant to its canonical skill_id.
        Returns canonical skill_id or None if not recognized.
        """
        if not raw_name:
            return None
        
        token = self._clean_token(raw_name)
        if token in self.canonical_map:
            return self.canonical_map[token]
        if token in self.synonym_map:
            return self.synonym_map[token]
        
        # Substring / fuzzy check for common suffixes
        for syn_token, sid in self.synonym_map.items():
            if syn_token == token or syn_token in token or token in syn_token:
                # If exact word match length is close
                if len(token) >= 3 and abs(len(token) - len(syn_token)) <= 2:
                    return sid
        
        return None

    def normalize_extracted_skills(self, extracted_skills):
        """
        Takes list of extracted skills (either strings or dicts with name, level, evidence)
        and normalizes them to canonical skill records.
        """
        normalized_results = {}
        for item in extracted_skills:
            if isinstance(item, str):
                raw_name = item
                level = 3
                evidence = ""
            elif isinstance(item, dict):
                raw_name = item.get('name') or item.get('skill')
                level = item.get('level', 3)
                evidence = item.get('evidence', '')
            else:
                continue

            canonical_id = self.normalize(raw_name)
            if canonical_id:
                # If duplicate, keep highest level
                if canonical_id in normalized_results:
                    if level > normalized_results[canonical_id]['level']:
                        normalized_results[canonical_id]['level'] = level
                        if evidence:
                            normalized_results[canonical_id]['evidence'] = evidence
                else:
                    normalized_results[canonical_id] = {
                        'skill_id': canonical_id,
                        'raw_name': raw_name,
                        'level': max(1, min(5, int(level))),
                        'evidence': evidence
                    }
        return list(normalized_results.values())
