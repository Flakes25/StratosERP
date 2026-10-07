from datetime import date

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone


# ---------------------------------------------------------------
# Existing models (kept so current data and templates still work)
# ---------------------------------------------------------------
class Resource(models.Model):
    resource_name = models.CharField(max_length=100)
    category = models.CharField(max_length=100)
    quantity = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default="Available")
    description = models.TextField(blank=True)

    def __str__(self):
        return self.resource_name


class Infrastructure(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    status = models.CharField(max_length=50, default="Operational")
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class HardwareNode(models.Model):
    ONLINE = "Online"
    OFFLINE = "Offline"
    MAINTENANCE = "Maintenance"
    STATUS_CHOICES = [
        (ONLINE, "Online"),
        (OFFLINE, "Offline"),
        (MAINTENANCE, "Maintenance"),
    ]

    node_name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    cpu_usage = models.FloatField(default=0)
    memory_usage = models.FloatField(default=0)
    storage_usage = models.FloatField(default=0)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default=ONLINE)
    last_seen = models.DateTimeField(auto_now=True, null=True)  # updates on every save

    class Meta:
        ordering = ["-last_seen", "-id"]

    def __str__(self):
        return self.node_name


# ---------------------------------------------------------------
# Objective A: organizational data
# ---------------------------------------------------------------
class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Employee(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="employee",
    )
    employee_id = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    email = models.EmailField(blank=True)
    department = models.ForeignKey(
        Department, null=True, on_delete=models.SET_NULL, related_name="employees"
    )
    position = models.CharField(max_length=100, blank=True)
    date_hired = models.DateField(default=date.today)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["last_name", "first_name"]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return f"{self.employee_id} - {self.full_name}"


class Supplier(models.Model):
    name = models.CharField(max_length=120, unique=True)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


# ---------------------------------------------------------------
# Objective C: inventory and procurement
# ---------------------------------------------------------------
class InventoryItem(models.Model):
    name = models.CharField(max_length=120)
    sku = models.CharField(max_length=40, unique=True)
    category = models.ForeignKey(
        Category, null=True, on_delete=models.SET_NULL, related_name="items"
    )
    quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=5)
    location = models.CharField(max_length=100, blank=True)  # warehouse / room
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    def __str__(self):
        return f"{self.name} ({self.sku})"


class StockMovement(models.Model):
    IN = "IN"
    OUT = "OUT"
    ADJUST = "ADJUST"
    TYPE_CHOICES = [(IN, "Stock in"), (OUT, "Stock out"), (ADJUST, "Adjustment")]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="movements")
    movement_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.movement_type} {self.quantity} x {self.item.name}"


class PurchaseRequest(models.Model):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    RECEIVED = "Received"
    STATUS_CHOICES = [(s, s) for s in (PENDING, APPROVED, REJECTED, RECEIVED)]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="purchase_requests")
    supplier = models.ForeignKey(Supplier, null=True, on_delete=models.SET_NULL)
    quantity = models.PositiveIntegerField()
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="purchase_requests",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @transaction.atomic
    def mark_received(self, user=None):
        """Restock the item and log the movement. Safe to call once."""
        if self.status == self.RECEIVED:
            return
        self.status = self.RECEIVED
        self.save(update_fields=["status"])
        self.item.quantity += self.quantity
        self.item.save(update_fields=["quantity"])
        StockMovement.objects.create(
            item=self.item, movement_type=StockMovement.IN, quantity=self.quantity,
            note=f"Purchase request #{self.pk} received", created_by=user,
        )

    def __str__(self):
        return f"PR#{self.pk} {self.item.name} x{self.quantity}"


# ---------------------------------------------------------------
# Objective D: asset assignment
# ---------------------------------------------------------------
class AssetAssignment(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="assignments")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="assignments")
    quantity = models.PositiveIntegerField(default=1)
    assigned_at = models.DateTimeField(auto_now_add=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-assigned_at"]

    @property
    def is_active(self):
        return self.returned_at is None

    @classmethod
    @transaction.atomic
    def assign(cls, item, employee, quantity=1, user=None):
        item = InventoryItem.objects.select_for_update().get(pk=item.pk)
        if item.quantity < quantity:
            raise ValueError(f"Only {item.quantity} of '{item.name}' available.")
        item.quantity -= quantity
        item.save(update_fields=["quantity"])
        assignment = cls.objects.create(item=item, employee=employee, quantity=quantity)
        StockMovement.objects.create(
            item=item, movement_type=StockMovement.OUT, quantity=quantity,
            note=f"Assigned to {employee.full_name}", created_by=user,
        )
        return assignment

    @transaction.atomic
    def return_asset(self, user=None):
        if self.returned_at:
            return
        self.returned_at = timezone.now()
        self.save(update_fields=["returned_at"])
        self.item.quantity += self.quantity
        self.item.save(update_fields=["quantity"])
        StockMovement.objects.create(
            item=self.item, movement_type=StockMovement.IN, quantity=self.quantity,
            note=f"Returned by {self.employee.full_name}", created_by=user,
        )

    def __str__(self):
        return f"{self.item.name} -> {self.employee.full_name}"


# ---------------------------------------------------------------
# Dashboard activity feed
# ---------------------------------------------------------------
class ActivityLog(models.Model):
    category = models.CharField(max_length=30)  # SYSTEM, INVENTORY, TELEMETRY...
    message = models.CharField(max_length=255)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.category}] {self.message}"
