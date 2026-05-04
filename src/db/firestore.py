from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter


class model:
    def __init__(self):
        self.db = firestore.Client(database="huehunt-db")

    def get_or_create_challenge(self, today: str) -> dict:
        """
        Return today's challenge, creating and persisting it if it doesn't exist yet.

        :param today: ISO date string (e.g. "2026-05-03"), used as the Firestore document ID.
        :returns: The challenge document as a dict with keys such as "date", "color", and "hex".
        """
        from challenges import generate_challenge
        from datetime import date

        ref = self.db.collection("challenges").document(today)
        doc = ref.get()
        if doc.exists:
            return doc.to_dict()

        challenge = generate_challenge(date.fromisoformat(today))
        ref.set(challenge)
        return challenge

    def get_past_challenges(self) -> list[dict]:
        """
        Return all challenge documents for dates before today, sorted newest first.

        :returns: List of challenge dicts, each containing at minimum a "date" key.
        """
        from datetime import date
        today = date.today().isoformat()
        docs = self.db.collection("challenges").stream()
        return sorted(
            [doc.to_dict() for doc in docs if doc.id < today],
            key=lambda c: c["date"],
            reverse=True,
        )

    def get_user(self, user_id: str) -> dict | None:
        """
        Return a user's data by their document ID.

        :param user_id: The Firestore document ID for the user.
        :returns: The user data dict, or None if no document exists for that ID.
        """
        doc = self.db.collection("users").document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def get_user_by_username(self, username: str) -> tuple[str, dict] | None:
        """
        Look up a user by their username field.

        :param username: The username to search for (case-sensitive).
        :returns: A (user_id, data) tuple, or None if no matching user exists.
        """
        docs = list(
            self.db.collection("users")
            .where(filter=FieldFilter("username", "==", username))
            .limit(1)
            .stream()
        )
        if docs:
            return docs[0].id, docs[0].to_dict()
        return None

    def get_user_by_email(self, email: str) -> tuple[str, dict] | None:
        """
        Look up a user by their email address.

        :param email: The email address to search for (case-sensitive).
        :returns: A (user_id, data) tuple, or None if no matching user exists.
        """
        docs = list(
            self.db.collection("users")
            .where(filter=FieldFilter("email", "==", email))
            .limit(1)
            .stream()
        )
        if docs:
            return docs[0].id, docs[0].to_dict()
        return None

    def upsert_user(self, user_id: str, data: dict) -> None:
        """
        Create or merge-update a user document.

        :param user_id: The Firestore document ID to write to.
        :param data: Fields to set or update on the user document.
        """
        self.db.collection("users").document(user_id).set(data, merge=True)

    def create_post(self, user_id: str, data: dict) -> str:
        """
        Add a new post to the user's posts subcollection.

        :param user_id: The Firestore document ID of the submitting user.
        :param data: Post fields (e.g. "challenge_date", "date", "blob_name").
        :returns: The auto-generated Firestore document ID of the new post.
        """
        _, ref = (
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .add(data)
        )
        return ref.id

    def delete_post(self, user_id: str, post_id: str) -> None:
        """
        Delete a specific post from the user's posts subcollection.

        :param user_id: The Firestore document ID of the post's owner.
        :param post_id: The Firestore document ID of the post to delete.
        """
        (
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .document(post_id)
            .delete()
        )

    def get_post(self, user_id: str, post_id: str) -> dict | None:
        """
        Fetch a single post by owner and post ID.

        :param user_id: The Firestore document ID of the post's owner.
        :param post_id: The Firestore document ID of the post.
        :returns: The post data dict with an added "id" key, or None if not found.
        """
        doc = (
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .document(post_id)
            .get()
        )
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def get_submissions_for_date(self, date_str: str, limit: int = 50) -> list[dict]:
        """
        Return submissions across all users for a specific challenge date.

        :param date_str: ISO date string of the challenge (e.g. "2026-05-03").
        :param limit: Maximum number of results to return. Defaults to 50.
        :returns: List of post dicts with an added "id" key, sorted newest first.
        """
        docs = (
            self.db.collection_group("posts")
            .where(filter=FieldFilter("challenge_date", "==", date_str))
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]

    def get_recent_submissions(self, limit: int = 50) -> list[dict]:
        """
        Return the most recent submissions across all users.

        :param limit: Maximum number of results to return. Defaults to 50.
        :returns: List of post dicts with an added "id" key, sorted newest first.
        """
        docs = (
            self.db.collection_group("posts")
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]

    def has_submitted_today(self, user_id: str, today: str) -> bool:
        """
        Check whether a user has already submitted for today's challenge.

        Checks the challenge_date field first (present on all posts after that field
        was added), then falls back to a timestamp range query for older posts.

        :param user_id: The Firestore document ID of the user to check.
        :param today: ISO date string for the current day (e.g. "2026-05-03").
        :returns: True if the user has at least one submission for today, False otherwise.
        """
        from datetime import datetime, timezone
        docs = list(
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .where(filter=FieldFilter("challenge_date", "==", today))
            .limit(1)
            .stream()
        )
        if docs:
            return True
        day_start = datetime.fromisoformat(today).replace(tzinfo=timezone.utc)
        day_end = datetime(day_start.year, day_start.month, day_start.day, 23, 59, 59, tzinfo=timezone.utc)
        docs = list(
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .where(filter=FieldFilter("date", ">=", day_start))
            .where(filter=FieldFilter("date", "<=", day_end))
            .limit(1)
            .stream()
        )
        return len(docs) > 0

    def update_streak(self, user_id: str, today: str) -> int:
        """
        Increment the user's streak if they submitted yesterday, or reset it to 1.

        :param user_id: The Firestore document ID of the user.
        :param today: ISO date string for the current day (e.g. "2026-05-03").
        :returns: The updated streak count after this submission.
        """
        from datetime import date, timedelta
        yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
        user = self.get_user(user_id) or {}
        current = user.get("streak", 0)
        last = user.get("last_submitted_date")
        new_streak = current + 1 if last == yesterday else 1
        self.db.collection("users").document(user_id).set(
            {"streak": new_streak, "last_submitted_date": today}, merge=True
        )
        return new_streak

    def get_user_posts(self, user_id: str) -> list[dict]:
        """
        Return all posts for a user, sorted newest first.

        :param user_id: The Firestore document ID of the user.
        :returns: List of post dicts with an added "id" key, sorted by date descending.
        """
        docs = (
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .order_by("date", direction=firestore.Query.DESCENDING)
            .stream()
        )
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
