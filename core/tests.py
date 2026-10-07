"""Automated tests for StratosERP.

Run all:        python manage.py test core
Run verbosely:  python manage.py test core -v 2
Run one class:  python manage.py test core.tests.ProcurementFlowTests
"""
import csv
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import (
    ActivityLog, AssetAssignment, Category, Department, Employee, HardwareNode,
    InventoryItem, PurchaseRequest, StockMovement, Supplier,
)
from .permissions import ADMIN, ALL_ROLES, HR, INVENTORY, MANAGER

User = get_user_model()


class BaseTestCase(TestCase):
    """Creates one user per role plus a little shared data."""

    @classmethod
    def setUpTestData(cls):
        for role in ALL_ROLES:
            Group.objects.get_or_create(name=role)

        def make_user(username, role):
            user = User.objects.create_user(username, password="pass12345")
            user.groups.add(Group.objects.get(name=role))
            return user

        cls.admin = make_user("t_admin", ADMIN)
        cls.inv = make_user("t_inv", INVENTORY)
        cls.hr = make_user("t_hr", HR)
        cls.mgr = make_user("t_mgr", MANAGER)

        cls.dept = Department.objects.create(name="IT")
        cls.emp = Employee.objects.create(
            employee_id="E-1", first_name="Ana", last_name="Reyes", department=cls.dept)
        cls.category = Category.objects.create(name="Hardware")
        cls.supplier = Supplier.objects.create(name="PC Express")
        cls.item = InventoryItem.objects.create(
            name="Laptop", sku="LAP-1", category=cls.category, quantity=10, reorder_level=3)

    def login(self, user):
        self.client.force_login(user)

    def stock(self):
        self.item.refresh_from_db()
        return self.item.quantity


# ---------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------
class AuthenticationTests(BaseTestCase):
    def test_anonymous_dashboard_redirects_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("login")))

    def test_anonymous_module_page_redirects_to_login(self):
        response = self.client.get(reverse("inventory_list"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("login")))

    def test_login_with_valid_credentials_goes_to_dashboard(self):
        response = self.client.post(reverse("login"), {"username": "t_inv", "password": "pass12345"})
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)

    def test_login_with_wrong_password_stays_on_login(self):
        response = self.client.post(reverse("login"), {"username": "t_inv", "password": "nope"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "password don't match")

    def test_logout_returns_to_login(self):
        self.login(self.inv)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)


