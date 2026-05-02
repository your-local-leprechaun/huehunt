import base64
import os
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, make_response, redirect, request, session
from google.cloud import storage

submit_bp = Blueprint("submit", __name__)


def _gcs_bucket():
    return storage.Client().bucket(os.environ["GCS_BUCKET"])


def _upload_image(data_url: str, user_id: str) -> str:
    """Upload to GCS, return blob path (not a public URL)."""
    header, encoded = data_url.split(",", 1)
    image_bytes = base64.b64decode(encoded)
    ext = "jpg" if "jpeg" in header else "png"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
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

    from app import model
    post_id = model.create_post(user_id, {
        "date": datetime.now(timezone.utc),
        "image_url": image_url,
        "alt_text": alt_text,
        "challenge": None,
    })

    return jsonify({"post_id": post_id, "image_url": image_url}), 200


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
