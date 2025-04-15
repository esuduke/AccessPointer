# Routes.py (Updated to use client dimensions)
from flask import Flask, render_template, request, jsonify
import uuid
import random
from DatabaseHandler import DatabaseHandler # Assuming DatabaseHandler.py is accessible
import threading
import time

# --- Coordinate Mapping Section ---
# Default image dimensions as a fallback (will be overridden by client dimensions)
DEFAULT_IMAGE_WIDTH = 375  # 1500/4 = 375 
DEFAULT_IMAGE_HEIGHT = 300  # 1200/4 = 300

# Bounds derived from user-provided corner coordinates
MIN_LAT = 43.037278
MAX_LAT = 43.037944
MIN_LON = -76.132944
MAX_LON = -76.132194

def map_lat_lon_to_pixels(latitude, longitude, container_width=None, container_height=None):
    """
    Maps geographic coordinates to image pixel coordinates.
    If container_width and container_height are provided, scales the output to those dimensions.
    
    Returns (x, y, is_within_bounds) or (None, None, False) if conversion fails.
    """
    try:
        lat = float(latitude)
        lon = float(longitude)
        epsilon = 1e-9 # Tolerance for float comparison

        # Default dimensions if none provided
        img_width = DEFAULT_IMAGE_WIDTH if container_width is None else container_width
        img_height = DEFAULT_IMAGE_HEIGHT if container_height is None else container_height

        # Determine if the original point is within bounds BEFORE clamping
        is_within_bounds = (MIN_LAT - epsilon <= lat <= MAX_LAT + epsilon and
                            MIN_LON - epsilon <= lon <= MAX_LON + epsilon)

        # Avoid division by zero if bounds are identical
        if abs(MAX_LAT - MIN_LAT) < epsilon or abs(MAX_LON - MIN_LON) < epsilon:
            print(f"DEBUG: Error - MIN/MAX Lat or Lon are too close, cannot map.")
            return None, None, False # Indicate mapping failure

        # First map to [0,1] range based on the geographical bounds
        x_normalized = (MAX_LAT - lat) / (MAX_LAT - MIN_LAT)
        y_normalized = (MAX_LON - lon) / (MAX_LON - MIN_LON)
        
        # Then scale to the provided container dimensions
        x_pixel_float = x_normalized * img_width
        y_pixel_float = y_normalized * img_height

        # Clamp float values to image edges - this finds the 'closest edge' point
        x_pixel_clamped = max(0.0, min(x_pixel_float, float(img_width - 1)))
        y_pixel_clamped = max(0.0, min(y_pixel_float, float(img_height - 1)))

        # Convert clamped values to int
        x_pixel = int(x_pixel_clamped)
        y_pixel = int(y_pixel_clamped)

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
        
        # Store client dimensions for each session
        self.client_dimensions = {} # {session_id: {width: w, height: h, container: {width: cw, height: ch}}}
        self.dimensions_lock = threading.Lock()
        
        self.setup_routes()

    def generate_id(self):
        return random.randint(100000, 999999)

    def setup_routes(self):
        @self.app.route("/")
        def index():
            # Pass default dimensions to the template - will be overridden by client
            return render_template("index.html")

        @self.app.route("/set-client-dimensions", methods=["POST"])
        def set_client_dimensions():
            """Store the client's screen and container dimensions for this session"""
            data = request.json
            if not data:
                return jsonify({"error": "Invalid JSON payload"}), 400
                
            session_id = data.get("session_id")
            dimensions = data.get("dimensions")
            
            if not session_id or not dimensions:
                return jsonify({"error": "Missing session_id or dimensions"}), 400
                
            with self.dimensions_lock:
                self.client_dimensions[session_id] = dimensions
                
            return jsonify({
                "status": "success", 
                "message": "Client dimensions saved",
                "dimensions": dimensions
            })

        @self.app.route("/generate_unique_id", methods=["GET"])
        def generate_id_route():
            session_id = request.args.get("session_id")
            if not session_id: return jsonify({"error": "Missing session_id parameter"}), 400
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
            
            # Store client dimensions if provided
            dimensions = data.get("dimensions")
            if dimensions and session_id:
                with self.dimensions_lock:
                    self.client_dimensions[session_id] = dimensions
            
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
                return jsonify({"error": f"Invalid data format: {e}"}), 400
            except Exception as e: 
                print(f"DB save location error: {e}")
                return jsonify({"error": "Failed to save location"}), 500

        @self.app.route("/save_user_location", methods=["POST"])
        def save_user_location():
            data = request.get_json(silent=True)
            if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400
            
            latitude = data.get("latitude")
            longitude = data.get("longitude")
            session_id = data.get("session_id")
            
            # Store client dimensions if provided
            dimensions = data.get("dimensions")
            if dimensions and session_id:
                with self.dimensions_lock:
                    self.client_dimensions[session_id] = dimensions
            
            if latitude is not None and longitude is not None and session_id is not None:
                try:
                    lat_float = float(latitude)
                    lon_float = float(longitude)
                    current_time = time.time()
                    
                    with self.session_lock:
                        self.user_sessions[session_id] = (lat_float, lon_float, current_time)
                        
                    return jsonify({"status": "User location updated", "session_id": session_id}), 200
                except (TypeError, ValueError):
                    return jsonify({"error": "Invalid lat/lon format"}), 400
            else:
                missing = [f for f in ['latitude','longitude','session_id'] if data.get(f) is None]
                return jsonify({"error": f"Missing fields {missing}"}), 400

        @self.app.route("/submit-speed", methods=["POST"])
        def submit_speed():
            data = request.json
            if not data: return jsonify({"error": "Invalid or empty JSON payload"}), 400
            
            try:
                dl = float(data.get("dlStatus"))
                ul = float(data.get("ulStatus"))
                p = float(data.get("pingStatus"))
            except (TypeError, ValueError, KeyError) as e:
                return jsonify({"error": f"Invalid speed values: {e}"}), 400
                
            session_id = data.get("session_id")
            if not session_id: return jsonify({"error": "Missing session_id"}), 400
            
            with self.id_lock:
                current_db_id = self.session_ids_to_generated_ids.get(session_id)
                
            if current_db_id is None:
                return jsonify({"error": "Associated DB ID not found. Refresh."}), 400
                
            try:
                self.db_handler.save_speed_test(dl, ul, p, current_db_id)
                return jsonify({"message": "Speed test results saved!", "id": current_db_id})
            except Exception as e:
                print(f"DB save speed error for {current_db_id}: {e}")
                return jsonify({"error": "Failed to save speed results"}), 500

        @self.app.route("/heatmap-data", methods=["GET"])
        def get_heatmap_data():
            try:
                # Get session ID to determine container dimensions
                session_id = request.args.get("session_id")
                
                # Get client container dimensions if available
                container_width = DEFAULT_IMAGE_WIDTH
                container_height = DEFAULT_IMAGE_HEIGHT
                
                if session_id:
                    with self.dimensions_lock:
                        client_dims = self.client_dimensions.get(session_id, {})
                        container_dims = client_dims.get("container", {})
                        if container_dims:
                            container_width = container_dims.get("width", DEFAULT_IMAGE_WIDTH)
                            container_height = container_dims.get("height", DEFAULT_IMAGE_HEIGHT)
                
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
                        
                        # Use client dimensions for mapping
                        x_pixel, y_pixel, _ = map_lat_lon_to_pixels(
                            lat, lon, container_width, container_height
                        )
                        
                        if x_pixel is not None and y_pixel is not None:
                            points_mapped += 1
                            heatmap_points.append({
                                "x": x_pixel,
                                "y": y_pixel,
                                "value": speed
                            })
                            if speed > max_speed:
                                max_speed = speed
                
                print(f"DEBUG HEATMAP DATA: Processed {points_processed} entries. Mapped {points_mapped} points.")
                print(f"Using container dimensions: {container_width}x{container_height}")
                
                return jsonify({
                    "max": max_speed if max_speed > 0 else 100, 
                    "data": heatmap_points,
                })
            except Exception as e: 
                print(f"Error generating heatmap data: {e}")
                return jsonify({"error": f"Failed to generate heatmap data: {str(e)}"}), 500

        @self.app.route("/get-live-location/<session_id>", methods=["GET"])
        def get_live_location(session_id):
            """
            Gets the latest location for a session, maps it using client dimensions.
            """
            if not session_id:
                return jsonify({"error": "Missing session_id"}), 400

            with self.session_lock:
                session_data = self.user_sessions.get(session_id)

            if session_data and len(session_data) == 3:
                lat, lon, timestamp = session_data
                
                # Get client container dimensions
                container_width = DEFAULT_IMAGE_WIDTH
                container_height = DEFAULT_IMAGE_HEIGHT
                
                with self.dimensions_lock:
                    client_dims = self.client_dimensions.get(session_id, {})
                    container_dims = client_dims.get("container", {})
                    if container_dims:
                        container_width = container_dims.get("width", DEFAULT_IMAGE_WIDTH)
                        container_height = container_dims.get("height", DEFAULT_IMAGE_HEIGHT)
                
                # Get original coordinates for reference (using default dimensions)
                orig_x, orig_y, is_within_bounds = map_lat_lon_to_pixels(lat, lon)
                
                # Get scaled coordinates for the actual container
                x_pixel, y_pixel, _ = map_lat_lon_to_pixels(
                    lat, lon, container_width, container_height
                )

                if x_pixel is not None and y_pixel is not None:
                    # Return coordinates AND the in_bounds status
                    return jsonify({
                        "x": x_pixel,
                        "y": y_pixel,
                        "orig_x": orig_x,  # Original reference coordinates
                        "orig_y": orig_y,
                        "in_bounds": is_within_bounds,
                        "found": True,
                        "lat": lat,
                        "lon": lon,
                        "container": {
                            "width": container_width,
                            "height": container_height
                        }
                    })
                else:
                    # Original mapping failed (e.g., conversion error)
                    return jsonify({"found": False, "reason": "Mapping failed"})
            else:
                # No location data found for this session yet
                return jsonify({"found": False, "reason": "No data for session"})

        @self.app.route("/get_all_sessions", methods=["GET"])
        def get_all_sessions_route():
             with self.session_lock:
                active_sessions = {
                    sid: time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(sdata[2]))
                    for sid, sdata in self.user_sessions.items() 
                    if sdata and len(sdata) == 3
                }
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
        with self.session_lock:
            session_data = self.user_sessions.get(session_id)
            if session_data and len(session_data) == 3: 
                return (session_data[0], session_data[1])
            return (None, None)

    def get_all_sessions(self):
        with self.session_lock: 
            return list(self.user_sessions.keys())

    def cleanup_inactive_sessions(self, timeout_seconds):
        current_time = time.time()
        inactive_session_ids = [
            sid for sid, sdata in self.user_sessions.items()
            if not sdata or len(sdata) != 3 or (current_time - sdata[2]) > timeout_seconds
        ]
        if inactive_session_ids:
            with self.session_lock:
                for session_id in inactive_session_ids: 
                    self.user_sessions.pop(session_id, None)
            with self.id_lock:
                for session_id in inactive_session_ids: 
                    self.session_ids_to_generated_ids.pop(session_id, None)
            with self.dimensions_lock:
                for session_id in inactive_session_ids:
                    self.client_dimensions.pop(session_id, None)

# --- Function to initialize routes ---
def setup_routes(app):
    routes_instance = Routes(app)
    return routes_instance