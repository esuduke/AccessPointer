# Routes.py
# Defines the main Flask routes for the application, including HTML rendering,
# data submission (location, speed test), heatmap data retrieval, and live location tracking.
# Also includes coordinate mapping logic and session management.

from flask import Flask, render_template, request, jsonify
import uuid # Used for generating session IDs (though frontend uses crypto.randomUUID).
import random # Used for generating unique test IDs.
from DatabaseHandler import DatabaseHandler # Interface for database operations.
import threading # Used for locks to protect shared data structures.
import time # Used for timestamps and session timeout checks.

# --- Coordinate Mapping Configuration ---
# Dimensions of the floor plan image used for mapping (in pixels).
# These should match the actual dimensions of the static/Floor1.png image.
IMAGE_WIDTH = 1003
IMAGE_HEIGHT = 800

# Geographic boundaries (latitude/longitude) corresponding to the
# corners or extent of the floor plan image. These values are crucial
# for accurate mapping. Adjust these based on the actual area covered.
# Example bounds (replace with actual values for Floor1.png):
MIN_LAT = 43.037278 # Southernmost latitude boundary
MAX_LAT = 43.037944 # Northernmost latitude boundary
MIN_LON = -76.132944 # Westernmost longitude boundary
MAX_LON = -76.132194 # Easternmost longitude boundary

# --- Coordinate Mapping Function ---

def map_lat_lon_to_pixels(latitude: float, longitude: float) -> tuple[int | None, int | None, bool]:
    """
    Maps geographic coordinates (latitude, longitude) to image pixel coordinates (x, y).
    Assumes a linear mapping between the geographic boundaries and image dimensions.
    Handles coordinates outside the defined bounds by clamping them to the image edges.
    Indicates whether the original point was within the defined geographic bounds.

    IMPORTANT: Assumes the floor plan image orientation requires specific mapping logic
               (e.g., West corresponds to the bottom, North to the left). Adjust the
               calculation formulas (`x_pixel_float`, `y_pixel_float`) if the image
               orientation or desired mapping differs.

    Args:
        latitude: The latitude of the point.
        longitude: The longitude of the point.

    Returns:
        A tuple containing:
        - x (int | None): The calculated x pixel coordinate (clamped), or None if mapping fails.
        - y (int | None): The calculated y pixel coordinate (clamped), or None if mapping fails.
        - is_within_bounds (bool): True if the original (lat, lon) was within the
                                   defined MIN/MAX boundaries, False otherwise or if mapping fails.
    """
    # Try converting input coordinates to float.
    try:
        lat = float(latitude)
        lon = float(longitude)
        # Define a small tolerance for floating-point comparisons.
        epsilon = 1e-9

        # Check if the original point is within the defined geographic bounds.
        # Compare using epsilon for float precision issues.
        is_within_bounds = (
            (MIN_LAT - epsilon <= lat <= MAX_LAT + epsilon) and
            (MIN_LON - epsilon <= lon <= MAX_LON + epsilon)
        )

        # Prevent division by zero if latitude or longitude bounds are identical.
        if abs(MAX_LAT - MIN_LAT) < epsilon or abs(MAX_LON - MIN_LON) < epsilon:
            print(f"DEBUG: Error - MIN/MAX Lat or Lon bounds are too close, cannot map.")
            return None, None, False # Indicate mapping failure.

        # --- Mapping Calculation ---
        # These formulas map lat/lon to x/y pixels based on the assumed image orientation.
        # Adjust these formulas if your image orientation or mapping logic differs.
        # Example: Higher latitude (North) maps to lower X pixel value (Left).
        # Example: Higher longitude (East) maps to lower Y pixel value (Top).
        x_pixel_float = ((MAX_LAT - lat) / (MAX_LAT - MIN_LAT)) * IMAGE_WIDTH
        y_pixel_float = ((MAX_LON - lon) / (MAX_LON - MIN_LON)) * IMAGE_HEIGHT
        # --- End Mapping Calculation ---

        # Clamp the calculated pixel values to stay within the image dimensions (0 to width/height - 1).
        # This ensures points outside the bounds are mapped to the nearest edge.
        x_pixel_clamped = max(0.0, min(x_pixel_float, float(IMAGE_WIDTH - 1)))
        y_pixel_clamped = max(0.0, min(y_pixel_float, float(IMAGE_HEIGHT - 1)))

        # Convert the clamped floating-point pixel coordinates to integers.
        x_pixel = int(x_pixel_clamped)
        y_pixel = int(y_pixel_clamped)

        # Return the clamped pixel coordinates and the original in-bounds status.
        return x_pixel, y_pixel, is_within_bounds

    # Handle errors during float conversion (e.g., non-numeric input).
    except (ValueError, TypeError) as e:
        print(f"DEBUG: Error converting lat/lon ({latitude}, {longitude}) to float: {e}")
        return None, None, False # Indicate mapping failure.

