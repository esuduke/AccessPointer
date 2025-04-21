# FlaskApp.py
# Main application file for the Flask web server.
# Sets up Flask, configures logging, registers blueprints, and runs the app.
# Includes background threads for session cleanup and user input handling.

import threading
import time # Used for timestamps and sleeping.
import logging # Used for configuring log output.
import re # Used for regular expressions in log filtering.
from flask import Flask

# Import blueprints and setup functions from other modules.
from Routes import setup_routes # Function to set up main application routes.
from DatabaseHandler import DatabaseHandler # Used in input listener.
from BackendRoutes import backend_bp # Blueprint for backend API routes.

# --- Configuration Constants ---
# Session timeout duration in seconds (e.g., 30 minutes).
SESSION_TIMEOUT_SECONDS = 1800
# Interval for checking and cleaning up inactive sessions (e.g., 5 minutes).
CLEANUP_INTERVAL_SECONDS = 300
# Default port for the Flask application.
DEFAULT_PORT = 8000
# Paths to SSL certificate and key files (if using HTTPS).
SSL_CERT_FILE = 'cert.pem'
SSL_KEY_FILE = 'key.pem'
# --- End Configuration Constants ---

# --- Logging Configuration ---

class RequestPathFilter(logging.Filter):
    """
    A custom logging filter to prevent logging requests for specific URL paths.
    Useful for filtering out frequent, less important requests like polling endpoints.
    """
    def __init__(self, paths_to_block=None, *args, **kwargs):
        """
        Initializes the filter.
        Args:
            paths_to_block: A list of base URL paths to block (e.g., ['/get-live-location']).
        """
        super().__init__(*args, **kwargs)
        # Ensure paths start with '/' for consistent matching.
        self.paths_to_block = [p if p.startswith('/') else f'/{p}' for p in (paths_to_block or [])]
        # Regex to capture HTTP method and path from standard Werkzeug log format.
        # Example log: "GET /some/path HTTP/1.1" 200 -
        self.log_pattern = re.compile(r'\"(GET|POST|PUT|DELETE|HEAD|OPTIONS)\s+([^?\s]+).*?\"')

    def filter(self, record):
        """
        Determines whether to allow or block a log record based on its path.
        Returns:
            False if the log record should be blocked, True otherwise.
        """
        # Get the formatted log message.
        log_message = record.getMessage()
        # Search for the request pattern in the message.
        match = self.log_pattern.search(log_message)

        # If the log message matches the request pattern:
        if match:
            # Extract the request path (e.g., /get-live-location/some-id).
            # The method (GET, POST) is in match.group(1), but not used for filtering here.
            path = match.group(2)

            # Check if the extracted path starts with any of the paths designated for blocking.
            for blocked_path_prefix in self.paths_to_block:
                # Handle exact matches (e.g., /save_location) and prefix matches (e.g., /get-live-location/*).
                if path == blocked_path_prefix or path.startswith(blocked_path_prefix + '/'):
                    # Block this log record.
                    return False

        # If it's not a request log or doesn't match a blocked path, allow it.
        return True

def configure_logging(app: Flask, paths_to_block: list):
    """
    Configures the Werkzeug logger to use the custom RequestPathFilter.
    Removes default handlers and adds a new one with the filter applied.
    Args:
        app: The Flask application instance.
        paths_to_block: List of URL paths to filter out from logs.
    """
    # Get the logger used by Werkzeug (Flask's development server).
    werkzeug_logger = logging.getLogger('werkzeug')
    # Prevent logs from propagating to the root logger if other handlers are configured there.
    werkzeug_logger.propagate = False
    # Set the desired logging level (e.g., INFO, WARNING, ERROR).
    werkzeug_logger.setLevel(logging.INFO)

    # Remove any existing handlers attached to this logger to avoid duplicate logs.
    # Caution: This might remove other custom handlers if they exist.
    for handler in werkzeug_logger.handlers[:]:
        werkzeug_logger.removeHandler(handler)

    # Create a handler to output logs to the console (stderr).
    console_handler = logging.StreamHandler()
    # Optional: Set a specific format for log messages.
    # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # console_handler.setFormatter(formatter)

    # Add the custom filter to the console handler.
    console_handler.addFilter(RequestPathFilter(paths_to_block))
    # Add the configured handler to the Werkzeug logger.
    werkzeug_logger.addHandler(console_handler)

    # Optional: Configure Flask's default logger (app.logger) if needed.
    # Usually less verbose than Werkzeug's logger.
    # app.logger.setLevel(logging.INFO)

