import os
import django
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "database"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "database.settings")
django.setup()

from myapp.models import Location, Internet

class DatabaseHandler:
    def __init__(self):
        print("Database Handler initilized")
        
    def save_location(self, latitude, longitude, unique_id):
        # Saves location data to the database
        try:
            location = Location(latitude=latitude, longitude=longitude, unique_id=unique_id)
            location.save()
            print(f"Saved location: Latitude {latitude}, Longitude {longitude}, ID {unique_id}")
        except Exception as e:
            print(f"Error saving location: {e}")

    def save_speed_test(self, download, upload, ping, unique_id):
        # Saves speed test to database
        try:
            internet = Internet(download=download, upload=upload, ping=ping, unique_id=unique_id)
            internet.save()
            print(f"Saved speed test: {download} Mbps / {upload} Mbps / {ping} ms (ID: {unique_id})")
        except Exception as e:
            print(f"Error saving speed test: {e}")

    def get_data(self):
        #Fetch all data from the Internet and Location models
        internet_data = Internet.objects.all() # Query all Internet entries
        location_data = Location.objects.all() # Query all Location entries

        # Dictionary to store the data based on the unique_id
        combined_data = {}

        # Store Internet data in the dictionary using unique_id as key
        for internet_entry in internet_data:
            unique_id = internet_entry.unique_id
            combined_data[unique_id] = {
                'download': internet_entry.download,
                'upload': internet_entry.upload,
                'ping': internet_entry.ping,
                'location': None # Placeholdder for location data
            }

        # Store Location data in the dictionary using unique_id
        for location_entry in location_data:
            unique_id = location_entry.unique_id
            if unique_id in combined_data:
                #Add location data to corresponding unique_id
                combined_data[unique_id]['location'] = {
                    'latitude': location_entry.latitude,
                    'longitude': location_entry.longitude
                }
        return combined_data

    def print_data(self):
        data = self.get_data()
        for unique_id, info in data.items():
            print(f"Unique ID: {unique_id}")
            print(f"Internet Data: {info['download']} download, {info['upload']} upload, {info['ping']} ping")
            if info.get('location') is not None:
                print(f"Location Data: Latitude: {info['location']['latitude']}, Longitude: {info['location']['longitude']}")
            else:
                print("Location Data: Not yet received")
            print("-" * 40)


if __name__ == "__main__":
    handler = DatabaseHandler()
    data = handler.get_data()
    for unique_id, info in data.items():
        print(f"Unique ID: {unique_id}")
        print(f"Internet Data: {info['download']} download, {info['upload']} upload, {info['ping']} ping")
        print(f"Location Data: Latitude: {info['location']['latitude']}, Longitude: {info['location']['longitude']}")
        print("-" * 40)