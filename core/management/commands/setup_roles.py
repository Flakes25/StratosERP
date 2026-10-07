from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from core.models import (
    Category, Department, Employee, HardwareNode, InventoryItem, Supplier,
)
from core.permissions import ADMIN, ALL_ROLES, HR, INVENTORY, MANAGER

DEMO_PASSWORD = "stratos123"


class Command(BaseCommand):
    help = "Create the four RBAC groups. Add --demo for sample data and one login per role."

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Also load demo data and users")

    def handle(self, *args, **options):
        for name in ALL_ROLES:
            Group.objects.get_or_create(name=name)
        self.stdout.write(self.style.SUCCESS("Roles ready: " + ", ".join(ALL_ROLES)))
        if options["demo"]:
            self.load_demo()

    def load_demo(self):
        User = get_user_model()
        for username, role in [("demo_admin", ADMIN), ("demo_inventory", INVENTORY),
                               ("demo_hr", HR), ("demo_manager", MANAGER)]:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(DEMO_PASSWORD)
                user.is_staff = role == ADMIN  # lets the admin demo user open /admin/
                user.save()
            user.groups.set([Group.objects.get(name=role)])

        it, _ = Department.objects.get_or_create(name="IT Department")
        hr, _ = Department.objects.get_or_create(name="Human Resources")
        for eid, first, last, dept, pos in [
            ("E-001", "Ana", "Reyes", it, "Systems Administrator"),
            ("E-002", "Ben", "Santos", hr, "HR Officer"),
            ("E-003", "Carla", "Dizon", it, "Technician"),
        ]:
            Employee.objects.get_or_create(employee_id=eid, defaults=dict(
                first_name=first, last_name=last, department=dept, position=pos))

        Supplier.objects.get_or_create(name="PC Express", defaults=dict(
            contact_person="Sales Desk", email="sales@example.com"))
        hardware, _ = Category.objects.get_or_create(name="Hardware")
        peripherals, _ = Category.objects.get_or_create(name="Peripherals")
        for name, sku, cat, qty, reorder in [
            ("Laptop", "LAP-001", hardware, 12, 5),
            ("Monitor 24in", "MON-024", peripherals, 4, 5),
            ("Wireless Mouse", "MOU-001", peripherals, 30, 10),
        ]:
            InventoryItem.objects.get_or_create(sku=sku, defaults=dict(
                name=name, category=cat, quantity=qty, reorder_level=reorder, location="Main warehouse"))

        for name, ip, cpu, mem, disk, status in [
            ("node-alpha", "10.0.0.11", 34, 58, 41, "Online"),
            ("node-bravo", "10.0.0.12", 72, 64, 77, "Online"),
            ("node-charlie", "10.0.0.13", 0, 0, 52, "Offline"),
        ]:
            HardwareNode.objects.get_or_create(node_name=name, defaults=dict(
                ip_address=ip, cpu_usage=cpu, memory_usage=mem, storage_usage=disk, status=status))

        self.stdout.write(self.style.SUCCESS(
            f"Demo data loaded. Logins: demo_admin / demo_inventory / demo_hr / demo_manager, "
            f"password '{DEMO_PASSWORD}'"))
