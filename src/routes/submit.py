import base64
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, make_response, redirect, request, session
from google.cloud import storage

submit_bp = Blueprint("submit", __name__)

_storage_client: storage.Client | None = None


def _gcs_bucket():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client.bucket(os.environ["GCS_BUCKET"])


def _upload_image(data_url: str, user_id: str) -> str:
    """Upload to GCS, return blob path (not a public URL)."""
    header, encoded = data_url.split(",", 1)
    image_bytes = base64.b64decode(encoded)
    ext = "jpg" if "jpeg" in header else "png"

    today = date.today().isoformat()
    blob_name = f"posts/{user_id}/{today}/{uuid.uuid4()}.{ext}"

    blob = _gcs_bucket().blob(blob_name)
    blob.upload_from_string(image_bytes, content_type=f"image/{ext}")

    return blob_name


@submit_bp.route("/submit", methods=["POST"])
def submit():
    if not session.get("user_id"):
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json()
    image_data = data.get("image")
    alt_text = data.get("alt_text", "").strip()

    if not image_data:
        return jsonify({"error": "No image provided"}), 400

    user_id = session["user_id"]

    try:
        blob_name = _upload_image(image_data, user_id)
    except Exception as e:
        return jsonify({"error": f"Upload failed: {e}"}), 500

    image_url = f"/image/{blob_name}"

    today = data.get("local_date") or request.cookies.get("local_date") or date.today().isoformat()
    from app import model
    challenge = model.get_or_create_challenge(today)
    post_id = model.create_post(user_id, {
        "date": datetime.now(timezone.utc),
        "challenge_date": today,
        "image_url": image_url,
        "alt_text": alt_text,
        "challenge": challenge.get("color_hex"),
        "username": session.get("username"),
        "user_id": user_id,
        "colorblind": session.get("colorblind", False),
    })

    new_streak = model.update_streak(user_id, today)
    session["streak"] = new_streak

    return jsonify({"post_id": post_id, "image_url": image_url}), 200



@submit_bp.route("/post/<post_id>", methods=["DELETE"])
def delete_post(post_id):
    if not session.get("user_id"):
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user_id"]
    from app import model

    post = model.get_post(user_id, post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404

    # Delete from GCS — image_url is stored as /image/<blob_name>
    blob_name = post["image_url"].removeprefix("/image/")
    try:
        _gcs_bucket().blob(blob_name).delete()
    except Exception:
        pass  # Don't block deletion if GCS file is already gone

    model.delete_post(user_id, post_id)

    today = request.cookies.get("local_date") or date.today().isoformat()
    if post.get("challenge_date") == today:
        user = model.get_user(user_id) or {}
        new_streak = max(0, user.get("streak", 1) - 1)
        yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
        model.upsert_user(user_id, {"last_submitted_date": yesterday, "streak": new_streak})
        session["streak"] = new_streak

    return jsonify({"ok": True}), 200


@submit_bp.route("/image/<path:blob_name>")
def serve_image(blob_name):
    """Serve a GCS image using the service account — bucket stays private."""
    try:
        blob = _gcs_bucket().blob(blob_name)
        data = blob.download_as_bytes()
        content_type = blob.content_type or "image/jpeg"
    except Exception:
        return "", 404

    resp = make_response(data)
    resp.headers["Content-Type"] = content_type
    resp.headers["Cache-Control"] = "private, max-age=86400, immutable"
    return resp
