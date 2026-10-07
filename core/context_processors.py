from .permissions import ACCESS, can, user_roles


def roles(request):
    """Makes can_view / can_edit available in every template."""
    user = request.user
    if not user.is_authenticated:
        return {}
    return {
        "user_roles": sorted(user_roles(user)),
        "can_view": {m: can(user, m, "view") for m in ACCESS},
        "can_edit": {m: can(user, m, "edit") for m in ACCESS},
    }
