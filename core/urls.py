from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="dashboard"),

    # authentication
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html",
                                                redirect_authenticated_user=True,
                                                next_page="dashboard"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # pages
    path("modules/", views.modules, name="modules"),
    path("telemetry/", views.telemetry, name="telemetry"),
    path("reports/", views.reports, name="reports"),

    # actions
    path("procurement/<int:pk>/do/<str:action>/", views.procurement_action, name="procurement_action"),
    path("assignments/new/", views.assignment_create, name="assignments_create"),
    path("assignments/<int:pk>/return/", views.assignment_return, name="assignment_return"),

    # CSV exports
    path("export/inventory.csv", views.export_inventory, name="export_inventory"),
    path("export/procurement.csv", views.export_procurement, name="export_procurement"),
    path("export/employees.csv", views.export_employees, name="export_employees"),
    path("export/assignments.csv", views.export_assignments, name="export_assignments"),
]

# list / create / edit / delete routes for every CRUD module
for key, crud in views.CRUD.items():
    base = key
    urlpatterns.append(path(f"{base}/", crud["list"], name=f"{key}_list"))
    if "create" in crud:
        urlpatterns.append(path(f"{base}/new/", crud["create"], name=f"{key}_create"))
    if "update" in crud:
        urlpatterns.append(path(f"{base}/<int:pk>/edit/", crud["update"], name=f"{key}_update"))
    if "delete" in crud:
        urlpatterns.append(path(f"{base}/<int:pk>/delete/", crud["delete"], name=f"{key}_delete"))
