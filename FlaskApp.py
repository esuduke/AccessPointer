import threading
from flask import Flask
from Routes import Routes
from NgrokTunnel import NgrokTunnel
from EmailSender import EmailSender
from DatabaseHandler import DatabaseHandler

class FlaskApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.tunnel = NgrokTunnel()
        self.sender = EmailSender()
        self.routes = Routes(self.app)

    def run(self):
        port = 5000
        public_url = self.tunnel.start(port) # start ngrok

        #Send email
        # self.sender.send_email("njczarne@syr.edu", "Updated ngrok URL", f"New ngrok URL: {public_url}")

        print(f" * Secure ngrok tunnel available at: {public_url}")
        self.app.run(host="0.0.0.0", port=port)

    def listen_for_input(self):
        while True:
            user_input = input("Press 1 to print current data, Press 2 to print current location: ")
            if user_input == '1':
                DatabaseHandler().print_data()
            elif user_input == '2':
                latitude, longitude = self.routes.get_user_location()
                if latitude is not None and longitude is not None:
                    print(f"Current Location -> Latitude: {latitude}, Longitude: {longitude}")
                else:
                    print("Location data not available")
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
