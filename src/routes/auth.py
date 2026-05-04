import json
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

from authlib.integrations.flask_client import OAuth
from db import instance as model
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)
oauth = OAuth()


def _validated_streak(user_data: dict) -> int:
    """
    Return the user's current streak, or 0 if they missed a day.

    A streak is still valid if the user submitted today or yesterday. Anything
    older is treated as broken and resets to 0.

    :param user_data: The user's Firestore document as a dict.
    :returns: The user's streak count, or 0 if it has lapsed.
    """
    last = user_data.get("last_submitted_date")
    if not last:
        return 0
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if last >= yesterday:
        return user_data.get("streak", 0)
    return 0


# Load OAuth credentials from env vars, falling back to oauth-creds.json for local dev
_client_id = os.environ.get("GOOGLE_CLIENT_ID")
_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

if not (_client_id and _client_secret):
    _creds_path = Path(__file__).parent.parent.parent / "oauth-creds.json"
    _raw = json.loads(_creds_path.read_text())
    _creds = _raw.get("web", _raw)
    _client_id = _creds["client_id"]
    _client_secret = _creds["client_secret"]

google = oauth.register(
    name="google",
    client_id=_client_id,
    client_secret=_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@auth_bp.route("/login")
def login():
    """
    Render the login page, or redirect home if already signed in.

    :returns: Rendered login.html, or redirect to index.
    """
    if session.get("user_id"):
        return redirect(url_for("index"))
    return render_template("login.html")


# ── Email auth ───────────────────────────────────────────────

@auth_bp.route("/auth/signin", methods=["POST"])
def email_signin():
    """
    Handle email/password sign-in.

    Looks up the user by email, verifies the password hash, and populates
    the session. Redirects back to login with an error flash on failure.

    :returns: Redirect to index on success, or back to login on failure.
    """
    email = request.form["email"].strip().lower()
    password = request.form["password"]

    result = model.get_user_by_email(email)
    if not result:
        flash("No account found with that email.", "error")
        return redirect(url_for("auth.login"))

    user_id, user_data = result
    stored_hash = user_data.get("password")
    if not stored_hash or not check_password_hash(stored_hash, password):
        flash("Incorrect password.", "error")
        return redirect(url_for("auth.login"))

    session["user_id"] = user_id
    session["username"] = user_data.get("username")
    session["streak"] = _validated_streak(user_data)
    return redirect(url_for("index"))


@auth_bp.route("/auth/signup", methods=["POST"])
def email_signup():
    """
    Handle new account creation via email/password.

    Checks for an existing account with the same email, creates a new user
    document with a hashed password, and redirects to username selection.

    :returns: Redirect to choose_username on success, or back to login on failure.
    """
    email = request.form["email"].strip().lower()
    password = request.form["password"]

    if model.get_user_by_email(email):
        flash("An account with that email already exists.", "error")
        return redirect(url_for("auth.login", tab="signup"))

    user_id = str(uuid.uuid4())
    model.upsert_user(user_id, {
        "username": None,
        "email": email,
        "password": generate_password_hash(password),
        "streak": 0,
        "last_submitted_date": None,
    })

    session["user_id"] = user_id
    session["username"] = None
    session["streak"] = 0
    return redirect(url_for("auth.choose_username"))


# ── Username selection ───────────────────────────────────────

@auth_bp.route("/choose-username")
def choose_username():
    """
    Render the username selection page for newly registered users.

    Skipped if the user already has a username (e.g. returning after OAuth).

    :returns: Rendered choose_username.html, or redirect to index/login.
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    if session.get("username"):
        return redirect(url_for("index"))
    return render_template("choose_username.html")


@auth_bp.route("/auth/set-username", methods=["POST"])
def set_username():
    """
    Save the chosen username to Firestore and update the session.

    :returns: Redirect to index on success, or back to choose_username on failure.
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    username = request.form["username"].strip()
    if not username:
        flash("Username cannot be empty.", "error")
        return redirect(url_for("auth.choose_username"))

    model.upsert_user(session["user_id"], {"username": username})
    session["username"] = username
    return redirect(url_for("index"))


# ── Google OAuth ─────────────────────────────────────────────

@auth_bp.route("/auth/google")
def google_login():
    """
    Kick off the Google OAuth flow by redirecting to Google's auth page.

    :returns: Redirect to Google's OAuth consent screen.
    """
    redirect_uri = url_for("auth.google_callback", _external=True)
    return google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/google/callback")
def google_callback():
    """
    Handle the Google OAuth callback after the user approves access.

    Creates a new user document on first sign-in and redirects to username
    selection. Returns existing users directly to the home page.

    :returns: Redirect to choose_username for new users, or index for existing ones.
    """
    token = google.authorize_access_token()
    info = token.get("userinfo")

    user_id = info["sub"]  # Google's stable unique ID for the user
    email = info["email"]

    existing = model.get_user(user_id)

    if not existing:
        model.upsert_user(user_id, {
            "username": None,
            "email": email,
            "password": None,  # no password for OAuth users
            "streak": 0,
            "last_submitted_date": None,
        })
        session["user_id"] = user_id
        session["username"] = None
        session["streak"] = 0
        return redirect(url_for("auth.choose_username"))

    session["user_id"] = user_id
    session["username"] = existing.get("username")
    session["streak"] = _validated_streak(existing)
    return redirect(url_for("index"))


@auth_bp.route("/logout")
def logout():
    """
    Clear the session and redirect to the login page.

    :returns: Redirect to login.
    """
    session.clear()
    return redirect(url_for("auth.login"))
