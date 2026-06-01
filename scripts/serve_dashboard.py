from __future__ import annotations

import argparse
import http.server
import socket
import socketserver
from functools import partial
from pathlib import Path


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "README.md").exists() and (candidate / "src").exists():
            return candidate
    return current.parents[1]


def find_available_port(preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"No available port found from {preferred_port} to {preferred_port + 49}.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve the generated Claims Denials dashboard locally.")
    parser.add_argument("--port", type=int, default=8055, help="Preferred local port.")
    parser.add_argument("--host", default="127.0.0.1", help="Host/interface to bind.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = find_project_root()
    dashboard = root / "reports" / "dashboard" / "claims_denials_revenue_cycle_dashboard.html"
    if not dashboard.exists():
        print("Dashboard not found. Build it first with:")
        print("  python scripts\\run_claims_denials_pipeline.py")
        return 1

    port = find_available_port(args.port)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    with socketserver.ThreadingTCPServer((args.host, port), handler) as server:
        server.allow_reuse_address = True
        print("Claims Denials dashboard is running locally:")
        print(f"  http://{args.host}:{port}/reports/dashboard/claims_denials_revenue_cycle_dashboard.html")
        print("Press Ctrl+C to stop the server.")
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

