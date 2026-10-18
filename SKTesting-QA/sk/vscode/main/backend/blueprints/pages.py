"""
pages.py — Page rendering routes.

Serves HTML pages and handles the login-required decorator.
"""

from functools import wraps
from flask import Blueprint, current_app, render_template, redirect, url_for, session

pages_bp = Blueprint("pages", __name__)


def _skip_auth_enabled():
    return bool(current_app.config.get("SKIP_AUTH", False))


def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not _skip_auth_enabled() and not session.get("user_id"):
            return redirect(url_for("pages.auth_login_page"))
        return f(*args, **kwargs)
    return wrapper


@pages_bp.route("/")
@require_login
def index():
    return render_template("index.html")


@pages_bp.route("/login")
def auth_login_page():
    if _skip_auth_enabled():
        return redirect(url_for("pages.index"))
    return render_template("auth.html")


@pages_bp.route("/signup")
def auth_signup_page():
    return render_template("auth.html")


@pages_bp.route("/verify")
def auth_verify_page():
    return render_template("auth.html")


@pages_bp.route("/set-password")
def auth_setpw_page():
    return render_template("auth.html")


@pages_bp.route("/forgot-password")
def auth_forgot_page():
    return render_template("auth.html")


@pages_bp.route("/reset-password")
def auth_reset_page():
    return render_template("auth.html")
