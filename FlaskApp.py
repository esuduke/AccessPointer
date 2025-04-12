# FlaskApp.py
import threading
import time # <-- Import time
from flask import Flask
# from Routes import Routes # setup_routes returns the instance now
from Routes import setup_routes # <-- Import setup_routes instead
# from NgrokTunnel import NgrokTunnel # Keep if used
# from EmailSender import EmailSender # Keep if used
from DatabaseHandler import DatabaseHandler
from BackendRoutes import backend_bp

# --- Configuration ---
SESSION_TIMEOUT_SECONDS = 1800 # e.g., 30 minutes
CLEANUP_INTERVAL_SECONDS = 300 # e.g., Check every 5 minutes
# --- End Configuration ---

class FlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
        # self.tunnel = NgrokTunnel() # Keep if used
        # self.sender = EmailSender() # Keep if used
        # Use the setup_routes function which returns the Routes instance
        self.routes_instance = setup_routes(self.app) # <-- Store the Routes instance

    def run_cleanup_loop(self):
        """Periodically cleans up inactive sessions."""
        print("Starting background session cleanup thread...")
        while True:
            time.sleep(CLEANUP_INTERVAL_SECONDS) # Wait before running cleanup
            try:
                # Access the cleanup method via the stored instance
                self.routes_instance.cleanup_inactive_sessions(SESSION_TIMEOUT_SECONDS)
            except Exception as e:
                print(f"Error during session cleanup: {e}") # Log errors

    def run(self):
        port = 8000
        # ... (ngrok/email code if used) ...

        self.app.register_blueprint(backend_bp)

        # --- Start Cleanup Thread ---
        cleanup_thread = threading.Thread(target=self.run_cleanup_loop, daemon=True)
        cleanup_thread.start()
        # --- End Start Cleanup Thread ---

        print(f" * Flask app starting on port {port}")
        # Make sure cert.pem and key.pem exist or remove ssl_context for HTTP
        try:
            self.app.run(host='0.0.0.0', port=port, ssl_context=('cert.pem', 'key.pem')) # Commented out SSL for now
        except FileNotFoundError:
             print("\n*** Warning: cert.pem or key.pem not found. Running without HTTPS. ***\n")
             self.app.run(host='0.0.0.0', port=port)


    def listen_for_input(self):
        # This function now needs access to the routes_instance
        while True:
            user_input = input("Press 1 to print current data, Press 2 to print current location for a user: ")
            if user_input == '1':
                DatabaseHandler().print_data() # Assumes DB handler is okay to re-initialize

            elif user_input == '2':
                # Access methods via the stored instance
                session_ids = self.routes_instance.get_all_sessions()
                if not session_ids:
                    print("No active users being tracked.") # Updated message
                    continue

                print("\nTracked User Sessions:") # Updated message
                for i, sid in enumerate(session_ids):
                    print(f"{i + 1}. {sid}")

                try:
                    choice = int(input("Enter the number of the session to view: "))
                    if 1 <= choice <= len(session_ids):
                        selected_sid = session_ids[choice - 1]
                    else:
                        print("Invalid selection.")
                        continue
                except ValueError:
                    print("Invalid input. Please enter a number.")
                    continue

                # Access method via the stored instance
                lat, long = self.routes_instance.get_user_session_location(selected_sid)

                if lat is not None and long is not None:
                     # Get timestamp too for display if desired
                     with self.routes_instance.session_lock:
                          _, last_seen = self.routes_instance.user_sessions.get(selected_sid, ((None, None), 0))
                     last_seen_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen)) if last_seen else "N/A"
                     print(f"Session {selected_sid} -> Latitude: {lat}, Longitude: {long} (Last seen: {last_seen_str})")
                else:
                    # This might mean the session exists but has no location yet, or was cleaned up between get_all_sessions and get_user_session_location
                     print(f"No location data currently available or session inactive for {selected_sid}")
            else:
                print("Invalid input")


if __name__ == "__main__":
    flask_app = FlaskApp()

    # Start input listener in separate thread
    # Pass the flask_app instance if listen_for_input becomes a method
    input_thread = threading.Thread(target=flask_app.listen_for_input)
    input_thread.daemon = True
    input_thread.start()

    # Start Flask (which now also starts the cleanup thread)
    flask_app.run() # Run Flask in the main thread

    # Keep main thread alive (no longer needed if Flask runs in main thread)
    # while True:
    #     time.sleep(1) # Keep alive