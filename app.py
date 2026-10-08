import os
from flask import Flask, jsonify, render_template
from config import Config
from models import db
from data.seed import seed_database

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'instance'), exist_ok=True)
    db.init_app(app)

    # Register blueprints
    from blueprints.auth import auth_bp
    from blueprints.profile import profile_bp
    from blueprints.resume import resume_bp
    from blueprints.roles import roles_bp
    from blueprints.analysis import analysis_bp
    from blueprints.roadmap import roadmap_bp
    from blueprints.interview import interview_bp
    from blueprints.report import report_bp
    from blueprints.admin import admin_bp
    from blueprints.analytics import analytics_bp
    from blueprints.web import web_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(resume_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(roadmap_bp)
    app.register_blueprint(interview_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(web_bp)

    # Automatically seed if database is uninitialized
    with app.app_context():
        try:
            seed_database(app)
        except Exception as e:
            app.logger.warning(f"Seed check: {e}")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({'error': 'Internal server error'}), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='127.0.0.1', port=5000, debug=True)
