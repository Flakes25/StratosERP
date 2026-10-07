import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.db.models import Avg, Count, F, ProtectedError, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AssignmentForm, CategoryForm, DepartmentForm, EmployeeForm, HardwareNodeForm,
    InventoryItemForm, PurchaseRequestForm, ResourceForm, SupplierForm,
)
from .models import (
    ActivityLog, AssetAssignment, Category, Department, Employee, HardwareNode,
    Infrastructure, InventoryItem, PurchaseRequest, Resource, StockMovement, Supplier,
)
from .permissions import ADMIN, INVENTORY, MANAGER, can, module_required, user_roles


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------
class Badge:
    """A table cell rendered as a coloured pill. tone: good / warn / bad / info."""
    def __init__(self, text, tone=""):
        self.text, self.tone = text, tone

    def __str__(self):
        return str(self.text)


def log(request, category, message):
    ActivityLog.objects.create(
        category=category.upper()[:30],
        message=message[:255],
        detail=f"by {request.user.get_username()}",
    )


def _date(dt):
    return timezone.localtime(dt).strftime("%b %d, %Y") if dt else "—"


def _database_online():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def _telemetry():
    online = HardwareNode.objects.filter(status=HardwareNode.ONLINE)
    avg = online.aggregate(cpu=Avg("cpu_usage"), memory=Avg("memory_usage"), storage=Avg("storage_usage"))
    return {
        "avg_cpu": avg["cpu"] or 0,
        "avg_memory": avg["memory"] or 0,
        "avg_storage": avg["storage"] or 0,
        "active_nodes": online.count(),
    }


# ---------------------------------------------------------------
# Generic CRUD factory: one list / create / edit / delete set per module
# ---------------------------------------------------------------
def make_crud(key, model, form_class, title, columns, row, *, eyebrow="Operations",
              search=(), related=(), create="auto", edit=True, delete=True,
              export=None, actions=None, on_create=None):
    singular = model._meta.verbose_name.title()
    list_name = f"{key}_list"

    @module_required(key, "view")
    def list_view(request):
        qs = model.objects.select_related(*related)
        q = request.GET.get("q", "").strip()
        if q and search:
            cond = Q()
            for field in search:
                cond |= Q(**{f"{field}__icontains": q})
            qs = qs.filter(cond)
        editable = can(request.user, key, "edit")
        rows = []
        for obj in qs:
            rows.append({
                "cells": row(obj),
                "actions": actions(obj, request.user) if actions else [],
                "edit_url": reverse(f"{key}_update", args=[obj.pk]) if edit and editable else None,
                "delete_url": reverse(f"{key}_delete", args=[obj.pk]) if delete and editable else None,
            })
        return render(request, "core/list.html", {
            "title": title, "eyebrow": eyebrow, "columns": columns, "rows": rows,
            "colspan": len(columns) + 1, "search": bool(search), "q": q,
            "can_create": bool(create) and editable,
            "create_url": reverse(f"{key}_create") if create else None,
            "export_url": reverse(export) if export else None,
        })

    @module_required(key, "edit")
    def create_view(request):
        form = form_class(request.POST or None)
        if request.method == "POST" and form.is_valid():
            obj = form.save(commit=False)
            if on_create:
                on_create(obj, request)
            obj.save()
            form.save_m2m()
            log(request, title, f"{singular} created: {obj}")
            messages.success(request, f"{singular} created.")
            return redirect(list_name)
        return render(request, "core/form.html", {
            "form": form, "title": f"New {singular.lower()}", "back_url": reverse(list_name),
            "submit": f"Create {singular.lower()}",
        })

    @module_required(key, "edit")
    def update_view(request, pk):
        obj = get_object_or_404(model, pk=pk)
        form = form_class(request.POST or None, instance=obj)
        if request.method == "POST" and form.is_valid():
            obj = form.save()
            log(request, title, f"{singular} updated: {obj}")
            messages.success(request, f"{singular} saved.")
            return redirect(list_name)
        return render(request, "core/form.html", {
            "form": form, "title": f"Edit {singular.lower()}", "back_url": reverse(list_name),
            "submit": "Save changes",
        })

    @module_required(key, "edit")
    def delete_view(request, pk):
        obj = get_object_or_404(model, pk=pk)
        if request.method == "POST":
            label = str(obj)
            try:
                obj.delete()
            except ProtectedError:
                messages.error(request, f"{label} can't be deleted because other records depend on it.")
            else:
                log(request, title, f"{singular} deleted: {label}")
                messages.success(request, f"{singular} deleted.")
            return redirect(list_name)
        return render(request, "core/confirm_delete.html", {
            "object": obj, "title": f"Delete {singular.lower()}", "back_url": reverse(list_name),
        })

    views = {"list": list_view}
    if create == "auto":
        views["create"] = create_view
    if edit:
        views["update"] = update_view
    if delete:
        views["delete"] = delete_view
    return views


