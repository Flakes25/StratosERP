from django.contrib import admin

from .models import (
    ActivityLog, AssetAssignment, Category, Department, Employee, HardwareNode,
    Infrastructure, InventoryItem, PurchaseRequest, Resource, StockMovement, Supplier,
)


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "quantity", "reorder_level", "location")
    search_fields = ("name", "sku")


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("employee_id", "last_name", "first_name", "department", "is_active")
    search_fields = ("employee_id", "last_name", "first_name")


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "supplier", "quantity", "status", "created_at")
    list_filter = ("status",)


admin.site.register([
    ActivityLog, AssetAssignment, Category, Department, HardwareNode,
    Infrastructure, Resource, StockMovement, Supplier,
])
