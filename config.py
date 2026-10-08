import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Load project-local server secrets before Config snapshots os.environ.
# Existing process environment variables take precedence over .env values.
load_dotenv(os.path.join(BASE_DIR, '.env'), override=False)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'tech-tide-career-platform-secret-key-2026-production-ready')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'tech-tide-jwt-secret-key-2026-secure-token-generation-key')
    
    # SQLite Database
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', 
        f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'career_platform.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload folder
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
    
    # AI API Keys (Optional - offline rule-based fallback works automatically)
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
    INTERVIEW_ANTHROPIC_MODEL = os.environ.get('INTERVIEW_ANTHROPIC_MODEL', 'claude-sonnet-4-6')
    INTERVIEW_GEMINI_MODEL = os.environ.get('INTERVIEW_GEMINI_MODEL', 'gemini-3.8-flash')
