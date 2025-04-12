# Routes.py (Complete - Corrected Rotated Mapping for Y-Axis)
from flask import Flask, render_template, request, jsonify
import uuid
import random
from DatabaseHandler import DatabaseHandler # Assuming DatabaseHandler.py is in the same directory or accessible
import threading
import time

# --- Coordinate Mapping Section ---
IMAGE_WIDTH = 1507
IMAGE_HEIGHT = 1202

# Use previously adjusted bounds (modify if needed)
MIN_LAT = 43.03695
MAX_LAT = 43.03805
MIN_LON = -76.1331
MAX_LON = -76.1309

def map_lat_lon_to_pixels(latitude, longitude):
    """
    Maps geographic coordinates to image pixel coordinates,
    assuming West corresponds to the bottom of the image.
    CORRECTED Y-AXIS LOGIC.
    Returns (x, y) pixel coordinates or (None, None) if mapping fails.
    """
    try:
        lat = float(latitude)
        lon = float(longitude)

        # Check if within bounds
        if not (MIN_LAT <= lat <= MAX_LAT and MIN_LON <= lon <= MAX_LON):
            print(f"DEBUG: Point ({lat}, {lon}) is OUTSIDE defined bounds ({MIN_LAT}-{MAX_LAT}, {MIN_LON}-{MAX_LON}).")
            return None, None

        # Avoid division by zero
        if MAX_LAT == MIN_LAT or MAX_LON == MIN_LON:
             print(f"DEBUG: Error - MIN/MAX Lat or Lon are identical, cannot map.")
             return None, None

        # --- ROTATED MAPPING LOGIC ---
        # Latitude (North/South) maps to X-pixel (Left/Right)
        # Since North is Left (lower X), use (MAX_LAT - lat)
        x_pixel_float = ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * IMAGE_WIDTH

        # Longitude (West/East) maps to Y-pixel (Top/Bottom)
        # Since West is Bottom (higher Y), use (MAX_LON - lon) - CORRECTED
        y_pixel_float = ((MAX_LON - lon) / (MAX_LON - MIN_LON)) * IMAGE_HEIGHT
        # --- END ROTATED MAPPING LOGIC ---

        # print(f"DEBUG: Raw Rotated Mapped Floats ({lat}, {lon}) -> ({x_pixel_float:.4f}, {y_pixel_float:.4f})") # Optional debug

        # Clamp values first
        x_pixel_clamped = max(0.0, min(x_pixel_float, float(IMAGE_WIDTH - 1)))
        y_pixel_clamped = max(0.0, min(y_pixel_float, float(IMAGE_HEIGHT - 1)))

        # Convert to int AFTER clamping
        x_pixel = int(x_pixel_clamped)
        y_pixel = int(y_pixel_clamped)

        print(f"DEBUG: Final Rotated Mapped Ints ({lat}, {lon}) -> ({x_pixel}, {y_pixel})") # Keep for debugging

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
            # Pass correct image dimensions to template
            return render_template("index.html", image_width=IMAGE_WIDTH, image_height=IMAGE_HEIGHT)

        @self.app.route("/generate_unique_id", methods=["GET"])
        def generate_id_route():
            session_id = request.args.get("session_id")
            if not session_id:
                return jsonify({"error": "Missing session_id parameter"}), 400
            with self.id_lock:
                new_id = self.generate_id()
                self.session_ids_to_generated_ids[session_id] = new_id
                # print(f"Generated ID {new_id} for session {session_id}") # Logging
            return jsonify({"id": new_id})

        @self.app.route("/save_location", methods=["POST"])
        def save_location():
            data = request.json
            if not data:
                 return jsonify({"error": "Invalid JSON payload"}), 400

            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id")
            unique_id = data.get("id")

            if not session_id:
                return jsonify({"error": "Missing session_id in JSON body"}), 400
            if unique_id is None:
                 return jsonify({"error": "Missing unique test id ('id') in JSON body"}), 400
            if latitude is None or longitude is None:
                return jsonify({"error": "Missing latitude or longitude in JSON body"}), 400

            try:
                lat_float = float(latitude)
                lon_float = float(longitude)
                unique_id_int = int(unique_id)

                self.db_handler.save_location(lat_float, lon_float, unique_id_int)
                # print(f"Saved location for ID {unique_id_int} (Session: {session_id})")
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
            if not data:
                return jsonify({"error": "Invalid or empty JSON payload"}), 400

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
            if not data:
                return jsonify({"error": "Invalid or empty JSON payload"}), 400

            try:
                download_speed = float(data.get("dlStatus"))
                upload_speed = float(data.get("ulStatus"))
                ping = float(data.get("pingStatus"))
            except (TypeError, ValueError, KeyError) as e:
                print(f"Error parsing speed values: {e}")
                return jsonify({"error": f"Invalid or missing speed values in JSON body: {e}"}), 400

            session_id = data.get("session_id")
            if not session_id:
                return jsonify({"error": "Missing session_id in JSON body"}), 400

            with self.id_lock:
                current_db_id = self.session_ids_to_generated_ids.get(session_id)

            if current_db_id is None:
                 print(f"Error: No database ID found mapped for session {session_id} during speed submit.")
                 return jsonify({"error": "Associated database ID not found for this session. Please refresh and retry test."}), 400

            try:
                self.db_handler.save_speed_test(download_speed, upload_speed, ping, current_db_id)
                # print(f"Saved speed test for ID {current_db_id} (Session: {session_id})")
                return jsonify({"message": "Speed test results saved successfully!", "id": current_db_id})
            except Exception as e:
                 print(f"Database error saving speed test results for ID {current_db_id}: {e}")
                 return jsonify({"error": "Failed to save speed test results to database"}), 500

        @self.app.route("/heatmap-data", methods=["GET"])
        def get_heatmap_data():
            """
            Fetches combined location and speed data, maps coordinates using corrected rotated logic,
            and returns data formatted for heatmap.js.
            """
            try:
                combined_data = self.db_handler.get_data() # Fetch data
                heatmap_points = []
                max_speed = 0 # Keep track of max speed for heatmap scaling
                points_processed = 0
                points_mapped = 0

                for unique_id, info in combined_data.items():
                    points_processed += 1
                    # Ensure both location and speed data exist for this ID
                    if info.get('location') and info.get('download') is not None:
                        lat = info['location']['latitude']
                        lon = info['location']['longitude']
                        speed = info['download'] # Using download speed for heatmap value

                        # Calls the CORRECTED ROTATED mapping function defined above
                        x_pixel, y_pixel = map_lat_lon_to_pixels(lat, lon)

                        # Only add point if mapping was successful
                        if x_pixel is not None and y_pixel is not None:
                            points_mapped += 1
                            heatmap_points.append({
                                "x": x_pixel,
                                "y": y_pixel,
                                "value": speed
                            })
                            if speed > max_speed:
                                max_speed = speed # Update max value

                print(f"DEBUG HEATMAP DATA: Processed {points_processed} total entries. Mapped {points_mapped} points successfully.") # Summary Debug Print

                # Return data in the format heatmap.js expects
                return jsonify({
                    "max": max_speed if max_speed > 0 else 100, # Use calculated max or a default
                    "data": heatmap_points
                })
            except Exception as e:
                print(f"Error generating heatmap data: {e}")
                return jsonify({"error": "Failed to generate heatmap data"}), 500

        # --- Routes for debugging/displaying session info ---
        @self.app.route("/get_all_sessions", methods=["GET"])
        def get_all_sessions_route():
            with self.session_lock:
                active_sessions = {}
                for sid, session_data in self.user_sessions.items():
                    if session_data and len(session_data) == 3:
                         last_seen_ts = session_data[2]
                         active_sessions[sid] = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(last_seen_ts))
                    else:
                         active_sessions[sid] = "Timestamp data missing or invalid"
                return jsonify(active_sessions)

        @self.app.route("/get_location/<session_id>", methods=["GET"])
        def get_location_route(session_id):
            with self.session_lock:
                session_data = self.user_sessions.get(session_id)
                if session_data and len(session_data) == 3:
                    lat, lon, last_seen_ts = session_data
                    return jsonify({
                        "latitude": lat,
                        "longitude": lon,
                        "last_seen": time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(last_seen_ts))
                        })
                return jsonify({"error": "Session ID not found or data invalid"}), 404

    # --- Helper Methods ---
    def get_user_session_location(self, session_id):
        """Gets location tuple (lat, lon) for a given session_id."""
        with self.session_lock:
            session_data = self.user_sessions.get(session_id)
            if session_data and len(session_data) == 3:
                lat, lon, _ = session_data
                return (lat, lon)
            return (None, None)

    def get_all_sessions(self):
        """Gets a list of all currently tracked session IDs."""
        with self.session_lock:
            return list(self.user_sessions.keys())

    def cleanup_inactive_sessions(self, timeout_seconds):
        """Removes sessions inactive for longer than timeout_seconds."""
        current_time = time.time()
        inactive_session_ids = []
        # print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Running session cleanup (Timeout: {timeout_seconds}s)...") # Optional: uncomment for verbose logging
        with self.session_lock:
            session_ids_to_check = list(self.user_sessions.keys())
            # print(f"Checking {len(session_ids_to_check)} sessions...") # Optional: uncomment for verbose logging
            for session_id in session_ids_to_check:
                session_data = self.user_sessions.get(session_id)
                if session_data and len(session_data) == 3:
                    last_seen = session_data[2]
                    if (current_time - last_seen) > timeout_seconds:
                        inactive_session_ids.append(session_id)
                else:
                    # print(f"Warning: Session {session_id} found with invalid data format. Marking for removal.") # Optional: uncomment for verbose logging
                    inactive_session_ids.append(session_id)

            removed_count = 0
            for session_id in inactive_session_ids:
                if session_id in self.user_sessions:
                    try:
                        del self.user_sessions[session_id]
                        # print(f"Removed inactive session from user_sessions: {session_id}") # Optional: uncomment for verbose logging
                        removed_count += 1
                    except KeyError:
                        pass # Session already removed, ignore.

        removed_from_map = 0
        if inactive_session_ids:
            with self.id_lock:
                 for session_id in inactive_session_ids:
                     if session_id in self.session_ids_to_generated_ids:
                         try:
                            del self.session_ids_to_generated_ids[session_id]
                            # print(f"Removed inactive session from id_map: {session_id}") # Optional: uncomment for verbose logging
                            removed_from_map += 1
                         except KeyError:
                            pass # Session already removed, ignore.

        # print(f"Session cleanup finished. Removed {removed_count} sessions from user_sessions, {removed_from_map} from id_map.") # Optional: uncomment for verbose logging


# --- Function to initialize routes ---
def setup_routes(app):
    """Creates and returns an instance of the Routes class."""
    routes_instance = Routes(app)
    return routes_instance