# ---------------------------------------------------------------
# Row builders
# ---------------------------------------------------------------
_PR_TONE = {"Pending": "warn", "Approved": "info", "Rejected": "bad", "Received": "good"}
_NODE_TONE = {"Online": "good", "Offline": "bad", "Maintenance": "warn"}


def _inventory_row(i):
    return [i.sku, i.name, i.category or "—", i.quantity, i.reorder_level, i.location or "—",
            Badge("Low stock", "bad") if i.is_low_stock else Badge("In stock", "good")]


def _procurement_row(p):
    return [f"PR-{p.pk}", p.item.name, p.supplier or "—", p.quantity,
            p.requested_by or "—", Badge(p.status, _PR_TONE.get(p.status, "")), _date(p.created_at)]


def _procurement_actions(p, user):
    roles = user_roles(user)
    out = []
    if p.status == PurchaseRequest.PENDING and roles & {ADMIN, MANAGER}:
        out.append({"label": "Approve", "tone": "good", "url": reverse("procurement_action", args=[p.pk, "approve"])})
        out.append({"label": "Reject", "tone": "bad", "url": reverse("procurement_action", args=[p.pk, "reject"])})
    if p.status == PurchaseRequest.APPROVED and roles & {ADMIN, INVENTORY}:
        out.append({"label": "Mark received", "tone": "info", "url": reverse("procurement_action", args=[p.pk, "receive"])})
    return out


def _assignment_row(a):
    return [a.item.name, a.employee.full_name, a.quantity, _date(a.assigned_at),
            Badge("Assigned", "info") if a.is_active else f"Returned {_date(a.returned_at)}"]


def _assignment_actions(a, user):
    if a.is_active and can(user, "assignments", "edit"):
        return [{"label": "Return", "tone": "good", "url": reverse("assignment_return", args=[a.pk])}]
    return []


def _on_request_create(obj, request):
    obj.requested_by = request.user


CRUD = {
    "inventory": make_crud(
        "inventory", InventoryItem, InventoryItemForm, "Inventory",
        ["SKU", "Item", "Category", "Qty", "Reorder at", "Location", "Status"], _inventory_row,
        eyebrow="Asset control", search=("name", "sku", "location"), related=("category",),
        export="export_inventory"),
    "categories": make_crud(
        "categories", Category, CategoryForm, "Categories", ["Name", "Items"],
        lambda c: [c.name, c.items.count()], eyebrow="Asset control", search=("name",)),
    "suppliers": make_crud(
        "suppliers", Supplier, SupplierForm, "Suppliers", ["Supplier", "Contact", "Email", "Phone"],
        lambda s: [s.name, s.contact_person or "—", s.email or "—", s.phone or "—"],
        eyebrow="Procurement", search=("name", "contact_person")),
    "procurement": make_crud(
        "procurement", PurchaseRequest, PurchaseRequestForm, "Purchase requests",
        ["Request", "Item", "Supplier", "Qty", "Requested by", "Status", "Date"], _procurement_row,
        eyebrow="Procurement", related=("item", "supplier", "requested_by"),
        export="export_procurement", actions=_procurement_actions, on_create=_on_request_create),
    "movements": make_crud(
        "movements", StockMovement, None, "Stock movements",
        ["Date", "Item", "Type", "Qty", "Note", "By"],
        lambda m: [_date(m.created_at), m.item.name,
                   Badge(m.get_movement_type_display(), "good" if m.movement_type == "IN" else "warn"),
                   m.quantity, m.note or "—", m.created_by or "—"],
        eyebrow="Asset control", related=("item", "created_by"), create=None, edit=False, delete=False),
    "resources": make_crud(
        "resources", Resource, ResourceForm, "Resources",
        ["Name", "Category", "Qty", "Status", "Description"],
        lambda r: [r.resource_name, r.category, r.quantity, r.status, (r.description or "—")[:60]],
        eyebrow="Management", search=("resource_name", "category")),
    "employees": make_crud(
        "employees", Employee, EmployeeForm, "Employees",
        ["ID", "Name", "Department", "Position", "Email", "Status"],
        lambda e: [e.employee_id, e.full_name, e.department or "—", e.position or "—", e.email or "—",
                   Badge("Active", "good") if e.is_active else Badge("Inactive", "bad")],
        eyebrow="People", search=("employee_id", "first_name", "last_name", "position"),
        related=("department",), export="export_employees"),
    "departments": make_crud(
        "departments", Department, DepartmentForm, "Departments", ["Department", "Employees", "Description"],
        lambda d: [d.name, d.employees.count(), (d.description or "—")[:80]],
        eyebrow="People", search=("name",)),
    "assignments": make_crud(
        "assignments", AssetAssignment, None, "Asset assignments",
        ["Item", "Employee", "Qty", "Assigned", "Status"], _assignment_row,
        eyebrow="Asset control", related=("item", "employee"), create="custom", edit=False, delete=False,
        export="export_assignments", actions=_assignment_actions),
    "hardware": make_crud(
        "hardware", HardwareNode, HardwareNodeForm, "Hardware nodes",
        ["Node", "IP address", "CPU", "Memory", "Storage", "Status"],
        lambda n: [n.node_name, n.ip_address, f"{n.cpu_usage:.0f}%", f"{n.memory_usage:.0f}%",
                   f"{n.storage_usage:.0f}%", Badge(n.status, _NODE_TONE.get(n.status, ""))],
        eyebrow="Infrastructure", search=("node_name", "ip_address")),
}


