import os
import sys

# Ensure current folder is in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"\n=======================================================")
    print(f"🚀 AI Skill Gap & Career Roadmap Platform is starting...")
    print(f"🌐 Access the application at: http://127.0.0.1:{port}")
    print(f"👤 Candidate Login: alex@techtide.io / alex123")
    print(f"🛡️  Admin Login:     admin@techtide.io / admin123")
    print(f"=======================================================\n")
    app.run(host='127.0.0.1', port=port, debug=True)
