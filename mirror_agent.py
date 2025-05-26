from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
import platform
import subprocess
from dotenv import load_dotenv
import speech_recognition as sr
import json
from datetime import datetime

# --- Setup ---
app = Flask(__name__)
CORS(app)
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Persistent memory
MEMORY_FILE = "chat_memory.json"
AFFIRMATION_FILE = "daily_affirmation.txt"

# --- Memory ---
def save_chat_history():
    with open(MEMORY_FILE, "w") as f:
        json.dump(chat_history, f)

def load_chat_history():
    global chat_history
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            chat_history = json.load(f)
    else:
        chat_history = [
            {"role": "system", "content": "You are a helpful smart mirror assistant. Keep responses short and conversational."}
        ]

def is_fresh_today(file_path):
    if not os.path.exists(file_path):
        return False
    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
    return file_time.date() == datetime.now().date()

# --- TTS ---
def speak(text):
    if platform.system() == "Darwin":
        subprocess.run(["say", text])
    else:
        print("🗣️ " + text)  # Replace with actual TTS on Raspberry Pi

# --- Routes ---

@app.route('/query', methods=['POST'])
def query():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({"error": "Missing 'message'"}), 400

        user_input = data['message']
        chat_history.append({"role": "user", "content": user_input})

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=chat_history
        )

        reply = response.choices[0].message.content.strip()
        chat_history.append({"role": "assistant", "content": reply})
        save_chat_history()

        speak(reply)
        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route('/voice', methods=['GET'])
def voice_query():
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    with mic as source:
        print("🎤 Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)

    try:
        transcript = recognizer.recognize_google(audio)
        print(f"🗣️ You said: {transcript}")
        chat_history.append({"role": "user", "content": transcript})

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=chat_history
        )

        reply = response.choices[0].message.content.strip()
        chat_history.append({"role": "assistant", "content": reply})
        save_chat_history()

        speak(reply)
        return jsonify({"response": reply})

    except sr.UnknownValueError:
        return jsonify({"error": "Could not understand audio"}), 400
    except sr.RequestError as e:
        return jsonify({"error": f"Speech recognition error: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {str(e)}"}), 500


@app.route('/reset', methods=['POST'])
def reset_conversation():
    global chat_history
    chat_history = [
        {"role": "system", "content": "You are a helpful smart mirror assistant. Keep responses short and conversational."}
    ]
    save_chat_history()
    speak("Conversation history cleared.")
    return jsonify({"status": "Conversation reset."})


@app.route('/affirmation', methods=['GET'])
def get_affirmation():
    try:
        if is_fresh_today(AFFIRMATION_FILE):
            with open(AFFIRMATION_FILE, "r") as f:
                return jsonify({"response": f.read()})

        # Generate new affirmation
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a motivational assistant."},
                {"role": "user", "content": "Give me a short, uplifting daily affirmation. Keep it under 20 words."}
            ]
        )
        affirmation = response.choices[0].message.content.strip()

        with open(AFFIRMATION_FILE, "w") as f:
            f.write(affirmation)

        return jsonify({"response": affirmation})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# --- Launch ---
if __name__ == '__main__':
    print("🪞 Mirror agent is alive and listening...")
    load_chat_history()
    speak("Your smart mirror is alive and listening.")
    app.run(host='0.0.0.0', port=5000)
