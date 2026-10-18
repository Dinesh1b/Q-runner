"""
pages.py — SPA page-serving routes.

Serves the Angular SPA index.html for all navigation routes that are not
API routes or file assets.  Direct navigation and browser refresh work
correctly because every Angular client-route returns the same index.html.

SECURITY:
  - Backend authorization (SKIP_AUTH / session) is still authoritative.
  - Angular route-guards are a UX convenience only, not a security boundary.
  - Missing static assets return 404 (not the SPA fallback) so broken
    asset references surface during development.
  - API routes registered in other blueprints take precedence; the wildcard
    angular_static route at the bottom is last in Flask's routing table.

ANGULAR ROUTING:
  Angular uses HTML5 push-state routing.  The following paths all load the
  SPA which then shows the appropriate view based on the URL:
    /               -> authGuard -> ShellComponent or redirect to /login
    /login          -> guestGuard -> AuthComponent (login view)
    /signup         -> guestGuard -> AuthComponent (signup view)
    /verify         -> guestGuard -> AuthComponent (OTP verify view)
    /set-password   -> guestGuard -> AuthComponent (set-password view)
    /forgot-password-> guestGuard -> AuthComponent (forgot view)
    /reset-password -> guestGuard -> AuthComponent (reset view)
    /auth           -> guestGuard -> AuthComponent (default auth view)

BROWSER PREVIEW:
  /browser_status and /video_feed are NOT implemented in the backend.
  The browser.html template was a legacy-only feature.  Documented here
  as unavailable until backend implementation is added.
"""

import os

from flask import Blueprint, current_app, send_from_directory, abort


pages_bp = Blueprint("pages", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _angular_dist():
    """Return the verified Angular dist/browser directory path, or empty string."""
    return current_app.config.get("ANGULAR_DIST", "")


def _serve_angular_index():
    """Send the Angular SPA index.html."""
    dist = _angular_dist()
    if dist and os.path.isfile(os.path.join(dist, "index.html")):
        return send_from_directory(dist, "index.html")
    # Angular build has not been run yet.
    abort(503, description="Angular build not found. Run 'npm run build' in frontend-angular/.")


# ---------------------------------------------------------------------------
# SPA navigation routes
# Each route serves index.html; Angular's client-side router handles the view.
# ---------------------------------------------------------------------------

@pages_bp.route("/")
def index():
    return _serve_angular_index()


@pages_bp.route("/login")
def auth_login_page():
    return _serve_angular_index()


@pages_bp.route("/signup")
def auth_signup_page():
    return _serve_angular_index()


@pages_bp.route("/verify")
def auth_verify_page():
    return _serve_angular_index()


@pages_bp.route("/set-password")
def auth_setpw_page():
    return _serve_angular_index()


@pages_bp.route("/forgot-password")
def auth_forgot_page():
    return _serve_angular_index()


@pages_bp.route("/reset-password")
def auth_reset_page():
    return _serve_angular_index()


@pages_bp.route("/auth")
@pages_bp.route("/auth/<path:subpath>")
def auth_page(subpath=""):
    return _serve_angular_index()


# ---------------------------------------------------------------------------
# Static asset catch-all
#
# Flask's static_folder=_ANGULAR_DIST + static_url_path="/" already serves
# hashed bundles automatically, but this explicit route provides the
# correct 404-vs-index.html behaviour:
#   - path with a file extension AND file is present  -> serve the file
#   - path with a file extension AND file is missing  -> 404
#   - path WITHOUT a file extension                   -> serve index.html
#     (deep Angular route like /some/nested/page)
#
# This route is registered last in the pages blueprint so all API routes
# registered in other blueprints (auth, runner, uploads) take precedence.
# ---------------------------------------------------------------------------

@pages_bp.route("/<path:filename>")
def angular_static(filename):
    """
    Serve Angular hashed assets (JS, CSS, fonts, images, favicon) or
    fall back to index.html for deep SPA routes.
    """
    dist = _angular_dist()
    if not dist:
        abort(404)

    full_path = os.path.join(dist, filename)

    # Exact file exists in the dist directory -> serve it directly.
    if os.path.isfile(full_path):
        return send_from_directory(dist, filename)

    # Has a file extension but the file is missing -> genuine 404.
    _, ext = os.path.splitext(filename)
    if ext:
        abort(404)

    # No extension -> treat as an Angular client-side route -> serve index.html.
    return _serve_angular_index()
