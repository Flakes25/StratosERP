from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import HardwareNode


class Command(BaseCommand):
    help = "Mark Online nodes as Offline when they have not reported for N minutes."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=2)

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(minutes=options["minutes"])
        count = HardwareNode.objects.filter(
            status=HardwareNode.ONLINE, last_seen__lt=cutoff
        ).update(status=HardwareNode.OFFLINE)
        self.stdout.write(self.style.SUCCESS(f"{count} node(s) marked Offline."))
