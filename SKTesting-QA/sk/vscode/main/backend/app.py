"""
app.py — Q-Audit Runner Flask Application Factory.

Creates and configures the Flask app with all blueprints registered.
Serves the Angular production SPA from frontend-angular/dist/frontend-angular/browser/.
"""

import os
import secrets

from flask import Flask
from flask_cors import CORS


def create_app():
    """Create and configure the Flask application."""
    _HERE = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

    # Angular production build output (browser bundle)
    _ANGULAR_DIST = os.path.join(
        _PROJECT_ROOT,
        "frontend-angular", "dist", "frontend-angular", "browser"
    )

    # Determine template folder (index.html lives in the Angular dist/browser dir).
    # We do NOT set static_folder on the Flask app itself; instead the pages blueprint
    # uses send_from_directory() for all asset serving.  This prevents Flask's built-in
    # /<path:filename> static endpoint from conflicting with our SPA fallback logic.
    if os.path.isdir(_ANGULAR_DIST):
        _template_folder = _ANGULAR_DIST
    else:
        # Angular build not present – fall back so server can still start.
        _template_folder = os.path.join(_PROJECT_ROOT, "frontend", "templates")

    app = Flask(
        __name__,
        template_folder=_template_folder,
        static_folder=None,   # asset serving handled by pages blueprint
    )
    CORS(app)
    app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
    # SKIP_AUTH=True is a development convenience only.
    # Set SKIP_AUTH=False (or remove this line) in production environments.
    app.config["SKIP_AUTH"] = os.environ.get("SKIP_AUTH", "true").lower() in ("1", "true", "yes")

    # Store Angular dist path so blueprints can reference it
    app.config["ANGULAR_DIST"] = _ANGULAR_DIST

    # Initialize databases
    from backend.services.db import init_db, init_auth_db
    init_db()
    init_auth_db()

    # Register blueprints
    from backend.blueprints.pages import pages_bp
    from backend.blueprints.auth import auth_bp
    from backend.blueprints.runner import runner_bp
    from backend.blueprints.uploads import uploads_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(runner_bp)
    app.register_blueprint(uploads_bp)

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    # Add parent directory to sys.path so 'backend' is findable
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _root not in sys.path:
        sys.path.insert(0, _root)

    app = create_app()
    print("\n  Q-Audit Runner  (v10 - Pro Scalable + Angular)")
    print("  " + "-" * 57)
    print("  Open in browser ->  http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(
        debug=False,
        use_reloader=False,
        host="0.0.0.0",
        port=int(os.environ.get("FLASK_PORT", 5000)),
        threaded=True,
    )
