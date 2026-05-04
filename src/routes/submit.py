import base64
import os
import uuid
from datetime import date, datetime, timedelta, timezone

from db import instance as model
from flask import Blueprint, jsonify, make_response, request, session
from google.cloud import storage

submit_bp = Blueprint("submit", __name__)

# Lazily initialized so the storage client isn't created until first use
_storage_client: storage.Client | None = None


def _gcs_bucket():
    """
    Return the GCS bucket, initializing the storage client on first call.

    :returns: A google.cloud.storage.Bucket instance.
    """
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client.bucket(os.environ["GCS_BUCKET"])


def _upload_image(data_url: str, user_id: str) -> str:
    """
    Decode a base64 data URL and upload the image to GCS.

    The blob is stored at posts/<user_id>/<today>/<uuid>.<ext> to keep
    submissions organized by user and date.

    :param data_url: Base64-encoded data URL from the browser canvas (e.g. "data:image/jpeg;base64,...").
    :param user_id: The ID of the submitting user, used to namespace the blob path.
    :returns: The GCS blob name (not a public URL) used to serve the image via /image/<blob_name>.
    """
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
    """
    Accept a photo submission for today's challenge.

    Expects a JSON body with "image" (base64 data URL), "alt_text" (optional),
    and "local_date" (ISO date string from the client to handle timezones).
    Uploads the image to GCS, creates a post document, and updates the user's streak.

    :returns: JSON with "post_id" and "image_url" on success, or an error dict on failure.
    """
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

    # Prefer the client-supplied date to avoid UTC vs. local timezone mismatches
    today = data.get("local_date") or request.cookies.get("local_date") or date.today().isoformat()
    challenge = model.get_or_create_challenge(today)
    post_id = model.create_post(user_id, {
        "date": datetime.now(timezone.utc),
        "challenge_date": today,
        "image_url": image_url,
        "alt_text": alt_text,
        "challenge": challenge.get("color_hex"),
        "username": session.get("username"),
        "user_id": user_id,
    })

    new_streak = model.update_streak(user_id, today)
    session["streak"] = new_streak

    return jsonify({"post_id": post_id, "image_url": image_url}), 200


@submit_bp.route("/post/<post_id>", methods=["DELETE"])
def delete_post(post_id):
    """
    Delete a post and its associated GCS image.

    If the deleted post was from today, the user's streak is rolled back by 1
    and last_submitted_date is set to yesterday so they can resubmit.

    :param post_id: The Firestore document ID of the post to delete.
    :returns: JSON {"ok": True} on success, or an error dict on failure.
    """
    if not session.get("user_id"):
        return jsonify({"error": "Not logged in"}), 401

    user_id = session["user_id"]

    post = model.get_post(user_id, post_id)
    if not post:
        return jsonify({"error": "Post not found"}), 404

    # Delete from GCS — image_url is stored as /image/<blob_name>
    blob_name = post["image_url"].removeprefix("/image/")
    try:
        _gcs_bucket().blob(blob_name).delete()
    except Exception:
        pass  # Don't block deletion if the GCS file is already gone

    model.delete_post(user_id, post_id)

    # Roll back streak if the deleted post counted for today
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
    """
    Serve a GCS image via the service account, keeping the bucket private.

    Images are cached on the client for 24 hours. The immutable directive tells
    the browser the content at this URL will never change (each upload gets a unique UUID path).

    :param blob_name: GCS blob path (e.g. "posts/<user_id>/<date>/<uuid>.jpg").
    :returns: The raw image bytes with appropriate Content-Type, or 404 if not found.
    """
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
