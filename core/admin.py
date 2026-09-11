from django.contrib import admin
from .models import Resource, Infrastructure, HardwareNode


admin.site.register(Resource)
admin.site.register(Infrastructure)
admin.site.register(HardwareNode)