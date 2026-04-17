import os
from flask import Flask, redirect, url_for
from config import Config
from db import init_db

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    # ── Jinja2 globals ────────────────────────────────────────
    app.jinja_env.globals['enumerate'] = enumerate

    # ── Init BDD automatique ──────────────────────────────────
    with app.app_context():
        try:
            init_db()
        except Exception as e:
            print(f"[WARN] Init BDD échouée : {e}")

    # ── Blueprints ────────────────────────────────────────────
    from routes.auth        import auth_bp
    from routes.main        import main_bp
    from routes.formulaire  import formulaire_bp
    from routes.export      import export_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(formulaire_bp)
    app.register_blueprint(export_bp)

    @app.route('/')
    def index():
        return redirect(url_for('main.dashboard'))

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
