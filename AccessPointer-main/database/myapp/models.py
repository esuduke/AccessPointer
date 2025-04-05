from django.db import models

# Create your models here.

class Location(models.Model):
    latitude = models.CharField(max_length=255)
    longitude = models.CharField(max_length=255)
    unique_id = models.IntegerField(default = 100000)

    def __str__(self):
        return self.latitude + ", " + self.longitude + f"\nid: {self.unique_id}"

class Internet(models.Model):
    download = models.IntegerField()
    upload = models.IntegerField()
    ping = models.IntegerField()
    unique_id = models.IntegerField(default = 100000)

    def __str__(self):
        return f"Download Speed: {self.download:.2f} Mbps\nUpload Speed: {self.upload:.2f} Mbps\nPing: {self.ping:.3f} ms\nid: {self.unique_id}"