"""
firebase_config.py

Initializes the Firebase Admin SDK using a local service-account key file
and exposes a Firestore client (`db`) for the rest of the app to use.

Local development only:
- firebase-key.json must sit next to this file.
- Never commit firebase-key.json to version control.
- Never send its contents to the frontend or to Gemini.
"""

import os
import sys

import firebase_admin
from firebase_admin import credentials, firestore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_KEY_PATH = os.path.join(BASE_DIR, "firebase-key.json")


def _init_firebase():
    """Initialize the Firebase Admin app once and return a Firestore client."""
    if not os.path.exists(FIREBASE_KEY_PATH):
        print("[firebase_config] 'firebase-key.json' not found next to firebase_config.py.")
        sys.exit(1)

    if not firebase_admin._apps:
        cred = credentials.Certificate(FIREBASE_KEY_PATH)
        firebase_admin.initialize_app(cred)

    return firestore.client()


db = _init_firebase()
