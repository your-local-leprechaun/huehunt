import os
from datetime import date

from challenges import luminance
from db import instance as model
from flask import Flask, abort, redirect, render_template, request, session, url_for
from routes.auth import auth_bp, oauth
from routes.submit import submit_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

oauth.init_app(app)
app.register_blueprint(auth_bp)
app.register_blueprint(submit_bp)

@app.context_processor
def inject_today_challenge():
    """
    Inject today's challenge into every template context automatically.

    Reads the date from the user's local_date cookie (set by the client to
    avoid timezone issues), falling back to the server's UTC date. Returns
    an empty dict on failure so pages still render if Firestore is unavailable.

    :returns: Dict with "today_challenge" key containing the challenge document,
        or {"today_challenge": None} on error.
    """
    try:
        today = request.cookies.get("local_date") or date.today().isoformat()
        challenge = model.get_or_create_challenge(today)
        return {"today_challenge": challenge}
    except Exception:
        return {"today_challenge": None}


@app.template_filter("format_date")
def format_date(iso_str: str, fmt: str = "%B %d, %Y") -> str:
    """
    Jinja2 filter to format an ISO date string for display (e.g. "May 03, 2026").

    :param iso_str: ISO date string to format (e.g. "2026-05-03").
    :param fmt: strftime format string. Defaults to "%B %d, %Y".
    :returns: Formatted date string, or an empty string if input is invalid.
    """
    try:
        return date.fromisoformat(iso_str).strftime(fmt) if iso_str else ""
    except (ValueError, AttributeError):
        return ""


@app.template_filter("text_color")
def text_color(hex_color: str) -> str:
    """
    Jinja2 filter that returns black or white depending on which is more readable
    against the given background color, using the WCAG relative luminance formula.

    :param hex_color: Hex color string with or without leading "#" (e.g. "#a3f0c2").
    :returns: "#000000" for light backgrounds, "#ffffff" for dark backgrounds.
    """
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return "#000000" if luminance(r, g, b) > 0.179 else "#ffffff"


@app.route("/")
def index():
    """
    Home page — shows the daily challenge or the gallery if the user has already submitted.

    :returns: Rendered gallery.html if the user submitted today, otherwise index.html.
    """
    today = request.cookies.get("local_date") or date.today().isoformat()
    challenge = model.get_or_create_challenge(today)
    user = model.get_user(session["user_id"]) if session.get("user_id") else None
    submitted = user and user.get("last_submitted_date") == today
    if submitted:
        submissions = model.get_recent_submissions()
        return render_template("gallery.html", today=today, challenge=challenge, submissions=submissions)
    return render_template("index.html", today=today, challenge=challenge)


@app.route("/profile")
def profile():
    """
    Current user's profile page showing their submission history.

    Redirects to login if the user is not authenticated.

    :returns: Rendered profile.html with the user's posts.
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    posts = model.get_user_posts(session["user_id"])
    return render_template("profile.html", posts=posts)


@app.route("/user/<username>")
def user_profile(username):
    """
    Public profile page for any user by username.

    Redirects to login if unauthenticated, or to /profile if the username
    matches the logged-in user.

    :param username: The username from the URL path.
    :returns: Rendered user_profile.html with that user's posts, or 404 if not found.
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    if session.get("username") == username:
        return redirect(url_for("profile"))
    result = model.get_user_by_username(username)
    if not result:
        abort(404)
    user_id, user_data = result
    posts = model.get_user_posts(user_id)
    return render_template("user_profile.html", profile_user=user_data, posts=posts)


@app.route("/profile/post/<post_id>")
def post_detail(post_id):
    """
    Detail view for a single post belonging to the logged-in user.

    :param post_id: The Firestore document ID of the post.
    :returns: Rendered post_detail.html, or 404 if the post doesn't exist.
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    post = model.get_post(session["user_id"], post_id)
    if not post:
        abort(404)
    return render_template("post_detail.html", post=post)


@app.route("/archive")
def archive():
    """
    Archive index listing all past challenge dates.

    :returns: Rendered archive.html with a list of past challenges sorted newest first.
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    days = model.get_past_challenges()
    return render_template("archive.html", days=days)


@app.route("/archive/<date_str>")
def archive_day(date_str):
    """
    Gallery of submissions for a specific past challenge date.

    Returns 404 if the date string is invalid or the date is today or in the future.

    :param date_str: ISO date string from the URL path (e.g. "2026-05-03").
    :returns: Rendered archive_day.html with the challenge and its submissions.
    """
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        abort(404)
    if d >= date.today():
        abort(404)
    challenge = model.get_or_create_challenge(date_str)
    submissions = model.get_submissions_for_date(date_str)
    return render_template("archive_day.html", archive_date=date_str, challenge=challenge, submissions=submissions)


@app.route("/about")
def about():
    """
    Static about page.

    :returns: Rendered about.html.
    """
    return render_template("about.html")


@app.route("/health")
def health():
    """
    Health check endpoint used by Cloud Run to verify the service is running.

    Attempts a lightweight Firestore read to confirm database connectivity.

    :returns: JSON dict with "status" and "db" fields, always HTTP 200.
    """
    try:
        model.db.collection("challenges").limit(1).get()
        db_status = "ok"
    except Exception as e:
        db_status = str(e)
    return {"status": "ok", "db": db_status}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
