from .firestore import model as _Model

# Singleton instance shared across app.py and all route blueprints.
# Importing from here (rather than from app.py) avoids circular imports.
instance = _Model()
