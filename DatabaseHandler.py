# DatabaseHandler.py
# Provides an interface for interacting with the Django database models (Location, Internet).

import os
import django
import sys

# Add the parent directory of 'database' to the Python path
# This allows Django to find the settings module.
# Assumes DatabaseHandler.py is one level above the 'database' directory.
sys.path.append(os.path.join(os.path.dirname(__file__), "database"))

# Set the DJANGO_SETTINGS_MODULE environment variable.
# This tells Django which settings file to use.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "database.settings")
# Initialize Django. This must be called before importing models.
django.setup()

# Import models after Django setup.
from myapp.models import Location, Internet

class DatabaseHandler:
    """
    Handles database operations for Location and Internet speed test data.
    Provides methods to save and retrieve data using Django ORM.
    """
    def __init__(self):
        """Initializes the DatabaseHandler."""
        # Indicate successful initialization.
        print("Database Handler initialized")

    def save_location(self, latitude: float, longitude: float, unique_id: int):
        """
        Saves location data (latitude, longitude, unique_id) to the database.
        Handles potential exceptions during the save operation.
        """
        # Try to create and save a new Location record.
        try:
            # Create a new Location model instance.
            location = Location(latitude=latitude, longitude=longitude, unique_id=unique_id)
            # Save the instance to the database.
            location.save()
            # Log successful save operation.
            print(f"Saved location: Latitude {latitude}, Longitude {longitude}, ID {unique_id}")
        # Catch any exception during the save process.
        except Exception as e:
            # Log the error if saving fails.
            print(f"Error saving location: {e}")

    def save_speed_test(self, download: float, upload: float, ping: float, unique_id: int):
        """
        Saves internet speed test results (download, upload, ping, unique_id) to the database.
        Handles potential exceptions during the save operation.
        """
        # Try to create and save a new Internet record.
        try:
            # Create a new Internet model instance.
            internet = Internet(download=download, upload=upload, ping=ping, unique_id=unique_id)
            # Save the instance to the database.
            internet.save()
            # Log successful save operation.
            print(f"Saved speed test: {download} Mbps / {upload} Mbps / {ping} ms (ID: {unique_id})")
        # Catch any exception during the save process.
        except Exception as e:
            # Log the error if saving fails.
            print(f"Error saving speed test: {e}")

    def get_data(self) -> dict:
        """
        Fetches all Location and Internet data from the database.
        Combines the data based on the 'unique_id'.
        Returns a dictionary where keys are unique_ids and values contain speed and location info.
        """
        # Fetch all records from both tables.
        internet_data = Internet.objects.all() # Query all Internet entries.
        location_data = Location.objects.all() # Query all Location entries.

        # Dictionary to store the combined data, keyed by unique_id.
        combined_data = {}

        # Process Internet data first, creating entries in the dictionary.
        for internet_entry in internet_data:
            unique_id = internet_entry.unique_id
            # Initialize entry for this unique_id.
            combined_data[unique_id] = {
                'download': internet_entry.download,
                'upload': internet_entry.upload,
                'ping': internet_entry.ping,
                'location': None # Placeholder for location data.
            }

        # Process Location data, adding it to existing entries in the dictionary.
        for location_entry in location_data:
            unique_id = location_entry.unique_id
            # Check if a corresponding Internet entry exists.
            if unique_id in combined_data:
                # Add location details to the existing entry.
                combined_data[unique_id]['location'] = {
                    'latitude': location_entry.latitude,
                    'longitude': location_entry.longitude
                }
            # Optional: Handle locations without matching speed tests if needed.
            # else:
            #     combined_data[unique_id] = { 'download': None, ..., 'location': {...}}

        # Return the combined data structure.
        return combined_data

    def print_data(self):
        """
        Fetches combined data using get_data() and prints it to the console.
        Formats the output for readability.
        """
        # Retrieve the combined data.
        data = self.get_data()
        # Iterate through the combined data dictionary.
        for unique_id, info in data.items():
            # Print the unique identifier.
            print(f"Unique ID: {unique_id}")
            # Print internet speed test results.
            print(f"  Internet Data: {info.get('download', 'N/A')} download, {info.get('upload', 'N/A')} upload, {info.get('ping', 'N/A')} ping")
            # Check if location data exists for this ID.
            if info.get('location') is not None:
                # Print location coordinates if available.
                print(f"  Location Data: Latitude: {info['location'].get('latitude', 'N/A')}, Longitude: {info['location'].get('longitude', 'N/A')}")
            else:
                # Indicate if location data is missing.
                print("  Location Data: Not available")
            # Print a separator line between entries.
            print("-" * 40)


# --- Main execution block (for testing purposes) ---
# This block runs only when the script is executed directly.
if __name__ == "__main__":
    # Create an instance of the handler.
    db_handler = DatabaseHandler()
    # Call the print_data method to display current data.
    db_handler.print_data()