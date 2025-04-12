# Routes.py (Complete - Updated with Precise Corner Bounds)
from flask import Flask, render_template, request, jsonify
import uuid
import random
from DatabaseHandler import DatabaseHandler # Assuming DatabaseHandler.py is accessible
import threading
import time

# --- Coordinate Mapping Section ---
IMAGE_WIDTH = 1507
IMAGE_HEIGHT = 1202

# --- Bounds derived from user-provided corner coordinates ---
# Bottom Right: 43.037278, -76.132917
# Top Right:    43.037306, -76.132194
# Top Left:     43.037944, -76.132250
# Bottom Left:  43.037944, -76.132944

MIN_LAT = 43.037278  # Smallest Latitude from corners
MAX_LAT = 43.037944  # Largest Latitude from corners
MIN_LON = -76.132944 # Smallest Longitude (most negative) from corners
MAX_LON = -76.132194 # Largest Longitude (least negative) from corners
# --- End Bounds ---

def map_lat_lon_to_pixels(latitude, longitude):
    """
    Maps geographic coordinates to image pixel coordinates using precise bounds
    derived from corner points. Assumes West corresponds to the bottom of the image.
    Returns (x, y) pixel coordinates or (None, None) if mapping fails.
    """
    try:
        lat = float(latitude)
        lon = float(longitude)

        # Check if within *precise* bounds (add tiny buffer for float comparisons)
        epsilon = 1e-9 # A very small number for tolerance
        if not (MIN_LAT - epsilon <= lat <= MAX_LAT + epsilon and MIN_LON - epsilon <= lon <= MAX_LON + epsilon):
            # Optional: Keep this print only if points are still unexpectedly outside
            # print(f"DEBUG: Point ({lat}, {lon}) is OUTSIDE defined bounds ({MIN_LAT}-{MAX_LAT}, {MIN_LON}-{MAX_LON}).")
            return None, None

        # Avoid division by zero if bounds are identical
        if abs(MAX_LAT - MIN_LAT) < epsilon or abs(MAX_LON - MIN_LON) < epsilon:
             print(f"DEBUG: Error - MIN/MAX Lat or Lon are too close, cannot map.")
             return None, None

        # --- ROTATED MAPPING LOGIC (West at Bottom - Unchanged logic, uses new bounds) ---
        # Latitude (North/South) maps to X-pixel (Left/Right)
        x_pixel_float = ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * IMAGE_WIDTH

        # Longitude (West/East) maps to Y-pixel (Top/Bottom)
        y_pixel_float = ((MAX_LON - lon) / (MAX_LON - MIN_LON)) * IMAGE_HEIGHT
        # --- END ROTATED MAPPING LOGIC ---

        # Clamp values first (using 0.0 and float dimensions for consistency)
        x_pixel_clamped = max(0.0, min(x_pixel_float, float(IMAGE_WIDTH - 1)))
        y_pixel_clamped = max(0.0, min(y_pixel_float, float(IMAGE_HEIGHT - 1)))

        # Convert to int AFTER clamping
        x_pixel = int(x_pixel_clamped)
        y_pixel = int(y_pixel_clamped)

        # Optional: Keep this print for final debugging if needed
        # print(f"DEBUG: Final Rotated Mapped Ints ({lat}, {lon}) -> ({x_pixel}, {y_pixel})")

        return x_pixel, y_pixel
    except (ValueError, TypeError) as e:
        print(f"DEBUG: Error converting lat/lon ({latitude}, {longitude}): {e}")
        return None, None

# --- End Coordinate Mapping Section ---


