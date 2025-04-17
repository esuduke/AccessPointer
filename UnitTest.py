"""
Unit tests for the Routes class
"""

import unittest
from Routes import Routes
from flask import Flask
from unittest.mock import MagicMock
import time
import json


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

    def test_generate_id_multi_requests_performance(self):
        """
        Test making multiple requuests to /generate_unique_id,
        ensuring uniqueness and reasonable response time
        """
        num = 20 # number of requests
        ids = []
        start_time = time.time()

        # Loop to make multiple requests concurrently
        for i in range(num):
            # Uses a different session id for each request to test different users
            session_id = f"session-id-test-{i}"
            response = self.client1.get(f"/generate_unique_id?session_id={session_id}")

            # Check for success
            self.assertEqual(response.status_code, 200, msg = f"Request {i+1} failed")

            data = response.get_json()
            self.assertIn("id", data, msg = f"Request {i+1} response is missing id")
            ids.append(data["id"])

        end_time = time.time()
        duration = end_time - start_time

        # Check if there were the correct number of requests
        self.assertEqual(len(ids), num, msg = f"Expected {num} IDs but recieved {len(ids)}")
        
        # Check if all ids are unique
        unique_ids = set(ids)
        self.assertEqual(len(unique_ids), num, msg = "Not all ids are unqiue")

        # Check if the time taken is reasonable
        time_limit = 1.0
        self.assertLess(duration, time_limit, msg = f"Generating {num} ids took more than {time_limit}s ({duration} s)")

    def test_generate_id_missing_session_id(self):
        """
        Test if the /generate_unique_id route returns HTTP status 400 (Bad Request)
        when the session_id parameter is completely missing from the request.
        """
        # Make a GET request without the session_id query parameter
        response = self.client1.get("/generate_unique_id")

        # Assert that the HTTP status code is 400
        self.assertEqual(response.status_code, 400, msg="Expected HTTP 400 Bad Request when session_id parameter is missing.")

        # Check the error message in the JSON response
        data = response.get_json()
        self.assertIn("error", data, msg="JSON response should contain an 'error' field.")
        self.assertEqual(data.get("error"), "Missing session_id parameter", msg="Error message should indicate the missing session_id parameter.")

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

    def test_submit_speed_success(self):
        """Test successful speed submission"""
        session_id = "submit-test-session-1"
        unique_id = 123456
        # Ensure the session ID exists
        self.routes_instance.session_ids_to_generated_ids[session_id] = unique_id
        # Mock the database handler method
        self.routes_instance.db_handler.save_speed_test = MagicMock()

        # Example data
        payload = {
            "dlStatus": "123.45",
            "ulStatus": "50.2",
            "pingStatus": "15.6",
            "session_id": session_id
        }

        # Create post request
        response = self.client1.post(
            "/submit-speed",
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Check success status
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("message"), "Speed test results saved!")
        self.assertEqual(data.get("id"), unique_id)

        # Check if the mock was called correctly
        self.routes_instance.db_handler.save_speed_test.assert_called_once_with(
            123.45, # dl
            50.2,   # ul
            15.6,   # ping
            unique_id # id
        )

    def test_submit_speed_fail_values(self):
        """Test submission with 'Fail' values converted to 0.0."""
        session_id = "submit-test-session-fail"
        unique_id = 654321
        self.routes_instance.session_ids_to_generated_ids[session_id] = unique_id
        self.routes_instance.db_handler.save_speed_test = MagicMock()

        payload = {
            "dlStatus": "Fail",
            "ulStatus": "50.2",
            "pingStatus": "Fail",
            "session_id": session_id
        }

        response = self.client1.post(
            "/submit-speed",
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        # Check arguments passed to the mock
        self.routes_instance.db_handler.save_speed_test.assert_called_once_with(
            0.0,   # dlStatus was "Fail"
            50.2,  # ulStatus was valid
            0.0,   # pingStatus was "Fail"
            unique_id
        )

    def test_submit_speed_missing_values(self):
        """Test submission with missing speed values default to 0.0."""
        session_id = "submit-test-session-missing"
        unique_id = 789012
        self.routes_instance.session_ids_to_generated_ids[session_id] = unique_id
        self.routes_instance.db_handler.save_speed_test = MagicMock()

        payload = {
            "dlStatus": "100.0",
            # ulStatus is missing
            # pingStatus is missing
            "session_id": session_id
        }

        response = self.client1.post(
            "/submit-speed",
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        self.routes_instance.db_handler.save_speed_test.assert_called_once_with(
            100.0, # dlStatus present
            0.0,   # ulStatus missing, defaults to 0.0
            0.0,   # pingStatus missing, defaults to 0.0
            unique_id
        )

    def test_submit_speed_invalid_string_values(self):
        """Test submission with invalid non-numeric strings defaulting to 0.0."""
        session_id = "submit-test-session-invalid-str"
        unique_id = 112233
        self.routes_instance.session_ids_to_generated_ids[session_id] = unique_id
        self.routes_instance.db_handler.save_speed_test = MagicMock()

        payload = {
            "dlStatus": "abc", # Invalid string
            "ulStatus": "50.5", # Valid numeric string
            "pingStatus": "---", # Another invalid string
            "session_id": session_id
        }
        # Current behavior is 200 OK, defaulting invalid values to 0.0
        response = self.client1.post(
            "/submit-speed",
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        self.routes_instance.db_handler.save_speed_test.assert_called_once_with(
            0.0, # dlStatus was "abc" -> triggers except -> reset to 0.0
            0.0, # ulStatus was "50.5" -> BUT gets reset to 0.0 in except block
            0.0, # pingStatus was "---" -> triggers except -> reset to 0.0
            unique_id
        )

    def test_submit_speed_missing_session_id(self):
        """Test submission with missing session_id key in JSON payload."""
        payload = {
            "dlStatus": "10.0",
            "ulStatus": "5.0",
            "pingStatus": "20.0"
            # session_id is missing
        }

        response = self.client1.post(
            "/submit-speed",
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data.get("error"), "Missing session_id")

    def test_submit_speed_unrecognized_session_id(self):
        """Test submission with a session_id not previously generated."""
        session_id = "unrecognized-session"
        # Ensure this session_id is NOT in the mapping
        if session_id in self.routes_instance.session_ids_to_generated_ids:
            del self.routes_instance.session_ids_to_generated_ids[session_id]

        self.routes_instance.db_handler.save_speed_test = MagicMock() # Mock DB just in case

        payload = {
            "dlStatus": "10.0",
            "ulStatus": "5.0",
            "pingStatus": "20.0",
            "session_id": session_id
        }

        response = self.client1.post(
            "/submit-speed",
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("No test ID found for this session", data.get("error"))
        # Check DB method was NOT called
        self.routes_instance.db_handler.save_speed_test.assert_not_called()

    def test_submit_speed_invalid_json(self):
        """Test submission with malformed JSON syntax and empty payload."""
        # Test with syntactically incorrect JSON
        response_malformed = self.client1.post(
            "/submit-speed",
            data="{ 'dlStatus': '10.0', ", # Malformed JSON
            content_type='application/json' # Correct content type
        )

        # Assert Flask returns 400 Bad Request for malformed JSON.
        self.assertEqual(response_malformed.status_code, 400,
                         msg="Expected 400 Bad Request for malformed JSON payload.")

        # Test with empty JSON object payload (should trigger the 'if not data' check in the route)
        response_empty = self.client1.post(
            "/submit-speed",
            content_type='application/json',
            data='{}' # Send valid, empty JSON object
        )
        self.assertEqual(response_empty.status_code, 400,
                         msg="Expected 400 Bad Request for empty JSON object payload.")

        # For an empty payload, our route *should* return JSON, so we can check it.
        data_empty = response_empty.get_json()
        self.assertIsNotNone(data_empty,
                             msg="Response body should be valid JSON for empty payload case.")
        self.assertEqual(data_empty.get("error"), "Invalid or empty JSON payload",
                         msg="Incorrect error message for empty JSON payload.")


    def test_submit_speed_db_error(self):
        """Test handling of a database exception during save."""
        session_id = "submit-test-session-db-error"
        unique_id = 445566
        self.routes_instance.session_ids_to_generated_ids[session_id] = unique_id

        # Setup: Mock the database handler to raise an exception
        self.routes_instance.db_handler.save_speed_test = MagicMock(
            side_effect=Exception("Simulated DB Error")
        )

        payload = {
            "dlStatus": "10.0",
            "ulStatus": "5.0",
            "pingStatus": "20.0",
            "session_id": session_id
        }

        response = self.client1.post(
            "/submit-speed",
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertEqual(data.get("error"), "Failed to save speed results")

        # Check the mock was called (even though it raised an error)
        self.routes_instance.db_handler.save_speed_test.assert_called_once()

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

    def test_index_route(self):
        """
        Test if the index route returns HTTP status 200 (OK)
        and contains expected HTML content.
        """
        response = self.client1.get("/")
        self.assertEqual(response.status_code, 200)

    def test_heatmap_data_valid_entries(self):
        """
        Test if /heatmap-data returns HTTP 200 and correct data
        when the DB returns multiple valid entries.
        """
        mock_data = {
            1: {"download": 10.5, "location": {"latitude": 43.0376, "longitude": -76.1326}},
            2: {"download": 20.0, "location": {"latitude": 43.0374, "longitude": -76.1324}}
        }
        self.routes_instance.db_handler.get_data = MagicMock(return_value=mock_data)

        response = self.client1.get("/heatmap-data")
        data = response.get_json()

        # Assert status is OK and correct number of data points
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", data)
        self.assertIn("max", data)
        self.assertEqual(len(data["data"]), 2)
        self.assertAlmostEqual(data["max"], 20.0)

    def test_heatmap_data_with_fail_speed(self):
        """
        Test if /heatmap-data treats 'Fail' download values as 0.0.
        """
        mock_data = {
            1: {"download": "Fail", "location": {"latitude": 43.0376, "longitude": -76.1326}},
            2: {"download": 5.0, "location": {"latitude": 43.0375, "longitude": -76.1325}}
        }
        self.routes_instance.db_handler.get_data = MagicMock(return_value=mock_data)

        response = self.client1.get("/heatmap-data")
        data = response.get_json()

        # Assert both entries are returned and max is correct
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data["data"]), 2)
        self.assertAlmostEqual(data["max"], 5.0)

    def test_heatmap_data_all_invalid_locations(self):
        """
        Test if /heatmap-data skips entries with invalid lat/lon values.
        """
        mock_data = {
            1: {"download": 10.0, "location": {"latitude": None, "longitude": None}},
            2: {"download": 20.0, "location": {"latitude": "bad", "longitude": "data"}},
        }
        self.routes_instance.db_handler.get_data = MagicMock(return_value=mock_data)

        response = self.client1.get("/heatmap-data")
        data = response.get_json()

        # All invalid locations should be skipped, fallback max = 1.0
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["data"], [])
        self.assertEqual(data["max"], 1.0)

        
    def test_heatmap_data_empty(self):
        """
        Test if /heatmap-data returns an empty list and max = 1.0 when DB returns no data.
        """
        self.routes_instance.db_handler.get_data = MagicMock(return_value={})

        response = self.client1.get("/heatmap-data")
        data = response.get_json()

        # No data should return fallback max = 1.0
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["data"], [])
        self.assertEqual(data["max"], 1.0)

if __name__ == '__main__':
    unittest.main()
