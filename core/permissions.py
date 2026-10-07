"""Role-based access control (Objective B).

Roles are Django auth Groups. Superusers count as Administrators.
Edit ACCESS to change who can see or change each module.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

ADMIN = "Administrator"
INVENTORY = "Inventory Staff"
HR = "Human Resource Personnel"
MANAGER = "Department Manager"
ALL_ROLES = [ADMIN, INVENTORY, HR, MANAGER]

_stock = [ADMIN, INVENTORY]

ACCESS = {
    # module:       who can view                        who can add / edit / delete
    "inventory":   {"view": _stock + [MANAGER],         "edit": _stock},
    "categories":  {"view": _stock,                     "edit": _stock},
    "suppliers":   {"view": _stock + [MANAGER],         "edit": _stock},
    "procurement": {"view": _stock + [MANAGER],         "edit": _stock + [MANAGER]},
    "movements":   {"view": _stock + [MANAGER],         "edit": []},
    "resources":   {"view": _stock + [MANAGER],         "edit": _stock},
    "employees":   {"view": [ADMIN, HR, MANAGER],       "edit": [ADMIN, HR]},
    "departments": {"view": [ADMIN, HR, MANAGER],       "edit": [ADMIN, HR]},
    "assignments": {"view": ALL_ROLES,                  "edit": _stock},
    "hardware":    {"view": ALL_ROLES,                  "edit": _stock},
    "telemetry":   {"view": ALL_ROLES,                  "edit": []},
    "reports":     {"view": ALL_ROLES,                  "edit": []},
}


def user_roles(user):
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return set(ALL_ROLES)
    return set(user.groups.values_list("name", flat=True))


def can(user, module, mode="view"):
    return bool(user_roles(user) & set(ACCESS[module][mode]))


def module_required(module, mode="view"):
    """Login required, then the user must hold a role allowed for the module."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not can(request.user, module, mode):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return login_required(wrapper, login_url="login")
    return decorator