class Routes:
    def __init__(self, app: Flask):
        self.app = app
        self.db_handler = DatabaseHandler()
        self.session_ids_to_generated_ids = {}
        self.id_lock = threading.Lock()
        self.user_sessions = {}
        self.session_lock = threading.Lock()
        self.setup_routes()

    def generate_id(self):
        """Generates a random integer ID."""
        return random.randint(100000, 999999)

    def setup_routes(self):
        @self.app.route("/")
        def index():
            """Renders the main HTML page."""
            return render_template("index.html", image_width=IMAGE_WIDTH, image_height=IMAGE_HEIGHT)

        @self.app.route("/generate_unique_id", methods=["GET"])
        def generate_id_route():
            session_id = request.args.get("session_id")
            if not session_id:
                return jsonify({"error": "Missing session_id parameter"}), 400
            with self.id_lock:
                new_id = self.generate_id()
                self.session_ids_to_generated_ids[session_id] = new_id
            return jsonify({"id": new_id})

        @self.app.route("/save_location", methods=["POST"])
        def save_location():
            data = request.json
            if not data: return jsonify({"error": "Invalid JSON payload"}), 400
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id")
            unique_id = data.get("id")
            if not session_id: return jsonify({"error": "Missing session_id"}), 400
            if unique_id is None: return jsonify({"error": "Missing unique test id ('id')"}), 400
            if latitude is None or longitude is None: return jsonify({"error": "Missing latitude or longitude"}), 400

            try:
                lat_float = float(latitude)
                lon_float = float(longitude)
                unique_id_int = int(unique_id)
                self.db_handler.save_location(lat_float, lon_float, unique_id_int)
                return jsonify({"message": "Location saved successfully!", "id": unique_id_int}), 200
            except (ValueError, TypeError) as e:
                 print(f"Error converting location/id data: {e}")
                 return jsonify({"error": "Invalid data format for location or id"}), 400
            except Exception as e:
                 print(f"Database error saving location: {e}")
                 return jsonify({"error": "Failed to save location data"}), 500

        @self.app.route("/save_user_location", methods=["POST"])
        def save_user_location():
            data = request.get_json(silent=True)
            if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id")

            if latitude is not None and longitude is not None and session_id is not None:
                try:
                    lat_float = float(latitude)
                    lon_float = float(longitude)
                    current_time = time.time()
                    with self.session_lock:
                        self.user_sessions[session_id] = (lat_float, lon_float, current_time)
                    return jsonify({"status": "Location saved", "session_id": session_id}), 200
                except (TypeError, ValueError):
                     print(f"Error converting location data for session {session_id}")
                     return jsonify({"error": "Invalid latitude/longitude format"}), 400
            else:
                missing = [f for f in ['latitude', 'longitude', 'session_id'] if data.get(f) is None]
                return jsonify({"error": f"Invalid data: Missing fields {missing}"}), 400

        @self.app.route("/submit-speed", methods=["POST"])
        def submit_speed():
            data = request.json
            if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400
            try:
                download_speed = float(data.get("dlStatus"))
                upload_speed = float(data.get("ulStatus"))
                ping = float(data.get("pingStatus"))
            except (TypeError, ValueError, KeyError) as e:
                print(f"Error parsing speed values: {e}")
                return jsonify({"error": f"Invalid or missing speed values: {e}"}), 400

            session_id = data.get("session_id")
            if not session_id: return jsonify({"error": "Missing session_id"}), 400

            with self.id_lock:
                current_db_id = self.session_ids_to_generated_ids.get(session_id)
            if current_db_id is None:
                 print(f"Error: No DB ID found for session {session_id} during speed submit.")
                 return jsonify({"error": "Associated database ID not found. Refresh/retry test."}), 400

            try:
                self.db_handler.save_speed_test(download_speed, upload_speed, ping, current_db_id)
                return jsonify({"message": "Speed test results saved!", "id": current_db_id})
            except Exception as e:
                 print(f"DB error saving speed test for ID {current_db_id}: {e}")
                 return jsonify({"error": "Failed to save speed test results"}), 500

        @self.app.route("/heatmap-data", methods=["GET"])
        def get_heatmap_data():
            """
            Fetches data, maps coordinates using precise bounds & rotated logic,
            and returns data formatted for heatmap.js.
            """
            try:
                combined_data = self.db_handler.get_data()
                heatmap_points = []
                max_speed = 0
                points_processed = 0
                points_mapped = 0

                for unique_id, info in combined_data.items():
                    points_processed += 1
                    if info.get('location') and info.get('download') is not None:
                        lat = info['location']['latitude']
                        lon = info['location']['longitude']
                        speed = info['download']
                        x_pixel, y_pixel = map_lat_lon_to_pixels(lat, lon) # Uses updated bounds

                        if x_pixel is not None and y_pixel is not None:
                            points_mapped += 1
                            heatmap_points.append({"x": x_pixel, "y": y_pixel, "value": speed})
                            if speed > max_speed: max_speed = speed

                # Optional: Keep summary print for debugging
                # print(f"DEBUG HEATMAP DATA: Processed {points_processed} entries. Mapped {points_mapped} points.")

                return jsonify({
                    "max": max_speed if max_speed > 0 else 100,
                    "data": heatmap_points
                })
            except Exception as e:
                print(f"Error generating heatmap data: {e}")
                return jsonify({"error": "Failed to generate heatmap data"}), 500

        # --- Routes for debugging/displaying session info ---
        @self.app.route("/get_all_sessions", methods=["GET"])
        def get_all_sessions_route():
             with self.session_lock:
                active_sessions = {sid: time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(sdata[2]))
                                   for sid, sdata in self.user_sessions.items() if sdata and len(sdata) == 3}
                return jsonify(active_sessions)


        @self.app.route("/get_location/<session_id>", methods=["GET"])
        def get_location_route(session_id):
            with self.session_lock:
                session_data = self.user_sessions.get(session_id)
                if session_data and len(session_data) == 3:
                    lat, lon, last_seen_ts = session_data
                    return jsonify({
                        "latitude": lat, "longitude": lon,
                        "last_seen": time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(last_seen_ts))
                        })
                return jsonify({"error": "Session ID not found or data invalid"}), 404

    # --- Helper Methods ---
    def get_user_session_location(self, session_id):
        with self.session_lock:
            session_data = self.user_sessions.get(session_id)
            if session_data and len(session_data) == 3: return (session_data[0], session_data[1])
            return (None, None)

    def get_all_sessions(self):
        with self.session_lock: return list(self.user_sessions.keys())

    def cleanup_inactive_sessions(self, timeout_seconds):
        current_time = time.time()
        inactive_session_ids = [sid for sid, sdata in self.user_sessions.items()
                                if not sdata or len(sdata) != 3 or (current_time - sdata[2]) > timeout_seconds]

        if inactive_session_ids:
            with self.session_lock:
                for session_id in inactive_session_ids:
                    self.user_sessions.pop(session_id, None) # Remove from sessions dict
            with self.id_lock:
                 for session_id in inactive_session_ids:
                     self.session_ids_to_generated_ids.pop(session_id, None) # Remove from ID map dict
            # print(f"Session cleanup: Removed {len(inactive_session_ids)} inactive sessions.") # Optional log

# --- Function to initialize routes ---
def setup_routes(app):
    routes_instance = Routes(app)
    return routes_instance