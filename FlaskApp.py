import threading
from flask import Flask , request, jsonify
from Routes import Routes
from NgrokTunnel import NgrokTunnel
# from EmailSender import EmailSender
from DatabaseHandler import DatabaseHandler

class FlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.tunnel = NgrokTunnel()
       # self.sender = EmailSender()
        self.routes = Routes(self.app)

    # Add the new route for saving speed test results
        # @self.app.route('/save_speed_test_results', methods=['POST'])
        # def save_speed_test_results():
        #     data = request.json
        #     download = data.get('download')
        #     upload = data.get('upload')
        #     ping = data.get('ping')
        #     latitude = data.get('latitude')
        #     longitude = data.get('longitude')
        #     session_id = data.get('session_id')

        #     # Save the results to the database
        #     if session_id:
        #         self.database_handler.save_speed_test_results(
        #             session_id=session_id,
        #             download=download,
        #             upload=upload,
        #             ping=ping,
        #             latitude=latitude,
        #             longitude=longitude
        #         )
        #         print(f"Session {session_id} -> Download: {download} Mbps, Upload: {upload} Mbps, Ping: {ping} ms, "
        #               f"Latitude: {latitude}, Longitude: {longitude}")
        #         return jsonify({"status": "success"}), 200
        #     else:
        #         return jsonify({"status": "error", "message": "Session ID is missing"}), 400


    def run(self):
        port = 8001
        public_url = self.tunnel.start(port) # start ngrok

        #Send email
       # self.sender.send_email("njczarne@syr.edu", "Updated ngrok URL", f"New ngrok URL: {public_url}")

        print(f" * Secure ngrok tunnel available at: {public_url}")
        self.app.run(host="0.0.0.0", port=port)

    def listen_for_input(self):
        while True:
            user_input = input("Press 1 to print current data, Press 2 to print current location for a user: ")
            if user_input == '1':
                DatabaseHandler().print_data()

            elif user_input == '2':
                session_ids = self.routes.get_all_sessions()
                if not session_ids:
                    print("No active users yet.")
                    continue

                print("\nActive User Sessions:")
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

                lat, long = self.routes.get_user_session_location(selected_sid)
                if lat is not None and long is not None:
                    print(f"Session {selected_sid} -> Latitude: {lat}, Longitude: {long}")
                else:
                    print(f"No data available for session {selected_sid}")
            else:
                print("Invalid input")


if __name__ == "__main__":
    flask_app = FlaskApp()

    # Start input listener in seperate thread
    input_thread = threading.Thread(target=flask_app.listen_for_input)
    input_thread.daemon = True
    input_thread.start()

    #Start Flask in a seperate thread
    flask_thread = threading.Thread(target=flask_app.run)
    flask_thread.daemon = True
    flask_thread.start()

    

    while True:
        pass # Keeps the main thread running
