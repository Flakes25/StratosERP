"""StratosERP telemetry agent.

Run it on any machine you want to monitor. It reports CPU, memory and disk usage
to your StratosERP server every few seconds.

    pip install psutil
    python telemetry_agent.py --url http://127.0.0.1:8000 --key YOUR_TELEMETRY_API_KEY

The key must match TELEMETRY_API_KEY in the server's settings.
"""
import argparse
import json
import socket
import time
import urllib.error
import urllib.request

import psutil


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no packet is actually sent
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def sample(name):
    return {
        "node_name": name,
        "ip_address": local_ip(),
        "cpu_usage": psutil.cpu_percent(interval=1),
        "memory_usage": psutil.virtual_memory().percent,
        "storage_usage": psutil.disk_usage("/").percent,
        "status": "Online",
    }


def send(url, key, payload):
    request = urllib.request.Request(
        url.rstrip("/") + "/api/telemetry/",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-API-Key": key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


def main():
    parser = argparse.ArgumentParser(description="Report this machine's usage to StratosERP.")
    parser.add_argument("--url", required=True, help="e.g. http://127.0.0.1:8000")
    parser.add_argument("--key", required=True, help="the server's TELEMETRY_API_KEY")
    parser.add_argument("--name", default=socket.gethostname(), help="node name (default: hostname)")
    parser.add_argument("--interval", type=int, default=10, help="seconds between reports")
    args = parser.parse_args()

    print(f"Reporting {args.name} to {args.url} every {args.interval}s. Ctrl+C to stop.")
    while True:
        payload = sample(args.name)
        try:
            status = send(args.url, args.key, payload)
            print(f"[{time.strftime('%H:%M:%S')}] sent cpu={payload['cpu_usage']}% "
                  f"mem={payload['memory_usage']}% disk={payload['storage_usage']}% -> {status}")
        except urllib.error.HTTPError as err:
            print(f"Server rejected the report: {err.code} {err.read().decode()[:120]}")
        except (urllib.error.URLError, OSError) as err:
            print(f"Could not reach the server: {err}")
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
