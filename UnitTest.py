"""
Unit tests for the Routes class
"""

import unittest
from Routes import Routes
from flask import Flask

class TestRoutes(unittest.TestCase):
    """Test for the Flask routes defined in the Routes class."""

    def setUp(self):
        """
        Set up a test Flask app and necessary components before each test.
        """
        # Create a Flask application instance specifically for testing
        self.app = Flask(__name__)

        # Enable Flask's testing mode
        self.app.config['TESTING'] = True

        # Instantiate the Routes class
        # Connects the Routes class to our Flask App
        self.routes_instance = Routes(self.app)

        # Create test clients from the Flask application.
        # Each client simulates a separate browser session
        self.client1 = self.app.test_client()
        self.client2 = self.app.test_client() 

    def test_generate_id_route_200(self):
        """
        Test if the /generate_unique_id route returns HTTP status 200 (OK)
        when provided with a valid session_id.
        """
        session_id = "test-session_id-0"

        response = self.client1.get(f"/generate_unique_id?session_id={session_id}")

        # Assert that the HTTP status code is 200
        self.assertEqual(response.status_code, 200)

    def test_generate_id_route_no_id(self):
        """
        Test if the /generate_unique_id route returns HTTP status 400 (Bad Request)
        when the session_id parameter is provided but empty.
        """
        # Make a GET request with an empty session_id parameter
        response = self.client1.get("/generate_unique_id?session_id=")

        # Assert that the HTTP status code is 400
        # Checks behavior with an empty string value.
        self.assertEqual(response.status_code, 400)

    def test_generate_id_route_two_client(self):
        """
        Test if two different clients (different user sessions)
        receive different unique IDs
        """
        session_id1 = "test-session-id-1"
        session_id2 = "test-session-id-2"
        response1 = self.client1.get(f"/generate_unique_id?session_id={session_id1}")
        response2 = self.client2.get(f"/generate_unique_id?session_id={session_id2}")

        # Parse the JSON response to get the generated IDs
        data1 = response1.get_json()
        data2 = response2.get_json()

        # Assert that the 'id' from client1 is not equal to the 'id' from client2
        self.assertNotEqual(data1["id"], data2["id"], msg="IDs generated for different sessions should not be equal")

    def test_generate_id_route_different(self):
        """
        Test if making two requests to /generate_unique_id for the same session
        results in different generated IDs
        """
        session_id = "test-session-id-1"
        response1 = self.client1.get((f"/generate_unique_id?session_id={session_id}"))
        # Same client with the same session id
        response2 = self.client1.get((f"/generate_unique_id?session_id={session_id}"))

        # Parse the JSON response from both requests
        data1 = response1.get_json()
        data2 = response2.get_json()

        # Assert that the 'id' from the first response is not equal to the 'id' from the second response
        self.assertNotEqual(data1["id"], data2["id"], msg="Subsequent calls for the same session should generate different (overwritten) IDs")

    def test_save_location(self):
        """
        Test if the /save_location route returns HTTP status 200 (OK)
        when provided with valid parameters.
        """
        # Define the parameters for the request
        session_id = "test-session-id-1"
        unique_id = "test-unique-id-1"
        latitude = 67.7749
        longitude = -121.5193

        # Make a POST request to the /save_location route with the parameters
        response = self.client1.post(f"/save_location?session_id={session_id}&unique_id={unique_id}&latitude={latitude}&longitude={longitude}")

        # Assert that the HTTP status code is 200
        self.assertEqual(response.status_code, 200)

    def test_save_location_no_location(self):
        """
        Test if the /save_location route returns HTTP status 400 (Bad Request)
        when the latitude and longitude parameters are provided but empty.
        """
        # Make a POST request with empty latitude and longitude parameters
        response = self.client1.post("/save_location?session_id=test-session-id-1&unique_id=test-unique-id-1&latitude=&longitude=")

        # Assert that the HTTP status code is 400
        # Checks behavior with an empty string value.
        self.assertEqual(response.status_code, 400)

    def test_save_location_missing_unique_id(self):
        """
        Test if the /save_location route returns HTTP status 400 (Bad Request)
        when the unique_id parameter is missing.
        """
        session_id = "test-session-id-1"
        latitude = 47.7749
        longitude = -122.4194

        response = self.client1.post(f"/save_location?session_id={session_id}&latitude={latitude}&longitude={longitude}")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing unique test id ('id')", response.get_json().get("error", ""))

    def test_save_location_invalid_lat_lon_format(self):
        """
        Test if the /save_location route returns HTTP status 400 (Bad Request)
        when the latitude or longitude parameters are invalid.
        """
        session_id = "test-session-id-1"
        unique_id = "test-unique-id-1"
        latitude = "invalid_lat"
        longitude = "invalid_lon"

        response = self.client1.post(f"/save_location?session_id={session_id}&unique_id={unique_id}&latitude={latitude}&longitude={longitude}")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid data format", response.get_json().get("error", ""))

    def test_save_location_extra_parameters(self):
        """
        Test if the /save_location route handles extra parameters properly.
        """
        session_id = "test-session-id-1"
        unique_id = "test-unique-id-1"
        latitude = 39.7749
        longitude = -112.4294

        response = self.client1.post(f"/save_location?session_id={session_id}&unique_id={unique_id}&latitude={latitude}&longitude={longitude}&extra_param=extra_value")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Location saved successfully!", response.get_json().get("message", ""))

    def test_save_location_boundary_values(self):
        """
        Test if the /save_location route handles boundary values for latitude and longitude.
        """
        session_id = "test-session-id-1"
        unique_id = "test-unique-id-1"
        latitude = 90.0  # Maximum valid latitude
        longitude = 180.0  # Maximum valid longitude

        response = self.client1.post(f"/save_location?session_id={session_id}&unique_id={unique_id}&latitude={latitude}&longitude={longitude}")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Location saved successfully!", response.get_json().get("message", ""))

    def test_save_user_location(self):
        """
        Test if the /save_user_location route returns HTTP status 200 (OK)
        when provided with valid parameters.
        """
        # Define the parameters for the request
        session_id = "test-session-id-1"
        unique_id = "test-unique-id-1"
        latitude = 35.7749
        longitude = -121.4194

        # Make a POST request to the /save_user_location route with the parameters
        response = self.client1.post(f"/save_user_location?session_id={session_id}&unique_id={unique_id}&latitude={latitude}&longitude={longitude}")

        # Assert that the HTTP status code is 200
        self.assertEqual(response.status_code, 200)

    def test_save_user_location_no_location(self):
        """
        Test if the /save_user_location route returns HTTP status 400 (Bad Request)
        when the latitude and longitude parameters are provided but empty.
        """
        # Make a POST request with empty latitude and longitude parameters
        response = self.client1.post("/save_user_location?session_id=test-session-id-1&unique_id=test-unique-id-1&latitude=&longitude=")

        # Assert that the HTTP status code is 400
        # Checks behavior with an empty string value.
        self.assertEqual(response.status_code, 400)

    def test_save_user_location_out_of_bounds_lat_lon(self):
        """
        Test if the /save_user_location route handles out-of-bounds latitude and longitude.
        """
        session_id = "test-session-id-1"
        latitude = 100.0  # Out of bounds latitude
        longitude = 200.0  # Out of bounds longitude

        response = self.client1.post("/save_user_location", json={"session_id": session_id, "latitude": latitude, "longitude": longitude})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid lat/lon format", response.get_json().get("error", ""))

    def test_save_user_location_missing_session_id(self):
        """
        Test if the /save_user_location route returns HTTP status 400 (Bad Request)
        when the session_id parameter is missing.
        """
        latitude = 38.7749
        longitude = -112.4194

        response = self.client1.post("/save_user_location", json={"latitude": latitude, "longitude": longitude})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing required fields: session_id", response.get_json().get("error", ""))

if __name__ == '__main__':
    unittest.main()
