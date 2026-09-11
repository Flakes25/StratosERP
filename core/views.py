from django.shortcuts import render
from .models import Resource, Infrastructure, HardwareNode


def dashboard(request):
    resources = Resource.objects.count()
    infrastructure = Infrastructure.objects.count()
    hardware_nodes = HardwareNode.objects.count()

    return render(request, "core/dashboard.html", {
        "resources": resources,
        "infrastructure": infrastructure,
        "hardware_nodes": hardware_nodes,
    })