"""
app.py

Main Flask application for sincet_assistant.

Flow:
    User -> index.html -> fetch() -> POST /api/chat
    -> pull college knowledge from Firestore
    -> combine SYSTEM_PROMPT + Firestore knowledge + history + question
    -> Gemini generates a response
    -> JSON response back to the browser
"""

import os

from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types

from chatbot_config import SYSTEM_PROMPT
from firebase_config import db
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash")
PORT = int(os.environ.get("PORT", 5000))

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

client = genai.Client(api_key=GEMINI_API_KEY)
app = Flask(__name__)


# ---------------------------------------------------------------------------
# Firestore knowledge retrieval
# ---------------------------------------------------------------------------
def _format_document(doc, indent=""):
    """Format a Firestore document, including any sub-collections, as text."""
    data = doc.to_dict() or {}
    lines = [f"{indent}  - {key}: {value}" for key, value in data.items()]
    text = f"{indent}[{doc.id}]"
    if lines:
        text += "\n" + "\n".join(lines)

    for sub_collection in doc.reference.collections():
        sub_entries = [
            _format_document(sub_doc, indent + "    ")
            for sub_doc in sub_collection.stream()
        ]
        if sub_entries:
            text += f"\n{indent}  ({sub_collection.id}):\n" + "\n".join(sub_entries)

    return text


def get_college_knowledge():
    """
    Read every collection and document that currently exists in Firestore
    and format it into a plain-text block for the Gemini prompt.

    Collections are discovered automatically (db.collections()), so any
    collection you create in the Firebase console is picked up as-is,
    whatever you name it.
    """
    try:
        collections = list(db.collections())
    except Exception as exc:
        print(f"[firestore] Could not list collections: {exc}")
        return "(Could not reach the Firestore knowledge base.)"

    sections = []
    for collection_ref in collections:
        try:
            entries = [_format_document(doc) for doc in collection_ref.stream()]
        except Exception as exc:
            print(f"[firestore] Could not read collection '{collection_ref.id}': {exc}")
            continue

        entries = [e for e in entries if e.strip()]
        if entries:
            sections.append(f"## {collection_ref.id}\n" + "\n\n".join(entries))

    return "\n\n".join(sections) if sections else "(No data found in Firestore yet.)"


# ---------------------------------------------------------------------------
# Gemini call
# ---------------------------------------------------------------------------
def build_contents(history, college_knowledge, user_message):
    """Turn conversation history + Firestore knowledge + question into Gemini's `contents`."""
    contents = [
        types.Content(
            role="user" if turn.get("role") == "user" else "model",
            parts=[types.Part(text=turn["content"])],
        )
        for turn in history
        if turn.get("content")
    ]

    current_turn = (
        f"COLLEGE KNOWLEDGE (from Firebase):\n{college_knowledge}\n\n"
        f"CURRENT QUESTION:\n{user_message}"
    )
    contents.append(types.Content(role="user", parts=[types.Part(text=current_turn)]))
    return contents


def ask_gemini(history, college_knowledge, user_message):
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=build_contents(history, college_knowledge, user_message),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.4,
            max_output_tokens=1024,
        ),
    )
    return response.text


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid request body. Expected JSON."}), 400

    user_message = (payload.get("message") or "").strip()
    history = payload.get("history") or []

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400
    if not isinstance(history, list):
        return jsonify({"error": "'history' must be a list."}), 400

    try:
        college_knowledge = get_college_knowledge()
    except Exception as exc:
        print(f"[firestore] Error retrieving knowledge: {exc}")
        return jsonify({"error": "Couldn't reach the college knowledge base. Please try again."}), 502

    try:
        reply = ask_gemini(history, college_knowledge, user_message)
    except Exception as exc:
        print(f"[gemini] Error generating response: {exc}")
        return jsonify({"error": "Couldn't generate a response right now. Please try again."}), 502

    return jsonify({"reply": reply or "Sorry, I couldn't come up with an answer to that."})


if __name__ == "__main__":
    app.run(debug=True, port=PORT)
