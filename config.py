import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = "dev-secret-change-later"

DATABASE = os.path.join(BASE_DIR, "data", "challenge.db")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

ADMIN_PASSWORD = "admin123"  # später hashen
