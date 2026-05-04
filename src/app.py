import os
from datetime import date

import db
from flask import Flask, render_template
from routes.auth import auth_bp, oauth
from routes.submit import submit_bp

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

oauth.init_app(app)
app.register_blueprint(auth_bp)
app.register_blueprint(submit_bp)

model = db.get_model()


@app.context_processor
def inject_today_challenge():
    from flask import request
    try:
        today = request.cookies.get("local_date") or date.today().isoformat()
        challenge = model.get_or_create_challenge(today)
        return {"today_challenge": challenge}
    except Exception:
        return {"today_challenge": None}


@app.template_filter("format_date")
def format_date(iso_str: str, fmt: str = "%B %d, %Y") -> str:
    try:
        return date.fromisoformat(iso_str).strftime(fmt) if iso_str else ""
    except (ValueError, AttributeError):
        return ""


@app.template_filter("text_color")
def text_color(hex_color: str) -> str:
    """Return #000 or #fff depending on which is more readable on the given background."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    def linearize(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    luminance = 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)
    return "#000000" if luminance > 0.179 else "#ffffff"


@app.route("/")
def index():
    from flask import request, session
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
    from flask import redirect, session, url_for
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    posts = model.get_user_posts(session["user_id"])
    return render_template("profile.html", posts=posts)


@app.route("/user/<username>")
def user_profile(username):
    from flask import abort, redirect, session, url_for
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
    from flask import abort, redirect, session, url_for
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    post = model.get_post(session["user_id"], post_id)
    if not post:
        abort(404)
    return render_template("post_detail.html", post=post)



@app.route("/archive")
def archive():
    from flask import redirect, session, url_for
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    days = model.get_past_challenges()
    return render_template("archive.html", days=days)


@app.route("/archive/<date_str>")
def archive_day(date_str):
    from datetime import date
    from flask import abort, redirect, session, url_for
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
    return render_template("about.html")


@app.route("/health")
def health():
    try:
        model.db.collection("challenges").limit(1).get()
        db_status = "ok"
    except Exception as e:
        db_status = str(e)
    return {"status": "ok", "db": db_status}, 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, host="0.0.0.0", port=port)
