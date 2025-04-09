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

        # Maps browser session_id (a string generated on the client) to a unique numeric id.
        self.session_ids_to_generated_ids = {}
        self.id_lock = threading.Lock()

        # Stores user location data (for real‑time updates) keyed by session_id.
        self.user_sessions = {}
        self.session_lock = threading.Lock()

        self.setup_routes()

    def generate_id(self):
        return random.randint(100000, 999999)

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

        @self.app.route("/save_location", methods=["POST"])
        def save_location():
            data = request.json
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id")
            if not session_id:
                return "Missing session_id", 400

            # Retrieve or generate a unique id for this session.
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
            data = request.json
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id")

            if latitude is not None and longitude is not None and session_id is not None:
                with self.session_lock:
                    self.user_sessions[session_id] = (float(latitude), float(longitude))
                return jsonify({"status": "Location saved", "session_id": session_id}), 200
            return jsonify({"error": "Invalid data"}), 400

        @self.app.route("/submit-speed", methods=["POST"])
        def submit_speed():
            data = request.json
            # Extract the LibreSpeed test metrics from the received data.
            download_speed = data.get("dlStatus")
            upload_speed = data.get("ulStatus")
            ping = data.get("pingStatus")
            
            session_id = data.get("session_id")
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400

            # Retrieve or generate a unique id for this session.
            with self.id_lock:
                current_id = self.session_ids_to_generated_ids.get(session_id)
                if current_id is None:
                    current_id = self.generate_id()
                    self.session_ids_to_generated_ids[session_id] = current_id

            # Store the speed test results using the unique id.
            self.db_handler.save_speed_test(download_speed, upload_speed, ping, current_id)
            
            return jsonify({"message": "Speed test results saved successfully!", "id": current_id})

    def get_user_session_location(self, session_id):
        with self.session_lock:
            return self.user_sessions.get(session_id, (None, None))

    def get_all_sessions(self):
        with self.session_lock:
            return list(self.user_sessions.keys())

def setup_routes(app):
    Routes(app)
