# Routes.py (Complete - Handles Out-of-Bounds Live Location)
from flask import Flask, render_template, request, jsonify
import uuid
import random
from DatabaseHandler import DatabaseHandler # Assuming DatabaseHandler.py is accessible
import threading
import time

# --- Coordinate Mapping Section ---
IMAGE_WIDTH = 1507
IMAGE_HEIGHT = 1202

# Bounds derived from user-provided corner coordinates
MIN_LAT = 43.037278
MAX_LAT = 43.037944
MIN_LON = -76.132944
MAX_LON = -76.132194

def map_lat_lon_to_pixels(latitude, longitude):
    """
    Maps geographic coordinates to image pixel coordinates.
    Calculates mapping even if outside bounds and returns clamped coordinates
    along with an 'in_bounds' status.
    Assumes West corresponds to the bottom of the image.
    Returns (x, y, is_within_bounds) or (None, None, False) if conversion fails.
    """
    try:
        lat = float(latitude)
        lon = float(longitude)
        epsilon = 1e-9 # Tolerance for float comparison

        # Determine if the original point is within bounds BEFORE clamping
        is_within_bounds = (MIN_LAT - epsilon <= lat <= MAX_LAT + epsilon and
                            MIN_LON - epsilon <= lon <= MAX_LON + epsilon)

        # Avoid division by zero if bounds are identical
        if abs(MAX_LAT - MIN_LAT) < epsilon or abs(MAX_LON - MIN_LON) < epsilon:
             print(f"DEBUG: Error - MIN/MAX Lat or Lon are too close, cannot map.")
             return None, None, False # Indicate mapping failure

        # --- ROTATED MAPPING LOGIC (Calculate floats regardless of bounds) ---
        x_pixel_float = ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * IMAGE_WIDTH
        y_pixel_float = ((MAX_LON - lon) / (MAX_LON - MIN_LON)) * IMAGE_HEIGHT
        # --- END ROTATED MAPPING LOGIC ---

        # Clamp float values to image edges - this finds the 'closest edge' point
        x_pixel_clamped = max(0.0, min(x_pixel_float, float(IMAGE_WIDTH - 1)))
        y_pixel_clamped = max(0.0, min(y_pixel_float, float(IMAGE_HEIGHT - 1)))

        # Convert clamped values to int
        x_pixel = int(x_pixel_clamped)
        y_pixel = int(y_pixel_clamped)

        # Optional debug prints
        # if not is_within_bounds:
        #      print(f"DEBUG: Point ({lat}, {lon}) is OUTSIDE bounds, Clamped to ({x_pixel}, {y_pixel})")
        # else:
        #      print(f"DEBUG: Point ({lat}, {lon}) is INSIDE bounds, Mapped to ({x_pixel}, {y_pixel})")

        # Return coordinates AND whether original point was in bounds
        return x_pixel, y_pixel, is_within_bounds

    except (ValueError, TypeError) as e:
        print(f"DEBUG: Error converting lat/lon ({latitude}, {longitude}): {e}")
        return None, None, False # Indicate mapping failure

# --- End Coordinate Mapping Section ---


