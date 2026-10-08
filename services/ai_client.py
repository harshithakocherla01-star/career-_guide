import os
import json
import logging
import requests
from flask import current_app, has_app_context

logger = logging.getLogger(__name__)

class AIClient:
    def __init__(self, anthropic_model='claude-3-haiku-20240307', gemini_model='gemini-1.5-flash', timeout=15):
        if has_app_context():
            self.anthropic_key = str(current_app.config.get('ANTHROPIC_API_KEY') or '').strip()
            self.gemini_key = str(current_app.config.get('GEMINI_API_KEY') or '').strip()
        else:
            self.anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '').strip()
            self.gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
        self.anthropic_model = anthropic_model
        self.gemini_model = gemini_model
        self.timeout = timeout

    def is_available(self):
        return bool(self.anthropic_key or self.gemini_key)

    def _call_claude(self, prompt, system_prompt=None):
        if not self.anthropic_key:
            return None
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.anthropic_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.anthropic_model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data['content'][0]['text']
            logger.warning("Anthropic API request failed (HTTP %s)", resp.status_code)
        except Exception as exc:
            logger.warning("Anthropic API request failed (%s)", type(exc).__name__)
        return None

    def _call_gemini(self, prompt, system_prompt=None):
        if not self.gemini_key:
            return None
        client = None
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=self.gemini_key,
                http_options=types.HttpOptions(timeout=self.timeout * 1000)
            )
            config = types.GenerateContentConfig(system_instruction=system_prompt) if system_prompt else None
            response = client.models.generate_content(
                model=self.gemini_model,
                contents=prompt,
                config=config
            )
            return response.text
        except ImportError:
            logger.error("Gemini provider is configured but google-genai is not installed; install project requirements")
        except Exception as exc:
            status_code = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
            logger.warning("Gemini API request failed (exception=%s, status=%s)", type(exc).__name__, status_code or 'unknown')
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    logger.debug("Gemini SDK client cleanup failed")
        return None

    def call_llm(self, prompt, system_prompt=None):
        """
        Tries Claude first, then Gemini if configured.
        """
        if self.anthropic_key:
            res = self._call_claude(prompt, system_prompt)
            if res:
                return res
        if self.gemini_key:
            res = self._call_gemini(prompt, system_prompt)
            if res:
                return res
        return None

    def parse_json_safely(self, text):
        if not text:
            return None
        text = text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except Exception:
            # Try to find JSON within { } or [ ]
            start_brace = text.find("{")
            end_brace = text.rfind("}")
            if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                try:
                    return json.loads(text[start_brace:end_brace+1])
                except Exception:
                    pass
            start_bracket = text.find("[")
            end_bracket = text.rfind("]")
            if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
                try:
                    return json.loads(text[start_bracket:end_bracket+1])
                except Exception:
                    pass
        return None