# ---------------------------------------------------------------
# Procurement and assignment actions
# ---------------------------------------------------------------
@module_required("procurement", "edit")
@require_POST
def procurement_action(request, pk, action):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    roles = user_roles(request.user)
    if action in ("approve", "reject"):
        if not roles & {ADMIN, MANAGER}:
            raise PermissionDenied
        if pr.status != PurchaseRequest.PENDING:
            messages.error(request, "Only pending requests can be approved or rejected.")
        else:
            pr.status = PurchaseRequest.APPROVED if action == "approve" else PurchaseRequest.REJECTED
            pr.save(update_fields=["status"])
            log(request, "Procurement", f"PR-{pr.pk} {pr.status.lower()}")
            messages.success(request, f"Request {pr.status.lower()}.")
    elif action == "receive":
        if not roles & {ADMIN, INVENTORY}:
            raise PermissionDenied
        if pr.status != PurchaseRequest.APPROVED:
            messages.error(request, "Only approved requests can be received.")
        else:
            pr.mark_received(request.user)
            log(request, "Inventory", f"PR-{pr.pk} received: +{pr.quantity} {pr.item.name}")
            messages.success(request, f"Stock updated: +{pr.quantity} {pr.item.name}.")
    else:
        raise Http404
    return redirect("procurement_list")


@module_required("assignments", "edit")
def assignment_create(request):
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            a = AssetAssignment.assign(d["item"], d["employee"], d["quantity"], request.user)
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            log(request, "Assignments", f"{a.quantity} x {a.item.name} assigned to {a.employee.full_name}")
            messages.success(request, "Asset assigned. Inventory updated.")
            return redirect("assignments_list")
    return render(request, "core/form.html", {
        "form": form, "title": "Assign an asset", "back_url": reverse("assignments_list"),
        "submit": "Assign asset",
    })


@module_required("assignments", "edit")
@require_POST
def assignment_return(request, pk):
    a = get_object_or_404(AssetAssignment, pk=pk)
    if a.is_active:
        a.return_asset(request.user)
        log(request, "Assignments", f"{a.quantity} x {a.item.name} returned by {a.employee.full_name}")
        messages.success(request, "Asset returned. Inventory updated.")
    return redirect("assignments_list")


# ---------------------------------------------------------------
# Dashboard, telemetry, reports
# ---------------------------------------------------------------
@login_required(login_url="login")
def home(request):
    hardware_nodes = HardwareNode.objects.all()
    low_stock = InventoryItem.objects.filter(quantity__lte=F("reorder_level"))
    context = {
        "resources": Resource.objects.all(),
        "infrastructure": Infrastructure.objects.all(),
        "hardware_nodes": hardware_nodes,
        "latest_node": hardware_nodes.first(),
        "inventory_count": InventoryItem.objects.count(),
        "employee_count": Employee.objects.filter(is_active=True).count(),
        "low_stock_items": low_stock[:5],
        "low_stock_count": low_stock.count(),
        "pending_requests": PurchaseRequest.objects.filter(status=PurchaseRequest.PENDING).count(),
        "active_assignments": AssetAssignment.objects.filter(returned_at__isnull=True).count(),
        "recent_activity": ActivityLog.objects.all()[:5],
        "db_online": _database_online(),
        **_telemetry(),
    }
    return render(request, "core/dashboard.html", context)