# --- End Coordinate Mapping Section ---


class Routes:
    """
    Manages Flask routes, data handling, and session tracking for the application.
    Uses DatabaseHandler for persistence and maintains in-memory session data.
    """
    def __init__(self, app: Flask):
        """
        Initializes the Routes class.
        Args:
            app: The Flask application instance.
        """
        self.app = app
        # Instantiate the database handler for database interactions.
        self.db_handler = DatabaseHandler()
        # Dictionary to map session IDs (from frontend) to unique test IDs generated per test run.
        self.session_ids_to_generated_ids = {}
        # Lock to protect access to session_ids_to_generated_ids dictionary from concurrent requests.
        self.id_lock = threading.Lock()
        # Dictionary to store live user session data: {session_id: (latitude, longitude, timestamp)}.
        self.user_sessions = {}
        # Lock to protect access to user_sessions dictionary from concurrent requests/threads.
        self.session_lock = threading.Lock()
        # Call the method to define and register Flask routes.
        self.setup_routes()

    def _generate_unique_test_id(self) -> int:
        """Generates a random integer ID for associating a speed test with a location."""
        # Generate a random 6-digit integer.
        return random.randint(100000, 999999)

    def setup_routes(self):
        """Defines and registers all Flask routes for the application."""

        @self.app.route("/")
        def index():
            """
            GET /
            Renders the main HTML page (index.html).
            Passes image dimensions to the template for potential use in frontend logic.
            """
            # Render the main template, passing image dimensions.
            return render_template("index.html", image_width=IMAGE_WIDTH, image_height=IMAGE_HEIGHT)

        @self.app.route("/generate_unique_id", methods=["GET"])
        def generate_id_route():
            """
            GET /generate_unique_id?session_id=<session_id>
            Generates a unique ID for a new speed test run associated with a frontend session.
            Stores the mapping between session ID and the new test ID.
            Requires 'session_id' query parameter.
            """
            # Get session ID from query parameters.
            session_id = request.args.get("session_id")
            # Validate that session_id is provided.
            if not session_id:
                return jsonify({"error": "Missing session_id parameter"}), 400

            # Acquire lock before accessing shared dictionary.
            with self.id_lock:
                # Generate a new unique test ID.
                new_id = self._generate_unique_test_id()
                # Store the mapping (overwrites if session_id already exists).
                # Consider alternative logic if overwriting is not desired.
                self.session_ids_to_generated_ids[session_id] = new_id
            # Return the newly generated ID.
            return jsonify({"id": new_id}), 200

        @self.app.route("/save_location", methods=["POST"])
        def save_location():
            """
            POST /save_location
            Receives and saves location data associated with a specific speed test run.
            Expects JSON payload: {"latitude": float, "longitude": float, "session_id": str, "id": int}
            Uses the 'id' (unique test ID) to link location to speed results in the database.
            """
            # Get JSON data from the request body.
            data = request.json
            # Validate JSON payload.
            if not data:
                return jsonify({"error": "Invalid or missing JSON payload"}), 400

            # Extract data fields from JSON.
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id") # Frontend session ID (optional here, but good practice).
            unique_test_id = data.get("id") # The ID generated by /generate_unique_id.

            # Validate required fields for saving.
            if unique_test_id is None:
                return jsonify({"error": "Missing unique test id ('id')"}), 400
            if latitude is None or longitude is None:
                return jsonify({"error": "Missing latitude or longitude"}), 400
            # Optional: Validate session_id presence if needed for cross-referencing.
            # if not session_id: return jsonify({"error": "Missing session_id"}), 400

            # Attempt to convert data and save to database.
            try:
                # Convert to appropriate types.
                lat_float = float(latitude)
                lon_float = float(longitude)
                unique_id_int = int(unique_test_id)
                # Call database handler to save the location.
                self.db_handler.save_location(lat_float, lon_float, unique_id_int)
                # Return success response.
                return jsonify({"message": "Location saved successfully!", "id": unique_id_int}), 200
            # Handle errors during data conversion.
            except (ValueError, TypeError) as e:
                return jsonify({"error": f"Invalid data format (lat/lon/id): {e}"}), 400
            # Handle potential database errors.
            except Exception as e:
                print(f"DB save location error: {e}")
                return jsonify({"error": "Internal server error saving location"}), 500

        @self.app.route("/save_user_location", methods=["POST"])
        def save_user_location():
            """
            POST /save_user_location
            Receives and updates the latest known location for a specific user session (live tracking).
            Expects JSON payload: {"latitude": float, "longitude": float, "session_id": str}
            Stores this data in the in-memory `user_sessions` dictionary.
            """
            # Get JSON data, handle potential non-JSON request gracefully.
            data = request.get_json(silent=True)
            # Validate JSON payload.
            if not data:
                return jsonify({"error": "Invalid or empty JSON payload"}), 400

            # Extract required fields.
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id")

            # Validate that all required fields are present.
            if latitude is not None and longitude is not None and session_id is not None:
                # Attempt to convert location data and update session state.
                try:
                    # Convert coordinates to float.
                    lat_float = float(latitude)
                    lon_float = float(longitude)
                    # Get current time for timestamp.
                    current_time = time.time()
                    # Acquire lock before modifying shared session dictionary.
                    with self.session_lock:
                        # Update or add the session entry with new location and timestamp.
                        self.user_sessions[session_id] = (lat_float, lon_float, current_time)
                    # Return success response.
                    return jsonify({"status": "User location updated", "session_id": session_id}), 200
                # Handle errors during float conversion.
                except (TypeError, ValueError):
                    return jsonify({"error": "Invalid latitude/longitude format"}), 400
            else:
                # Identify and report missing fields.
                missing_fields = [f for f in ['latitude', 'longitude', 'session_id'] if data.get(f) is None]
                return jsonify({"error": f"Missing required fields: {', '.join(missing_fields)}"}), 400

        @self.app.route("/submit-speed", methods=["POST"])
        def submit_speed():
            """
            POST /submit-speed
            Receives and saves speed test results (download, upload, ping).
            Expects JSON payload containing speed metrics and 'session_id'.
            Retrieves the corresponding unique test ID using the session_id and saves
            the speed results linked to that test ID in the database.
            """
            # Get JSON data from the request.
            data = request.json
            # Validate JSON payload.
            if not data:
                return jsonify({"error": "Invalid or empty JSON payload"}), 400

            # Extract session ID.
            session_id = data.get("session_id")
            # Validate session ID presence.
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400

            # Extract and parse speed values robustly.
            # Default to "0" string if keys are missing.
            dl_str = data.get("dlStatus", "0")
            ul_str = data.get("ulStatus", "0")
            p_str = data.get("pingStatus", "0")
            # Convert "Fail" to 0.0, otherwise parse as float.
            try:
                dl_speed = 0.0 if dl_str == "Fail" else float(dl_str)
                ul_speed = 0.0 if ul_str == "Fail" else float(ul_str)
                ping_time = 0.0 if p_str == "Fail" else float(p_str)
            # Handle conversion errors (e.g., invalid numeric strings).
            except (TypeError, ValueError) as e:
                print(f"Warning: Error parsing speed values: {e}. Data received: {data}")
                # Default to 0.0 on error, could alternatively return 400 error.
                dl_speed, ul_speed, ping_time = 0.0, 0.0, 0.0
                # Optional: return jsonify({"error": "Invalid speed value format."}), 400

            # Retrieve the unique test ID associated with this session ID.
            # Acquire lock for thread safety.
            with self.id_lock:
                current_test_id = self.session_ids_to_generated_ids.get(session_id)

            # Check if a test ID was found for this session (i.e., /generate_unique_id was called).
            if current_test_id is None:
                return jsonify({"error": "No test ID found for this session. Please run a test first or refresh."}), 400

            # Attempt to save speed test results to the database.
            try:
                # Call database handler with extracted values and the test ID.
                self.db_handler.save_speed_test(dl_speed, ul_speed, ping_time, current_test_id)
                # Return success response.
                return jsonify({"message": "Speed test results saved!", "id": current_test_id}), 200
            # Handle potential database errors.
            except Exception as e:
                print(f"DB save speed error for ID {current_test_id}: {e}")
                return jsonify({"error": "Internal server error saving speed results"}), 500

        @self.app.route("/heatmap-data", methods=["GET"])
        def get_heatmap_data():
            """
            GET /heatmap-data
            Retrieves all combined location and speed test data from the database.
            Maps latitude/longitude to pixel coordinates for each data point.
            Returns JSON suitable for the heatmap.js library: {"max": float, "data": list[dict]}
            where 'max' is the maximum download speed and 'data' is a list of
            points { "x": int, "y": int, "value": float (download speed) }.
            """
            try:
                # Fetch combined data from the database handler.
                combined_data = self.db_handler.get_data()
                heatmap_points = []
                max_speed = 0.0 # Use float for max speed calculation.
                points_processed = 0
                points_mapped = 0

                # Iterate through each test entry in the combined data.
                for unique_id, info in combined_data.items():
                    points_processed += 1
                    # Safely extract download speed, default to 0.0 if missing or invalid.
                    speed = 0.0
                    try:
                        dl_value = info.get('download')
                        # Ensure value exists and is not None before converting.
                        if dl_value is not None:
                            speed = float(dl_value)
                    except (ValueError, TypeError):
                        # Log warning if conversion fails, use default.
                        print(f"Warning: Could not convert download speed '{info.get('download')}' for ID {unique_id} to float. Using 0.")
                        speed = 0.0

                    # Check if location data exists for this entry.
                    if info.get('location'):
                        lat = info['location'].get('latitude')
                        lon = info['location'].get('longitude')
                        # Map geographic coordinates to pixel coordinates.
                        x_pixel, y_pixel, _ = map_lat_lon_to_pixels(lat, lon)
                        # If mapping was successful, add point to heatmap data.
                        if x_pixel is not None and y_pixel is not None:
                            points_mapped += 1
                            heatmap_points.append({"x": x_pixel, "y": y_pixel, "value": speed})
                            # Update maximum speed found so far.
                            if speed > max_speed:
                                max_speed = speed

                # Determine the 'max' value to send to heatmap.js.
                # Ensure max is at least 1.0 if points exist but max speed is 0 or less.
                # Default to 1.0 if no points were mapped.
                if points_mapped > 0 and max_speed <= 0:
                    max_value_for_heatmap = 1.0
                elif points_mapped == 0:
                    max_value_for_heatmap = 1.0
                else:
                    max_value_for_heatmap = max_speed

                # Return the heatmap data in the expected format.
                return jsonify({"max": max_value_for_heatmap, "data": heatmap_points}), 200
            # Handle potential errors during data fetching or processing.
            except Exception as e:
                print(f"Error generating heatmap data: {e}")
                return jsonify({"error": "Failed to generate heatmap data"}), 500

        @self.app.route("/get-live-location/<session_id>", methods=["GET"])
        def get_live_location(session_id: str):
            """
            GET /get-live-location/<session_id>
            Retrieves the latest known location for the given session ID from memory.
            Maps the location to pixel coordinates.
            Returns JSON: {"x": int, "y": int, "in_bounds": bool, "found": bool}
            or {"found": False, "reason": str} if no data or mapping fails.
            """
            # Validate session ID parameter.
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400

            # Acquire lock to safely access shared session data.
            with self.session_lock:
                # Retrieve session data (lat, lon, timestamp) for the given ID.
                session_data = self.user_sessions.get(session_id)

            # Check if valid session data was found.
            if session_data and isinstance(session_data, tuple) and len(session_data) == 3:
                lat, lon, timestamp = session_data
                # Map the geographic coordinates to pixel coordinates.
                x_pixel, y_pixel, is_within_bounds = map_lat_lon_to_pixels(lat, lon)

                # Check if mapping was successful.
                if x_pixel is not None and y_pixel is not None:
                    # Return mapped coordinates and bounds status.
                    return jsonify({
                        "x": x_pixel,
                        "y": y_pixel,
                        "in_bounds": is_within_bounds,
                        "found": True
                    }), 200
                else:
                    # Indicate mapping failure.
                    return jsonify({"found": False, "reason": "Coordinate mapping failed"}), 200 # Return 200 OK, but indicate not found via payload
            else:
                # Indicate no recent data found for the session.
                return jsonify({"found": False, "reason": "No recent data for session"}), 200 # Return 200 OK, indicate not found

        @self.app.route("/get_all_sessions", methods=["GET"])
        def get_all_sessions_route():
            """
            GET /get_all_sessions
            (Primarily for debugging/admin)
            Returns a JSON object listing all currently tracked user sessions and their last seen timestamp.
            """
            # Acquire lock for safe access to shared session data.
            with self.session_lock:
                # Create a dictionary comprehension to format session data.
                # Filters out potentially malformed entries as a safeguard.
                active_sessions = {
                    sid: time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(sdata[2]))
                    for sid, sdata in self.user_sessions.items()
                    # Basic validation of session data format.
                    if isinstance(sdata, tuple) and len(sdata) == 3 and isinstance(sdata[2], (int, float))
                }
                # Return the dictionary as JSON.
                return jsonify(active_sessions), 200

        @self.app.route("/get_location/<session_id>", methods=["GET"])
        def get_location_route(session_id: str):
            """
            GET /get_location/<session_id>
            (Primarily for debugging/admin)
            Returns the raw latitude, longitude, and last seen timestamp for a specific session ID.
            """
            # Acquire lock for safe access.
            with self.session_lock:
                # Retrieve session data.
                session_data = self.user_sessions.get(session_id)
                # Validate session data format.
                if session_data and isinstance(session_data, tuple) and len(session_data) == 3:
                    lat, lon, last_seen_ts = session_data
                    # Format timestamp safely.
                    try:
                        last_seen_str = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(last_seen_ts))
                    except (ValueError, TypeError):
                        last_seen_str = "Invalid timestamp"
                    # Return location and timestamp.
                    return jsonify({"latitude": lat, "longitude": lon, "last_seen": last_seen_str}), 200
                # Return error if session not found or data is invalid.
                return jsonify({"error": "Session ID not found or data invalid"}), 404

    # --- Helper Methods (accessible by FlaskApp instance) ---

    def get_user_session_location(self, session_id: str) -> tuple[float | None, float | None]:
        """
        Retrieves the latest latitude and longitude for a given session ID.
        Used by the console input listener in FlaskApp.py.
        Args:
            session_id: The session ID to look up.
        Returns:
            A tuple (latitude, longitude), or (None, None) if not found or invalid.
        """
        # Acquire lock for safe access.
        with self.session_lock:
            # Retrieve session data.
            session_data = self.user_sessions.get(session_id)
            # Validate data format (tuple of 3 elements).
            if session_data and isinstance(session_data, tuple) and len(session_data) == 3:
                # Further validate that lat/lon are likely numeric before returning.
                try:
                    lat = float(session_data[0])
                    lon = float(session_data[1])
                    return lat, lon
                except (ValueError, TypeError):
                    # Log warning if conversion fails.
                    print(f"Warning: Invalid lat/lon format in session data for {session_id}")
                    return None, None
            # Return None if session not found or format is wrong.
            return None, None

    def get_all_sessions(self) -> list[str]:
        """
        Returns a list of all currently active session IDs.
        Used by the console input listener in FlaskApp.py.
        Returns:
            A list of session ID strings.
        """
        # Acquire lock for safe access.
        with self.session_lock:
            # Return a list of keys from the user_sessions dictionary.
            return list(self.user_sessions.keys())

    def cleanup_inactive_sessions(self, timeout_seconds: int):
        """
        Removes sessions from `user_sessions` and `session_ids_to_generated_ids`
        that haven't been updated within the specified timeout period.
        Called periodically by the background cleanup thread in FlaskApp.py.
        Args:
            timeout_seconds: The maximum inactivity time allowed before cleanup.
        """
        # Get the current time.
        current_time = time.time()
        inactive_session_ids = []

        # --- Identify Inactive/Invalid Sessions ---
        # Acquire lock to safely read session keys. Operate on a copy to avoid issues
        # if the dictionary changes during iteration (though less likely with lock).
        with self.session_lock:
            all_session_ids = list(self.user_sessions.keys())

        # Iterate through the copied list of session IDs.
        for session_id in all_session_ids:
            # Re-acquire lock to safely access the data for the current session ID.
            with self.session_lock:
                sdata = self.user_sessions.get(session_id)

            # Check if data exists and matches the expected format (tuple, 3 elements, valid timestamp).
            if not (sdata and isinstance(sdata, tuple) and len(sdata) == 3 and isinstance(sdata[2], (int, float))):
                # Mark sessions with invalid format for cleanup.
                inactive_session_ids.append(session_id)
                print(f"Marking session {session_id} for cleanup due to invalid format.")
            # Check if the session has timed out based on its last timestamp.
            elif (current_time - sdata[2]) > timeout_seconds:
                # Mark timed-out sessions for cleanup.
                inactive_session_ids.append(session_id)

        # --- Perform Cleanup ---
        # Proceed only if there are sessions marked for cleanup.
        if inactive_session_ids:
            print(f"Cleaning up inactive/invalid sessions: {inactive_session_ids}")
            # Acquire lock to safely modify the user_sessions dictionary.
            with self.session_lock:
                # Remove each inactive session. Use pop with default None for safety.
                for session_id in inactive_session_ids:
                    self.user_sessions.pop(session_id, None)
            # Acquire lock to safely modify the ID mapping dictionary.
            with self.id_lock:
                # Remove the corresponding generated ID mapping for cleaned-up sessions.
                for session_id in inactive_session_ids:
                    self.session_ids_to_generated_ids.pop(session_id, None)

            # Log remaining sessions after cleanup (acquire lock for consistency).
            with self.session_lock:
                remaining_sessions = list(self.user_sessions.keys())
            print(f"Cleanup complete. Remaining active sessions: {remaining_sessions}")
        # else:
            # Optional: Log if no sessions needed cleanup.
            # print("Cleanup check complete. No inactive sessions found.")


# --- Factory Function ---
# This function is used by FlaskApp.py to initialize the routes.
def setup_routes(app: Flask) -> Routes:
    """
    Initializes the Routes class with the Flask app instance.
    Args:
        app: The Flask application instance.
    Returns:
        An instance of the Routes class.
    """
    # Create an instance of the Routes class, passing the Flask app.
    routes_instance = Routes(app)
    # Return the instance (so FlaskApp can hold a reference to it).
    return routes_instance