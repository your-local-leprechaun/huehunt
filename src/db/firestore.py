from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter


class model:
    def __init__(self):
        self.db = firestore.Client(database="huehunt-db")

    def get_or_create_challenge(self, today: str) -> dict:
        from challenges import generate_challenge, two_days_ago
        from datetime import date

        ref = self.db.collection("challenges").document(today)
        doc = ref.get()
        if doc.exists:
            return doc.to_dict()

        challenge = generate_challenge(date.fromisoformat(today))
        ref.set(challenge)

        stale = two_days_ago(date.fromisoformat(today))
        self.db.collection("challenges").document(stale).delete()

        return challenge

    def get_user(self, user_id: str) -> dict | None:
        doc = self.db.collection("users").document(user_id).get()
        return doc.to_dict() if doc.exists else None

    def get_user_by_username(self, username: str) -> tuple[str, dict] | None:
        """Returns (user_id, data) or None."""
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
        """Returns (user_id, data) or None."""
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
        self.db.collection("users").document(user_id).set(data, merge=True)

    def create_post(self, user_id: str, data: dict) -> str:
        _, ref = (
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .add(data)
        )
        return ref.id

    def delete_post(self, user_id: str, post_id: str) -> None:
        (
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .document(post_id)
            .delete()
        )

    def get_post(self, user_id: str, post_id: str) -> dict | None:
        doc = (
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .document(post_id)
            .get()
        )
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def get_recent_submissions(self, limit: int = 50) -> list[dict]:
        docs = (
            self.db.collection_group("posts")
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]

    def has_submitted_today(self, user_id: str, today: str) -> bool:
        from datetime import datetime, timezone
        # Primary check: challenge_date field (set on all new posts)
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
        # Fallback: date range for posts created before challenge_date was added
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
        docs = (
            self.db.collection("users")
            .document(user_id)
            .collection("posts")
            .order_by("date", direction=firestore.Query.DESCENDING)
            .stream()
        )
        return [{"id": doc.id, **doc.to_dict()} for doc in docs]
