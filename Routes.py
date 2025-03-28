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

        self.session_ids_to_generated_ids = {}  
        self.id_lock = threading.Lock()

        self.speed_test_in_progress = {}
        self.speed_test_status_lock = threading.Lock()   

        self.user_sessions = {}  # Maps session_id -> (lat, long)
        self.session_lock = threading.Lock()

        self.setup_routes()

    def generate_id(self):
        return random.randint(100000, 999999)

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html")

        @self.app.route("/generate_unique_id", methods=["GET"])
        def generate_id_route():
            session_id = request.args.get("session_id")
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400

            with self.id_lock:
                new_id = self.generate_id()
                self.session_ids_to_generated_ids[session_id] = new_id
            return jsonify({"id": new_id})

        @self.app.route("/save_location", methods=["POST"])
        def save_location():
            data = request.json
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id")

            if not session_id:
                return "Missing session_id", 400

            with self.id_lock:
                current_id = self.session_ids_to_generated_ids.get(session_id)

            if latitude is not None and longitude is not None and current_id:
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

        @self.app.route("/speed_test", methods=["GET"])
        def speed_test():
            session_id = request.args.get("session_id")
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400

            with self.speed_test_status_lock:
                if self.speed_test_in_progress.get(session_id):
                    return jsonify({"error": "Speed test already in progress"}), 429
                self.speed_test_in_progress[session_id] = True

            try:
                with self.id_lock:
                    current_id = self.session_ids_to_generated_ids.get(session_id)
                    if current_id is None:
                        return jsonify({"error": "No ID found for this session"}), 400

                download_speed, upload_speed, ping = self.speed_test.run_speed_test()

                if download_speed is None:
                    return jsonify({"error": "Speed test failed"}), 500

                self.db_handler.save_speed_test(download_speed, upload_speed, ping, current_id)

                return jsonify({
                    "download_speed": f"{download_speed:.2f} Mbps",
                    "upload_speed": f"{upload_speed:.2f} Mbps",
                    "ping": f"{ping} ms",
                    "id": current_id
                })
            finally:
                with self.speed_test_status_lock:
                    self.speed_test_in_progress[session_id] = False
        
        @self.app.route("/check_speed_test_status", methods=["GET"])
        def check_speed_test_status():
            session_id = request.args.get("session_id")
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400
            
            with self.speed_test_status_lock:
                in_progress = self.speed_test_in_progress.get(session_id, False)

            return jsonify({"in_progress": in_progress})


    def get_user_session_location(self, session_id):
        with self.session_lock:
            return self.user_sessions.get(session_id, (None, None))

    def get_all_sessions(self):
        with self.session_lock:
            return list(self.user_sessions.keys())


def setup_routes(app):
    Routes(app)