MODULES = [
    ("inventory", "Inventory", "inventory_list", "Items, stock levels and reorder alerts."),
    ("categories", "Categories", "categories_list", "Group inventory items by type."),
    ("suppliers", "Suppliers", "suppliers_list", "Vendors you buy stock from."),
    ("procurement", "Purchase requests", "procurement_list", "Request, approve and receive stock."),
    ("movements", "Stock movements", "movements_list", "A record of every stock in and out."),
    ("assignments", "Asset assignments", "assignments_list", "Equipment issued to employees."),
    ("resources", "Resources", "resources_list", "Organizational resources and their status."),
    ("employees", "Employees", "employees_list", "Employee records and departments."),
    ("departments", "Departments", "departments_list", "The department directory."),
    ("hardware", "Hardware nodes", "hardware_list", "Register and edit monitored nodes."),
    ("telemetry", "Telemetry", "telemetry", "Live CPU, memory and storage across nodes."),
    ("reports", "Reports", "reports", "Summaries and CSV downloads."),
]


def _add_url(key):
    try:
        return reverse(f"{key}_create")
    except NoReverseMatch:
        return None


@login_required(login_url="login")
def modules(request):
    tiles = []
    for key, label, url_name, desc in MODULES:
        if can(request.user, key, "view"):
            add_url = _add_url(key) if can(request.user, key, "edit") else None
            tiles.append({"label": label, "desc": desc, "url": reverse(url_name), "add_url": add_url})
    return render(request, "core/modules.html", {"modules": tiles})


@module_required("telemetry", "view")
def telemetry(request):
    nodes = HardwareNode.objects.all()
    return render(request, "core/telemetry.html", {
        "nodes": nodes, "node_count": nodes.count(), **_telemetry(),
    })


@module_required("reports", "view")
def reports(request):
    low_stock = InventoryItem.objects.filter(quantity__lte=F("reorder_level")).select_related("category")
    return render(request, "core/reports.html", {
        "item_count": InventoryItem.objects.count(),
        "units_in_stock": InventoryItem.objects.aggregate(n=Sum("quantity"))["n"] or 0,
        "low_stock": low_stock,
        "pending_requests": PurchaseRequest.objects.filter(status=PurchaseRequest.PENDING).count(),
        "active_assignments": AssetAssignment.objects.filter(returned_at__isnull=True).count(),
        "by_category": Category.objects.annotate(
            items_n=Count("items"), units=Sum("items__quantity")).order_by("name"),
        "by_department": Department.objects.annotate(people=Count("employees")).order_by("name"),
        "exports": [
            {"label": "Inventory", "url": "export_inventory", "module": "inventory"},
            {"label": "Procurement", "url": "export_procurement", "module": "procurement"},
            {"label": "Employees", "url": "export_employees", "module": "employees"},
            {"label": "Asset assignments", "url": "export_assignments", "module": "assignments"},
        ],
    })


# ---------------------------------------------------------------
# CSV export (Objective E)
# ---------------------------------------------------------------
def _csv(filename, header, rows):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(header)
    writer.writerows(rows)
    return response


@module_required("inventory", "view")
def export_inventory(request):
    rows = [[i.sku, i.name, i.category or "", i.quantity, i.reorder_level, i.location,
             "LOW" if i.is_low_stock else "OK"]
            for i in InventoryItem.objects.select_related("category")]
    return _csv("inventory.csv", ["SKU", "Item", "Category", "Quantity", "Reorder level", "Location", "Status"], rows)


@module_required("procurement", "view")
def export_procurement(request):
    rows = [[f"PR-{p.pk}", p.item.name, p.supplier or "", p.quantity, p.requested_by or "",
             p.status, _date(p.created_at)]
            for p in PurchaseRequest.objects.select_related("item", "supplier", "requested_by")]
    return _csv("procurement.csv", ["Request", "Item", "Supplier", "Quantity", "Requested by", "Status", "Date"], rows)


@module_required("employees", "view")
def export_employees(request):
    rows = [[e.employee_id, e.full_name, e.department or "", e.position, e.email,
             e.date_hired, "Active" if e.is_active else "Inactive"]
            for e in Employee.objects.select_related("department")]
    return _csv("employees.csv", ["ID", "Name", "Department", "Position", "Email", "Date hired", "Status"], rows)


@module_required("assignments", "view")
def export_assignments(request):
    rows = [[a.item.name, a.employee.full_name, a.quantity, _date(a.assigned_at),
             _date(a.returned_at) if a.returned_at else "Assigned"]
            for a in AssetAssignment.objects.select_related("item", "employee")]
    return _csv("assignments.csv", ["Item", "Employee", "Quantity", "Assigned", "Returned"], rows)
