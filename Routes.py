from flask import Flask, render_template, request, jsonify
import uuid
import random
from SpeedTestHandler import SpeedTestHandler
from DatabaseHandler import DatabaseHandler
import threading

class Routes:
    def __init__(self, app: Flask):
        self.app = app
        self.db_handler = DatabaseHandler()
        self.speed_test = SpeedTestHandler()

        # Map session_id to unique ID
        self.session_ids_to_generated_ids = {}
        self.id_lock = threading.Lock()

        # Session ID to latest location (lat, lon)
        self.user_sessions = {}
        self.session_lock = threading.Lock()

        self.setup_routes()

    def generate_id(self):
        return random.randint(100000, 999999)

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

        @self.app.route("/generate_unique_id", methods=["GET"])
        def generate_unique_id():
            unique_id = self.generate_id()
            return jsonify({"id": unique_id})

        @self.app.route("/save_location", methods=["POST"])
        def save_location():
            data = request.json
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id") or data.get("id")  # Accept either key

            if not session_id:
                return "Missing session_id or id", 400

            # Ensure session_id maps to unique id
            with self.id_lock:
                current_id = self.session_ids_to_generated_ids.get(session_id)
                if current_id is None:
                    current_id = self.generate_id()
                    self.session_ids_to_generated_ids[session_id] = current_id

            if latitude is not None and longitude is not None:
                self.db_handler.save_location(latitude, longitude, current_id)
                return "Location saved successfully!", 200

            return "Invalid data", 400

        @self.app.route("/save_user_location", methods=["POST"])
        def save_user_location():
            data = request.get_json(force=True)  # ⬅ forces parsing
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id") or data.get("id")
            # print("save_user_location received:", data)
            if latitude is not None and longitude is not None and session_id is not None:
                with self.session_lock:
                    self.user_sessions[session_id] = (float(latitude), float(longitude))
                return jsonify({"status": "Location saved", "session_id": session_id}), 200
            return jsonify({"error": "Invalid data"}), 400


        @self.app.route("/submit-speed", methods=["POST"])
        def submit_speed():
            data = request.json
            try:
                download_speed = float(data.get("dlStatus"))
                upload_speed = float(data.get("ulStatus"))
                ping = float(data.get("pingStatus"))
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid speed values"}), 400

            session_id = data.get("session_id") or data.get("id")  # Accept either
            if not session_id:
                return jsonify({"error": "Missing session_id or id"}), 400

            # Ensure ID mapping exists
            with self.id_lock:
                current_id = self.session_ids_to_generated_ids.get(session_id)
                if current_id is None:
                    current_id = self.generate_id()
                    self.session_ids_to_generated_ids[session_id] = current_id

            self.db_handler.save_speed_test(download_speed, upload_speed, ping, current_id)
            return jsonify({"message": "Speed test results saved successfully!", "id": current_id})

        # Optional: For debugging from CLI
        @self.app.route("/get_all_sessions", methods=["GET"])
        def get_all_sessions():
            with self.session_lock:
                return jsonify(list(self.user_sessions.keys()))

        @self.app.route("/get_location/<session_id>", methods=["GET"])
        def get_location(session_id):
            with self.session_lock:
                location = self.user_sessions.get(session_id)
                if location:
                    return jsonify({"latitude": location[0], "longitude": location[1]})
                return jsonify({"error": "Session ID not found"}), 404

    def get_user_session_location(self, session_id):
        with self.session_lock:
            return self.user_sessions.get(session_id, (None, None))

    def get_all_sessions(self):
        with self.session_lock:
            return list(self.user_sessions.keys())

def setup_routes(app):
    Routes(app)