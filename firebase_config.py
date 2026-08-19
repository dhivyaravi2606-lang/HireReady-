import os
import json
import firebase_admin
from firebase_admin import credentials, firestore


def _init_firebase():
    firebase_credentials = os.environ.get("FIREBASE_CREDENTIALS")

    if not firebase_credentials:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS environment variable is not set."
        )

    try:
        credentials_dict = json.loads(firebase_credentials)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            "FIREBASE_CREDENTIALS contains invalid JSON."
        ) from e

    if not firebase_admin._apps:
        cred = credentials.Certificate(credentials_dict)
        firebase_admin.initialize_app(cred)

    return firestore.client()


db = _init_firebase()
  
