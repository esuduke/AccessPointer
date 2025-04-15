# Routes.py (Complete - Handles Out-of-Bounds Live Location)
from flask import Flask, render_template, request, jsonify
import uuid
import random
from DatabaseHandler import DatabaseHandler # Assuming DatabaseHandler.py is accessible
import threading
import time

# --- Coordinate Mapping Section ---
# --- UPDATED DIMENSIONS ---
IMAGE_WIDTH = 1003
IMAGE_HEIGHT = 800
# --- END UPDATED DIMENSIONS ---

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
        # Uses the updated IMAGE_WIDTH and IMAGE_HEIGHT constants
        x_pixel_float = ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * IMAGE_WIDTH
        y_pixel_float = ((MAX_LON - lon) / (MAX_LON - MIN_LON)) * IMAGE_HEIGHT
        # --- END ROTATED MAPPING LOGIC ---

        # Clamp float values to image edges - this finds the 'closest edge' point
        x_pixel_clamped = max(0.0, min(x_pixel_float, float(IMAGE_WIDTH - 1)))
        y_pixel_clamped = max(0.0, min(y_pixel_float, float(IMAGE_HEIGHT - 1)))

        # Convert clamped values to int
        x_pixel = int(x_pixel_clamped)
        y_pixel = int(y_pixel_clamped)

        return x_pixel, y_pixel, is_within_bounds # Return statement was indented incorrectly in user-provided code

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
             # Pass updated dimensions to template if needed
            return render_template("index.html", image_width=IMAGE_WIDTH, image_height=IMAGE_HEIGHT)

        @self.app.route("/generate_unique_id", methods=["GET"])
        def generate_id_route():
            session_id = request.args.get("session_id")
            if not session_id: return jsonify({"error": "Missing session_id parameter"}), 400
            with self.id_lock:
                new_id = self.generate_id()
                # Check if session_id already exists and handle if necessary (e.g., log, overwrite, return error)
                # For now, it overwrites the previous ID for the session
                self.session_ids_to_generated_ids[session_id] = new_id
            return jsonify({"id": new_id})

        @self.app.route("/save_location", methods=["POST"])
        def save_location():
            data = request.json
            if not data: return jsonify({"error": "Invalid JSON payload"}), 400
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id") # session_id needed for potential future use, but not directly for saving w/ unique id
            unique_id = data.get("id") # This is the crucial link to the speed test
            # Validate required fields
            if unique_id is None: return jsonify({"error": "Missing unique test id ('id')"}), 400
            if latitude is None or longitude is None: return jsonify({"error": "Missing latitude or longitude"}), 400
            # Optional: Validate session_id if needed for cross-referencing, but unique_id links the data
            # if not session_id: return jsonify({"error": "Missing session_id"}), 400
            try:
                lat_float = float(latitude); lon_float = float(longitude); unique_id_int = int(unique_id)
                self.db_handler.save_location(lat_float, lon_float, unique_id_int)
                return jsonify({"message": "Location saved successfully!", "id": unique_id_int}), 200
            except (ValueError, TypeError) as e: return jsonify({"error": f"Invalid data format: {e}"}), 400
            except Exception as e: print(f"DB save location error: {e}"); return jsonify({"error": "Failed to save location"}), 500

        @self.app.route("/save_user_location", methods=["POST"])
        def save_user_location():
            data = request.get_json(silent=True) # Use silent=True to avoid exception on bad JSON
            if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400
            latitude = data.get("latitude"); longitude = data.get("longitude"); session_id = data.get("session_id")
            if latitude is not None and longitude is not None and session_id is not None:
                try:
                    lat_float = float(latitude); lon_float = float(longitude); current_time = time.time()
                    with self.session_lock: self.user_sessions[session_id] = (lat_float, lon_float, current_time)
                    return jsonify({"status": "User location updated", "session_id": session_id}), 200
                except (TypeError, ValueError): return jsonify({"error": "Invalid lat/lon format"}), 400
            else:
                # More informative error about missing fields
                missing = [f for f in ['latitude', 'longitude', 'session_id'] if data.get(f) is None]
                return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

        @self.app.route("/submit-speed", methods=["POST"])
        def submit_speed():
            data = request.json
            if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400

            # Robust parsing of speed values
            try:
                dl_str = data.get("dlStatus", "0") # Default to "0" string if missing
                ul_str = data.get("ulStatus", "0")
                p_str = data.get("pingStatus", "0")
                # Convert "Fail" to 0, otherwise parse as float
                dl = 0.0 if dl_str == "Fail" else float(dl_str)
                ul = 0.0 if ul_str == "Fail" else float(ul_str)
                p = 0.0 if p_str == "Fail" else float(p_str)
            except (TypeError, ValueError) as e:
                # Log the error and received data for debugging
                print(f"Error parsing speed values: {e}. Data received: {data}")
                # Return an error or default values; let's default to 0 here
                dl, ul, p = 0.0, 0.0, 0.0
                # Optionally return error to client:
                # return jsonify({"error": f"Invalid speed values format. Check dlStatus, ulStatus, pingStatus."}), 400

            session_id = data.get("session_id")
            if not session_id: return jsonify({"error": "Missing session_id"}), 400

            with self.id_lock: current_db_id = self.session_ids_to_generated_ids.get(session_id)
            # Check if an ID was generated for this session
            if current_db_id is None: return jsonify({"error": "No test ID found for this session. Please run a test first or refresh."}), 400

            try:
                self.db_handler.save_speed_test(dl, ul, p, current_db_id)
                return jsonify({"message": "Speed test results saved!", "id": current_db_id}), 200 # Return 200 OK
            except Exception as e: print(f"DB save speed error for ID {current_db_id}: {e}"); return jsonify({"error": "Failed to save speed results"}), 500

        @self.app.route("/heatmap-data", methods=["GET"])
        def get_heatmap_data():
            try:
                combined_data = self.db_handler.get_data()
                heatmap_points = []
                max_speed = 0.0 # Use float for max speed
                points_processed = 0; points_mapped = 0
                for unique_id, info in combined_data.items():
                    points_processed += 1
                    # Safely get speed value
                    speed = 0.0
                    try:
                        # Check if download exists and is not None before converting
                        dl_value = info.get('download')
                        if dl_value is not None:
                            speed = float(dl_value)
                    except (ValueError, TypeError):
                        print(f"Warning: Could not convert download speed '{info.get('download')}' for ID {unique_id} to float. Using 0.")
                        speed = 0.0 # Default to 0 if conversion fails

                    if info.get('location'):
                        lat = info['location']['latitude']; lon = info['location']['longitude']
                        # map_lat_lon_to_pixels uses updated dimensions
                        x_pixel, y_pixel, _ = map_lat_lon_to_pixels(lat, lon)
                        if x_pixel is not None and y_pixel is not None:
                            points_mapped += 1
                            heatmap_points.append({"x": x_pixel, "y": y_pixel, "value": speed})
                            if speed > max_speed: max_speed = speed
                # Ensure max is at least 1 for heatmap.js if points exist but max is 0
                if points_mapped > 0 and max_speed <= 0:
                    max_to_send = 1.0
                elif points_mapped == 0:
                     max_to_send = 1.0 # Default max if no data
                else:
                     max_to_send = max_speed

                return jsonify({"max": max_to_send, "data": heatmap_points})
            except Exception as e: print(f"Error generating heatmap data: {e}"); return jsonify({"error": "Failed to generate heatmap data"}), 500

        @self.app.route("/get-live-location/<session_id>", methods=["GET"])
        def get_live_location(session_id):
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400

            with self.session_lock:
                session_data = self.user_sessions.get(session_id)

            if session_data and len(session_data) == 3:
                lat, lon, timestamp = session_data
                 # map_lat_lon_to_pixels uses updated dimensions
                x_pixel, y_pixel, is_within_bounds = map_lat_lon_to_pixels(lat, lon)

                if x_pixel is not None and y_pixel is not None:
                    return jsonify({
                        "x": x_pixel,
                        "y": y_pixel,
                        "in_bounds": is_within_bounds,
                        "found": True
                    })
                else:
                    return jsonify({"found": False, "reason": "Mapping failed"})
            else:
                 # Check if session exists but has old/invalid data format if needed
                return jsonify({"found": False, "reason": "No recent data for session"})


        @self.app.route("/get_all_sessions", methods=["GET"])
        def get_all_sessions_route():
             with self.session_lock:
                 # Filter out potentially malformed entries just in case
                active_sessions = {
                    sid: time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(sdata[2]))
                    for sid, sdata in self.user_sessions.items()
                    if isinstance(sdata, tuple) and len(sdata) == 3 and isinstance(sdata[2], (int, float))
                }
                return jsonify(active_sessions)

        @self.app.route("/get_location/<session_id>", methods=["GET"])
        def get_location_route(session_id):
            with self.session_lock:
                session_data = self.user_sessions.get(session_id)
                if session_data and isinstance(session_data, tuple) and len(session_data) == 3:
                    lat, lon, last_seen_ts = session_data
                    # Ensure timestamp is valid before formatting
                    try:
                        last_seen_str = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(last_seen_ts))
                    except (ValueError, TypeError):
                        last_seen_str = "Invalid timestamp"
                    return jsonify({"latitude": lat, "longitude": lon, "last_seen": last_seen_str})
                return jsonify({"error": "Session ID not found or data invalid"}), 404

    # --- Helper Methods ---
    def get_user_session_location(self, session_id):
        with self.session_lock:
            session_data = self.user_sessions.get(session_id)
             # Add check for valid format
            if session_data and isinstance(session_data, tuple) and len(session_data) == 3:
                # Ensure lat/lon are potentially valid numbers before returning
                 try:
                     float(session_data[0])
                     float(session_data[1])
                     return (session_data[0], session_data[1])
                 except (ValueError, TypeError):
                     print(f"Warning: Invalid lat/lon format in session data for {session_id}")
                     return (None, None)
            return (None, None)

    def get_all_sessions(self):
        # Ensure thread safety
        with self.session_lock:
            return list(self.user_sessions.keys())

    def cleanup_inactive_sessions(self, timeout_seconds):
        current_time = time.time()
        inactive_session_ids = []
        # Need to operate on a copy of keys or handle dict changes during iteration carefully
        with self.session_lock:
            all_session_ids = list(self.user_sessions.keys()) # Get keys first

        for session_id in all_session_ids:
            with self.session_lock: # Re-acquire lock to safely access data
                sdata = self.user_sessions.get(session_id)
            # Check if data exists, is a tuple, has 3 elements, and timestamp is valid before comparing
            if not (sdata and isinstance(sdata, tuple) and len(sdata) == 3 and isinstance(sdata[2], (int, float))):
                 inactive_session_ids.append(session_id) # Mark invalid format sessions for cleanup
            elif (current_time - sdata[2]) > timeout_seconds:
                inactive_session_ids.append(session_id) # Mark timed-out sessions

        if inactive_session_ids:
            print(f"Cleaning up inactive/invalid sessions: {inactive_session_ids}")
            with self.session_lock:
                for session_id in inactive_session_ids:
                    self.user_sessions.pop(session_id, None) # Use pop with default None
            # Also clean up the associated generated ID mapping
            with self.id_lock:
                 for session_id in inactive_session_ids:
                     self.session_ids_to_generated_ids.pop(session_id, None)
            # Log remaining sessions safely
            with self.session_lock:
                 remaining_sessions = list(self.user_sessions.keys())
            print(f"Cleanup complete. Remaining sessions: {remaining_sessions}")


# --- Function to initialize routes ---
def setup_routes(app):
    routes_instance = Routes(app)
    return routes_instance