# ---------------------------------------------------------------
# Role-based access control (Objective B)
# ---------------------------------------------------------------
class RoleAccessTests(BaseTestCase):
    def test_access_matrix(self):
        everyone = {"adm": 200, "inv": 200, "hr": 200, "mgr": 200}
        matrix = [
            ("dashboard", everyone),
            ("telemetry", everyone),
            ("reports", everyone),
            ("modules", everyone),
            ("assignments_list", everyone),
            ("hardware_list", everyone),
            ("inventory_list", {"adm": 200, "inv": 200, "hr": 403, "mgr": 200}),
            ("inventory_create", {"adm": 200, "inv": 200, "hr": 403, "mgr": 403}),
            ("suppliers_list", {"adm": 200, "inv": 200, "hr": 403, "mgr": 200}),
            ("movements_list", {"adm": 200, "inv": 200, "hr": 403, "mgr": 200}),
            ("procurement_list", {"adm": 200, "inv": 200, "hr": 403, "mgr": 200}),
            ("procurement_create", {"adm": 200, "inv": 200, "hr": 403, "mgr": 200}),
            ("employees_list", {"adm": 200, "inv": 403, "hr": 200, "mgr": 200}),
            ("employees_create", {"adm": 200, "inv": 403, "hr": 200, "mgr": 403}),
            ("departments_list", {"adm": 200, "inv": 403, "hr": 200, "mgr": 200}),
            ("assignments_create", {"adm": 200, "inv": 200, "hr": 403, "mgr": 403}),
            ("hardware_create", {"adm": 200, "inv": 200, "hr": 403, "mgr": 403}),
        ]
        users = {"adm": self.admin, "inv": self.inv, "hr": self.hr, "mgr": self.mgr}
        for url_name, expected in matrix:
            for key, user in users.items():
                with self.subTest(page=url_name, role=key):
                    self.client.force_login(user)
                    self.assertEqual(self.client.get(reverse(url_name)).status_code, expected[key])

    def test_superuser_counts_as_administrator(self):
        root = User.objects.create_superuser("root", password="pass12345")
        self.login(root)
        for url_name in ("inventory_create", "employees_create", "procurement_list", "reports"):
            with self.subTest(page=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_user_without_a_role_cannot_open_modules(self):
        nobody = User.objects.create_user("nobody", password="pass12345")
        self.login(nobody)
        self.assertEqual(self.client.get(reverse("inventory_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("employees_list")).status_code, 403)

    def test_manager_sees_no_add_button_on_inventory(self):
        self.login(self.mgr)
        response = self.client.get(reverse("inventory_list"))
        self.assertFalse(response.context["can_create"])
        self.assertNotContains(response, reverse("inventory_create"))

    def test_modules_page_only_lists_allowed_modules(self):
        self.login(self.hr)
        labels = [m["label"] for m in self.client.get(reverse("modules")).context["modules"]]
        self.assertIn("Employees", labels)
        self.assertNotIn("Inventory", labels)

    def test_navbar_hides_links_the_role_cannot_open(self):
        self.login(self.hr)
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn(reverse("employees_list"), html)
        self.assertNotIn(reverse("inventory_list"), html)


# ---------------------------------------------------------------
# Inventory (Objective C)
# ---------------------------------------------------------------
class InventoryTests(BaseTestCase):
    def test_low_stock_flag(self):
        self.item.quantity = 3  # equals reorder level
        self.assertTrue(self.item.is_low_stock)
        self.item.quantity = 4
        self.assertFalse(self.item.is_low_stock)

    def test_create_item_and_log_activity(self):
        self.login(self.inv)
        response = self.client.post(reverse("inventory_create"), {
            "name": "Mouse", "sku": "MOU-1", "category": self.category.pk,
            "quantity": 5, "reorder_level": 2, "location": "A1", "description": "",
        })
        self.assertRedirects(response, reverse("inventory_list"), fetch_redirect_response=False)
        self.assertTrue(InventoryItem.objects.filter(sku="MOU-1").exists())
        log = ActivityLog.objects.filter(category="INVENTORY").first()
        self.assertIsNotNone(log)
        self.assertIn("Mouse", log.message)

    def test_duplicate_sku_is_rejected(self):
        self.login(self.inv)
        response = self.client.post(reverse("inventory_create"), {
            "name": "Other", "sku": "LAP-1", "category": self.category.pk,
            "quantity": 1, "reorder_level": 1, "location": "", "description": "",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(InventoryItem.objects.filter(sku="LAP-1").count(), 1)

    def test_search_filters_the_list(self):
        InventoryItem.objects.create(name="Monitor", sku="MON-1", quantity=1, reorder_level=1)
        self.login(self.inv)
        response = self.client.get(reverse("inventory_list"), {"q": "lap"})
        skus = [row["cells"][0] for row in response.context["rows"]]
        self.assertEqual(skus, ["LAP-1"])

    def test_edit_item(self):
        self.login(self.inv)
        response = self.client.post(reverse("inventory_update", args=[self.item.pk]), {
            "name": "Laptop Pro", "sku": "LAP-1", "category": self.category.pk,
            "quantity": 7, "reorder_level": 3, "location": "", "description": "",
        })
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual((self.item.name, self.item.quantity), ("Laptop Pro", 7))

    def test_manager_cannot_create_item(self):
        self.login(self.mgr)
        response = self.client.post(reverse("inventory_create"), {
            "name": "X", "sku": "X-1", "category": self.category.pk,
            "quantity": 1, "reorder_level": 1, "location": "", "description": "",
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(InventoryItem.objects.filter(sku="X-1").exists())

    def test_delete_unused_category(self):
        extra = Category.objects.create(name="Temp")
        self.login(self.inv)
        self.client.post(reverse("categories_delete", args=[extra.pk]))
        self.assertFalse(Category.objects.filter(pk=extra.pk).exists())


# ---------------------------------------------------------------
# Procurement (Objective C)
# ---------------------------------------------------------------
class ProcurementFlowTests(BaseTestCase):
    def make_request(self, status=PurchaseRequest.PENDING, qty=5):
        return PurchaseRequest.objects.create(
            item=self.item, supplier=self.supplier, quantity=qty,
            requested_by=self.mgr, status=status)

    def act(self, user, pr, action):
        self.client.force_login(user)
        return self.client.post(reverse("procurement_action", args=[pr.pk, action]))

    def test_creating_a_request_records_the_requester_and_starts_pending(self):
        self.login(self.inv)
        self.client.post(reverse("procurement_create"), {
            "item": self.item.pk, "supplier": self.supplier.pk, "quantity": 5})
        pr = PurchaseRequest.objects.get()
        self.assertEqual(pr.requested_by, self.inv)
        self.assertEqual(pr.status, PurchaseRequest.PENDING)

    def test_manager_can_approve_and_reject(self):
        approved, rejected = self.make_request(), self.make_request()
        self.act(self.mgr, approved, "approve")
        self.act(self.mgr, rejected, "reject")
        approved.refresh_from_db(); rejected.refresh_from_db()
        self.assertEqual(approved.status, PurchaseRequest.APPROVED)
        self.assertEqual(rejected.status, PurchaseRequest.REJECTED)

    def test_inventory_staff_cannot_approve(self):
        pr = self.make_request()
        self.assertEqual(self.act(self.inv, pr, "approve").status_code, 403)
        pr.refresh_from_db()
        self.assertEqual(pr.status, PurchaseRequest.PENDING)

    def test_receiving_adds_stock_and_logs_a_movement(self):
        pr = self.make_request(status=PurchaseRequest.APPROVED, qty=5)
        self.act(self.inv, pr, "receive")
        pr.refresh_from_db()
        self.assertEqual(pr.status, PurchaseRequest.RECEIVED)
        self.assertEqual(self.stock(), 15)
        movement = StockMovement.objects.get()
        self.assertEqual((movement.movement_type, movement.quantity), ("IN", 5))

    def test_receiving_twice_does_not_double_count(self):
        pr = self.make_request(status=PurchaseRequest.APPROVED, qty=5)
        self.act(self.inv, pr, "receive")
        self.act(self.inv, pr, "receive")
        self.assertEqual(self.stock(), 15)
        self.assertEqual(StockMovement.objects.count(), 1)

    def test_pending_request_cannot_be_received(self):
        pr = self.make_request(status=PurchaseRequest.PENDING)
        self.act(self.inv, pr, "receive")
        pr.refresh_from_db()
        self.assertEqual(pr.status, PurchaseRequest.PENDING)
        self.assertEqual(self.stock(), 10)

    def test_manager_cannot_receive(self):
        pr = self.make_request(status=PurchaseRequest.APPROVED)
        self.assertEqual(self.act(self.mgr, pr, "receive").status_code, 403)
        self.assertEqual(self.stock(), 10)

    def test_unknown_action_is_404(self):
        pr = self.make_request()
        self.assertEqual(self.act(self.admin, pr, "explode").status_code, 404)

    def test_actions_require_post(self):
        pr = self.make_request()
        self.login(self.admin)
        response = self.client.get(reverse("procurement_action", args=[pr.pk, "approve"]))
        self.assertEqual(response.status_code, 405)

    def test_approve_and_receive_buttons_follow_role_and_status(self):
        pending = self.make_request()
        self.login(self.mgr)
        labels = [a["label"] for a in self.client.get(reverse("procurement_list")).context["rows"][0]["actions"]]
        self.assertEqual(labels, ["Approve", "Reject"])
        pending.status = PurchaseRequest.APPROVED
        pending.save()
        self.login(self.inv)
        labels = [a["label"] for a in self.client.get(reverse("procurement_list")).context["rows"][0]["actions"]]
        self.assertEqual(labels, ["Mark received"])


# ---------------------------------------------------------------
# Asset assignment (Objective D)
# ---------------------------------------------------------------
class AssetAssignmentTests(BaseTestCase):
    def test_assign_reduces_stock_and_logs_movement(self):
        AssetAssignment.assign(self.item, self.emp, 3, user=self.inv)
        self.assertEqual(self.stock(), 7)
        movement = StockMovement.objects.get()
        self.assertEqual((movement.movement_type, movement.quantity), ("OUT", 3))

    def test_return_restores_stock(self):
        assignment = AssetAssignment.assign(self.item, self.emp, 3)
        assignment.return_asset()
        self.assertEqual(self.stock(), 10)
        self.assertFalse(assignment.is_active)

    def test_returning_twice_does_not_double_restore(self):
        assignment = AssetAssignment.assign(self.item, self.emp, 3)
        assignment.return_asset()
        assignment.return_asset()
        self.assertEqual(self.stock(), 10)

    def test_cannot_assign_more_than_in_stock(self):
        with self.assertRaises(ValueError):
            AssetAssignment.assign(self.item, self.emp, 99)
        self.assertEqual(self.stock(), 10)
        self.assertEqual(AssetAssignment.objects.count(), 0)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_assign_through_the_form(self):
        self.login(self.inv)
        response = self.client.post(reverse("assignments_create"), {
            "item": self.item.pk, "employee": self.emp.pk, "quantity": 2})
        self.assertRedirects(response, reverse("assignments_list"), fetch_redirect_response=False)
        self.assertEqual(self.stock(), 8)

    def test_form_rejects_quantity_above_stock(self):
        self.login(self.inv)
        response = self.client.post(reverse("assignments_create"), {
            "item": self.item.pk, "employee": self.emp.pk, "quantity": 99})
        self.assertEqual(response.status_code, 200)
        self.assertIn("quantity", response.context["form"].errors)
        self.assertEqual(self.stock(), 10)

    def test_out_of_stock_items_and_inactive_employees_are_not_offered(self):
        InventoryItem.objects.create(name="Empty", sku="E-0", quantity=0, reorder_level=1)
        Employee.objects.create(employee_id="E-9", first_name="Old", last_name="Timer", is_active=False)
        self.login(self.inv)
        form = self.client.get(reverse("assignments_create")).context["form"]
        self.assertNotIn("E-0", [i.sku for i in form.fields["item"].queryset])
        self.assertNotIn("E-9", [e.employee_id for e in form.fields["employee"].queryset])

    def test_return_through_the_view(self):
        assignment = AssetAssignment.assign(self.item, self.emp, 4)
        self.login(self.inv)
        self.client.post(reverse("assignment_return", args=[assignment.pk]))
        self.assertEqual(self.stock(), 10)

    def test_hr_cannot_assign_or_return(self):
        assignment = AssetAssignment.assign(self.item, self.emp, 4)
        self.login(self.hr)
        self.assertEqual(self.client.post(reverse("assignment_return", args=[assignment.pk])).status_code, 403)
        self.assertEqual(self.stock(), 6)

    def test_employee_with_assignments_cannot_be_deleted(self):
        AssetAssignment.assign(self.item, self.emp, 1)
        self.login(self.hr)
        response = self.client.post(reverse("employees_delete", args=[self.emp.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Employee.objects.filter(pk=self.emp.pk).exists())

    def test_item_with_assignments_cannot_be_deleted(self):
        AssetAssignment.assign(self.item, self.emp, 1)
        self.login(self.inv)
        self.client.post(reverse("inventory_delete", args=[self.item.pk]))
        self.assertTrue(InventoryItem.objects.filter(pk=self.item.pk).exists())


# ---------------------------------------------------------------
# Dashboard and telemetry
# ---------------------------------------------------------------
class DashboardTests(BaseTestCase):
    def node(self, name, cpu, status="Online", memory=0, storage=0):
        return HardwareNode.objects.create(
            node_name=name, ip_address="10.0.0.1", cpu_usage=cpu,
            memory_usage=memory, storage_usage=storage, status=status)

    def test_telemetry_averages_only_online_nodes(self):
        self.node("a", 20, memory=40, storage=10)
        self.node("b", 60, memory=80, storage=30)
        self.node("c", 100, status="Offline", memory=100, storage=100)
        self.login(self.inv)
        context = self.client.get(reverse("dashboard")).context
        self.assertEqual(context["active_nodes"], 2)
        self.assertEqual(context["avg_cpu"], 40)
        self.assertEqual(context["avg_memory"], 60)
        self.assertEqual(context["avg_storage"], 20)

    def test_no_nodes_gives_zero_not_an_error(self):
        self.login(self.inv)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["avg_cpu"], 0)
        self.assertEqual(response.context["active_nodes"], 0)

    def test_low_stock_is_counted(self):
        InventoryItem.objects.create(name="Low", sku="L-1", quantity=1, reorder_level=5)
        self.login(self.inv)
        context = self.client.get(reverse("dashboard")).context
        self.assertEqual(context["low_stock_count"], 1)

    def test_pending_requests_and_active_assignments_are_counted(self):
        PurchaseRequest.objects.create(item=self.item, quantity=1, requested_by=self.mgr)
        AssetAssignment.assign(self.item, self.emp, 1)
        self.login(self.admin)
        context = self.client.get(reverse("dashboard")).context
        self.assertEqual(context["pending_requests"], 1)
        self.assertEqual(context["active_assignments"], 1)

    def test_database_status_is_online(self):
        self.login(self.inv)
        self.assertTrue(self.client.get(reverse("dashboard")).context["db_online"])

    def test_activity_feed_shows_recent_entries(self):
        ActivityLog.objects.create(category="SYSTEM", message="Hello feed")
        self.login(self.inv)
        self.assertContains(self.client.get(reverse("dashboard")), "Hello feed")

    def test_telemetry_page_lists_nodes(self):
        self.node("node-x", 50)
        self.login(self.hr)  # every role may view telemetry
        response = self.client.get(reverse("telemetry"))
        self.assertContains(response, "node-x")
        self.assertEqual(response.context["node_count"], 1)


# ---------------------------------------------------------------
# Reports and CSV export (Objective E)
# ---------------------------------------------------------------
class ReportTests(BaseTestCase):
    def get_csv(self, url_name):
        response = self.client.get(reverse(url_name))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/csv"))
        self.assertIn("attachment", response["Content-Disposition"])
        return list(csv.reader(io.StringIO(response.content.decode())))

    def test_inventory_csv(self):
        self.login(self.inv)
        rows = self.get_csv("export_inventory")
        self.assertEqual(rows[0][:3], ["SKU", "Item", "Category"])
        self.assertEqual(rows[1][0], "LAP-1")

    def test_procurement_csv(self):
        PurchaseRequest.objects.create(item=self.item, supplier=self.supplier, quantity=4, requested_by=self.mgr)
        self.login(self.mgr)
        rows = self.get_csv("export_procurement")
        self.assertEqual(rows[0][0], "Request")
        self.assertEqual(rows[1][1], "Laptop")

    def test_employees_csv(self):
        self.login(self.hr)
        rows = self.get_csv("export_employees")
        self.assertEqual(rows[1][0], "E-1")

    def test_assignments_csv(self):
        AssetAssignment.assign(self.item, self.emp, 2)
        self.login(self.inv)
        rows = self.get_csv("export_assignments")
        self.assertEqual(rows[1][:3], ["Laptop", "Ana Reyes", "2"])

    def test_hr_cannot_download_inventory_csv(self):
        self.login(self.hr)
        self.assertEqual(self.client.get(reverse("export_inventory")).status_code, 403)

    def test_inventory_staff_cannot_download_employee_csv(self):
        self.login(self.inv)
        self.assertEqual(self.client.get(reverse("export_employees")).status_code, 403)

    def test_report_page_numbers(self):
        InventoryItem.objects.create(name="Low", sku="L-1", quantity=1, reorder_level=5)
        self.login(self.admin)
        context = self.client.get(reverse("reports")).context
        self.assertEqual(context["item_count"], 2)
        self.assertEqual(context["units_in_stock"], 11)
        self.assertEqual(len(context["low_stock"]), 1)