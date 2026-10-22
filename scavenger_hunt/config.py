import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "scavenger_hunt.db")

# Secret key for session management
SECRET_KEY = os.environ.get("SECRET_KEY", "scavenger-hunt-secret-key-2026-xyz")

# Master PIN for Admin access
DEFAULT_MASTER_PIN = os.environ.get("ADMIN_PIN", "3102")