# --- End Logging Configuration ---


class FlaskApp:
    """
    Main class to encapsulate the Flask application setup and execution.
    Initializes Flask, configures logging, sets up routes, and manages background threads.
    """
    def __init__(self):
        """Initializes the Flask application and its components."""
        # Create the Flask app instance.
        self.app = Flask(__name__)

        # Configure logging before routes are set up or the app runs.
        # Specify paths to exclude from Werkzeug's request logs.
        configure_logging(self.app, [
            '/save_user_location', # Frequent background update.
            '/get-live-location', # Frequent polling endpoint.
            '/backend/garbage',   # High-volume data transfer.
            '/backend/empty'      # Frequent ping/upload endpoint.
        ])

        # Initialize helper classes (uncomment if used).
        # self.tunnel = NgrokTunnel() # For exposing local server via ngrok.
        # self.sender = EmailSender() # For sending emails.

        # Set up application routes using the function from Routes.py.
        # Store the returned Routes instance to access its methods later (e.g., for cleanup).
        self.routes_instance = setup_routes(self.app)

        # Register the blueprint for backend API routes.
        self.app.register_blueprint(backend_bp)

    def run_cleanup_loop(self):
        """
        Runs in a background thread to periodically clean up inactive user sessions.
        Uses the `cleanup_inactive_sessions` method of the `Routes` instance.
        """
        print("Starting background session cleanup thread...")
        # Loop indefinitely.
        while True:
            # Wait for the specified interval before running cleanup.
            time.sleep(CLEANUP_INTERVAL_SECONDS)
            # Log the start of a cleanup cycle.
            print(f"Running periodic cleanup ({CLEANUP_INTERVAL_SECONDS}s interval)...")
            try:
                # Call the cleanup method from the Routes instance, passing the timeout.
                self.routes_instance.cleanup_inactive_sessions(SESSION_TIMEOUT_SECONDS)
            except Exception as e:
                # Log any errors encountered during cleanup.
                print(f"Error during session cleanup: {e}")

    def run(self, port=DEFAULT_PORT):
        """
        Starts the Flask development server and the background cleanup thread.
        Args:
            port: The port number to run the server on. Defaults to DEFAULT_PORT.
        """
        # --- Start Background Cleanup Thread ---
        # Create a daemon thread for the cleanup loop. Daemon threads exit when the main program exits.
        cleanup_thread = threading.Thread(target=self.run_cleanup_loop, daemon=True)
        # Start the cleanup thread.
        cleanup_thread.start()
        # --- End Start Cleanup Thread ---

        # Print startup message.
        print(f" * Flask app starting on port {port}")

        # Attempt to run with HTTPS using provided certificate and key files.
        try:
            # Note: Running with debug=True might interfere with custom logging.
            # Set debug=False for production or when testing logging filters accurately.
            self.app.run(host='0.0.0.0', port=port, ssl_context=(SSL_CERT_FILE, SSL_KEY_FILE), debug=False)
        # Handle case where SSL files are not found.
        except FileNotFoundError:
            print(f"\n*** Warning: {SSL_CERT_FILE} or {SSL_KEY_FILE} not found. Running without HTTPS. ***\n")
            # Run without HTTPS if certificate/key files are missing.
            self.app.run(host='0.0.0.0', port=port, debug=False)
        # Handle other potential errors during startup.
        except Exception as e:
            print(f"\n*** Error starting Flask app: {e} ***\n")

    def listen_for_input(self):
        """
        Runs in a background thread to listen for user input in the console.
        Allows interacting with the running application (e.g., printing data).
        Requires access to the `routes_instance`.
        """
        # Loop indefinitely to wait for user input.
        while True:
            try:
                # Prompt the user for input.
                user_input = input("Options: (1) Print all data | (2) Print live user location | (q) Quit input listener > ")
                # Handle 'Print all data' option.
                if user_input == '1':
                    print("\n--- All Stored Data ---")
                    # Create a temporary DB handler instance to print data. Consider passing the main one if state matters.
                    DatabaseHandler().print_data()
                    print("--- End of Data ---\n")
                # Handle 'Print live user location' option.
                elif user_input == '2':
                    # Get list of currently tracked session IDs from the Routes instance.
                    session_ids = self.routes_instance.get_all_sessions()
                    # Check if any sessions are being tracked.
                    if not session_ids:
                        print("No active user sessions being tracked.")
                        continue # Go back to waiting for input.

                    # Display the list of tracked sessions.
                    print("\n--- Tracked User Sessions ---")
                    for i, session_id in enumerate(session_ids):
                        print(f"{i + 1}. {session_id}")
                    print("--------------------------")

                    # Prompt user to select a session number.
                    try:
                        choice_input = input("Enter the number of the session to view (or 'c' to cancel): ")
                        # Allow user to cancel.
                        if choice_input.lower() == 'c':
                            continue
                        choice = int(choice_input)
                        # Validate the chosen number.
                        if 1 <= choice <= len(session_ids):
                            # Get the selected session ID from the list.
                            selected_sid = session_ids[choice - 1]
                        else:
                            print("Invalid selection number.")
                            continue # Go back to waiting for input.
                    # Handle non-integer input.
                    except ValueError:
                        print("Invalid input. Please enter a number or 'c'.")
                        continue # Go back to waiting for input.

                    # Retrieve the location for the selected session ID using the Routes instance.
                    lat, lon = self.routes_instance.get_user_session_location(selected_sid)

                    # Check if location data was found.
                    if lat is not None and lon is not None:
                        # Retrieve the timestamp for the last update from the Routes instance.
                        # Acquire lock for thread safety when accessing shared session data.
                        with self.routes_instance.session_lock:
                            # Access session data safely.
                            session_data = self.routes_instance.user_sessions.get(selected_sid)
                            # Extract timestamp if data structure is valid.
                            last_seen_timestamp = session_data[2] if session_data and len(session_data) == 3 else 0
                        # Format the timestamp for display.
                        last_seen_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_seen_timestamp)) if last_seen_timestamp else "N/A"
                        # Print the location and last seen time.
                        print(f"Session {selected_sid} -> Latitude: {lat}, Longitude: {lon} (Last seen: {last_seen_str})")
                    else:
                        # Handle cases where location is not available (e.g., session expired or no data yet).
                        print(f"No location data currently available or session inactive for {selected_sid}.")
                # Handle 'Quit' option.
                elif user_input.lower() == 'q':
                    print("Exiting input listener thread.")
                    break # Exit the while loop, terminating the thread.
                # Handle invalid input.
                else:
                    print("Invalid option selected.")
            # Handle potential errors during input reading (e.g., EOFError if input stream closes).
            except EOFError:
                print("\nInput stream closed. Exiting input listener thread.")
                break # Exit loop on EOF.
            except Exception as e:
                print(f"\nError in input listener: {e}. Exiting thread.")
                break # Exit loop on other exceptions.


# --- Main execution block ---
# This code runs only when the script is executed directly (not imported).
if __name__ == "__main__":
    # Create an instance of the FlaskApp class.
    flask_app = FlaskApp()

    # --- Start Input Listener Thread ---
    # Create a non-daemon thread for the input listener.
    # This allows the program to wait for this thread if needed, but Flask typically runs indefinitely.
    input_thread = threading.Thread(target=flask_app.listen_for_input)
    input_thread.daemon = True # Set as daemon so it doesn't block program exit if Flask stops.
    # Start the input listener thread.
    input_thread.start()
    # --- End Start Input Listener Thread ---

    # Start the Flask application (which also starts the cleanup thread).
    # This call will block and run the web server in the main thread.
    flask_app.run()

    # Code below this point might not be reached if Flask runs indefinitely.
    # If Flask exits, we might want to ensure the input thread is joined.
    # input_thread.join() # Optional: Wait for the input thread to finish if Flask exits.