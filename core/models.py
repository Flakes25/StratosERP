from django.db import models


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
    node_name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    cpu_usage = models.FloatField(default=0)
    memory_usage = models.FloatField(default=0)
    storage_usage = models.FloatField(default=0)
    status = models.CharField(max_length=50, default="Online")

    def __str__(self):
        return self.node_name