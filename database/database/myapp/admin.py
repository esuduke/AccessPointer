from django.contrib import admin
from .models import Location
from .models import Internet

# Register your models here.

admin.site.register(Location)
admin.site.register(Internet)