class Routes:
    def __init__(self, app: Flask):
        self.app = app
        self.db_handler = DatabaseHandler()
        self.session_ids_to_generated_ids = {}
        self.id_lock = threading.Lock()
        self.user_sessions = {} # Stores {session_id: (lat, lon, timestamp)}
        self.session_lock = threading.Lock()
        self.setup_routes()

    def generate_id(self):
        return random.randint(100000, 999999)

    def setup_routes(self):
        @self.app.route("/")
        def index():
            return render_template("index.html", image_width=IMAGE_WIDTH, image_height=IMAGE_HEIGHT)

        # --- Other routes remain the same ---
        @self.app.route("/generate_unique_id", methods=["GET"])
        def generate_id_route():
            # (Code remains the same)
            session_id = request.args.get("session_id")
            if not session_id: return jsonify({"error": "Missing session_id parameter"}), 400
            with self.id_lock:
                new_id = self.generate_id()
                self.session_ids_to_generated_ids[session_id] = new_id
            return jsonify({"id": new_id})

        @self.app.route("/save_location", methods=["POST"])
        def save_location():
             # (Code remains the same)
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
                lat_float = float(latitude); lon_float = float(longitude); unique_id_int = int(unique_id)
                self.db_handler.save_location(lat_float, lon_float, unique_id_int)
                return jsonify({"message": "Location saved successfully!", "id": unique_id_int}), 200
            except (ValueError, TypeError) as e: return jsonify({"error": f"Invalid data format: {e}"}), 400
            except Exception as e: print(f"DB save location error: {e}"); return jsonify({"error": "Failed to save location"}), 500

        @self.app.route("/save_user_location", methods=["POST"])
        def save_user_location():
            # (Code remains the same)
            data = request.get_json(silent=True)
            if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400
            latitude = data.get("latitude"); longitude = data.get("longitude"); session_id = data.get("session_id")
            if latitude is not None and longitude is not None and session_id is not None:
                try:
                    lat_float = float(latitude); lon_float = float(longitude); current_time = time.time()
                    with self.session_lock: self.user_sessions[session_id] = (lat_float, lon_float, current_time)
                    return jsonify({"status": "User location updated", "session_id": session_id}), 200
                except (TypeError, ValueError): return jsonify({"error": "Invalid lat/lon format"}), 400
            else: missing = [f for f in ['latitude','longitude','session_id'] if data.get(f) is None]; return jsonify({"error": f"Missing fields {missing}"}), 400

        @self.app.route("/submit-speed", methods=["POST"])
        def submit_speed():
             # (Code remains the same)
            data = request.json
            if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400
            try:
                dl = float(data.get("dlStatus")); ul = float(data.get("ulStatus")); p = float(data.get("pingStatus"))
            except (TypeError, ValueError, KeyError) as e: return jsonify({"error": f"Invalid speed values: {e}"}), 400
            session_id = data.get("session_id")
            if not session_id: return jsonify({"error": "Missing session_id"}), 400
            with self.id_lock: current_db_id = self.session_ids_to_generated_ids.get(session_id)
            if current_db_id is None: return jsonify({"error": "Associated DB ID not found. Refresh."}), 400
            try:
                self.db_handler.save_speed_test(dl, ul, p, current_db_id)
                return jsonify({"message": "Speed test results saved!", "id": current_db_id})
            except Exception as e: print(f"DB save speed error for {current_db_id}: {e}"); return jsonify({"error": "Failed to save speed results"}), 500

        @self.app.route("/heatmap-data", methods=["GET"])
        def get_heatmap_data():
            # (Code remains the same - uses the updated map_lat_lon_to_pixels indirectly)
            try:
                combined_data = self.db_handler.get_data()
                heatmap_points = []
                max_speed = 0; points_processed = 0; points_mapped = 0
                for unique_id, info in combined_data.items():
                    points_processed += 1
                    if info.get('location') and info.get('download') is not None:
                        lat = info['location']['latitude']; lon = info['location']['longitude']
                        speed = info['download']
                        # map_lat_lon_to_pixels now returns x, y, in_bounds_status
                        # We only care about x, y for the heatmap itself
                        x_pixel, y_pixel, _ = map_lat_lon_to_pixels(lat, lon)
                        if x_pixel is not None and y_pixel is not None: # Check if mapping succeeded
                            points_mapped += 1
                            heatmap_points.append({"x": x_pixel, "y": y_pixel, "value": speed})
                            if speed > max_speed: max_speed = speed
                # print(f"DEBUG HEATMAP DATA: Processed {points_processed} entries. Mapped {points_mapped} points.") # Optional log
                return jsonify({"max": max_speed if max_speed > 0 else 100, "data": heatmap_points})
            except Exception as e: print(f"Error generating heatmap data: {e}"); return jsonify({"error": "Failed to generate heatmap data"}), 500

        # --- MODIFIED ROUTE TO GET LIVE LOCATION & BOUNDS STATUS ---
        @self.app.route("/get-live-location/<session_id>", methods=["GET"])
        def get_live_location(session_id):
            """
            Gets the latest location for a session, maps it (clamping to edge if needed),
            and returns pixel coordinates along with whether the original point was in bounds.
            """
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400

            with self.session_lock:
                session_data = self.user_sessions.get(session_id)

            if session_data and len(session_data) == 3:
                lat, lon, timestamp = session_data
                # Get x, y (clamped if needed) and the original in_bounds status
                x_pixel, y_pixel, is_within_bounds = map_lat_lon_to_pixels(lat, lon)

                if x_pixel is not None and y_pixel is not None:
                    # Return coordinates AND the in_bounds status
                    return jsonify({
                        "x": x_pixel,
                        "y": y_pixel,
                        "in_bounds": is_within_bounds, # True if original was inside, False otherwise
                        "found": True
                    })
                else:
                    # Original mapping failed (e.g., conversion error)
                    return jsonify({"found": False, "reason": "Mapping failed"})
            else:
                # No location data found for this session yet
                return jsonify({"found": False, "reason": "No data for session"})
        # --- END MODIFIED ROUTE ---

        @self.app.route("/get_all_sessions", methods=["GET"])
        def get_all_sessions_route():
             # (Code remains the same)
             with self.session_lock:
                active_sessions = {sid: time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(sdata[2]))
                                   for sid, sdata in self.user_sessions.items() if sdata and len(sdata) == 3}
                return jsonify(active_sessions)

        @self.app.route("/get_location/<session_id>", methods=["GET"])
        def get_location_route(session_id):
             # (Code remains the same)
            with self.session_lock:
                session_data = self.user_sessions.get(session_id)
                if session_data and len(session_data) == 3:
                    lat, lon, last_seen_ts = session_data
                    return jsonify({"latitude": lat, "longitude": lon, "last_seen": time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(last_seen_ts))})
                return jsonify({"error": "Session ID not found or data invalid"}), 404

    # --- Helper Methods ---
    def get_user_session_location(self, session_id):
         # (Code remains the same)
        with self.session_lock:
            session_data = self.user_sessions.get(session_id)
            if session_data and len(session_data) == 3: return (session_data[0], session_data[1])
            return (None, None)

    def get_all_sessions(self):
         # (Code remains the same)
        with self.session_lock: return list(self.user_sessions.keys())

    def cleanup_inactive_sessions(self, timeout_seconds):
         # (Code remains the same)
        current_time = time.time()
        inactive_session_ids = [sid for sid, sdata in self.user_sessions.items()
                                if not sdata or len(sdata) != 3 or (current_time - sdata[2]) > timeout_seconds]
        if inactive_session_ids:
            with self.session_lock:
                for session_id in inactive_session_ids: self.user_sessions.pop(session_id, None)
            with self.id_lock:
                 for session_id in inactive_session_ids: self.session_ids_to_generated_ids.pop(session_id, None)

# --- Function to initialize routes ---
def setup_routes(app):
    routes_instance = Routes(app)
    return routes_instance
