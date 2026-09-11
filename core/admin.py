from django.contrib import admin
from .models import Resource, Infrastructure, HardwareNode


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("resource_name", "category", "quantity", "status")
    search_fields = ("resource_name", "category")
    list_filter = ("category", "status")


@admin.register(Infrastructure)
class InfrastructureAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "status")
    search_fields = ("name", "location")
    list_filter = ("status",)


@admin.register(HardwareNode)
class HardwareNodeAdmin(admin.ModelAdmin):
    list_display = (
        "node_name",
        "ip_address",
        "cpu_usage",
        "memory_usage",
        "storage_usage",
        "status",
    )
    search_fields = ("node_name", "ip_address")
    list_filter = ("status",)