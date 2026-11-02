"""Read-only local HTTP and Server-Sent Events bridge for BirdBrain."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from birdbrain.observability.director import SimulationDirector
from birdbrain.observability.events import SCHEMA_VERSION
from birdbrain.observability.journal import EventJournal


class ObservabilityServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        server_address: tuple[str, int],
        journal: EventJournal,
        dashboard_dir: Path,
    ) -> None:
        super().__init__(server_address, ObservabilityHandler)
        self.journal = journal
        self.dashboard_dir = dashboard_dir.resolve()

    def handle_error(self, request: object, client_address: object) -> None:
        error = sys.exc_info()[1]
        if isinstance(error, (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


class ObservabilityHandler(BaseHTTPRequestHandler):
    server: ObservabilityServer

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/api/status":
            self._send_json(
                {
                    "service": "birdbrain-observability",
                    "schema_version": SCHEMA_VERSION,
                    "run_id": self.server.journal.run_id,
                    "latest_sequence": self.server.journal.latest_sequence,
                    "stream": "/api/events",
                }
            )
        elif route == "/api/snapshot":
            event = self.server.journal.latest("STATE_SNAPSHOT")
            self._send_json(event.to_dict() if event else {}, status=200 if event else 204)
        elif route == "/api/events":
            self._stream_events()
        else:
            self._serve_static(route)

    def do_POST(self) -> None:
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "Bridge is read-only")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _stream_events(self) -> None:
        try:
            sequence = int(self.headers.get("Last-Event-ID", "0"))
        except ValueError:
            sequence = 0
        if sequence == 0:
            sequence = max(0, self.server.journal.latest_sequence - 200)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                events = self.server.journal.wait_since(sequence, timeout=10.0)
                if not events:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                for event in events:
                    encoded = json.dumps(event.to_dict(), separators=(",", ":"))
                    message = (
                        f"id: {event.sequence}\nevent: birdbrain\ndata: {encoded}\n\n"
                    )
                    self.wfile.write(message.encode())
                    sequence = event.sequence
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def _serve_static(self, route: str) -> None:
        relative = "index.html" if route == "/" else route.lstrip("/")
        candidate = (self.server.dashboard_dir / relative).resolve()
        if self.server.dashboard_dir not in candidate.parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = candidate.read_bytes()
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_server(
    *,
    host: str,
    port: int,
    journal: EventJournal,
    dashboard_dir: Path,
) -> ObservabilityServer:
    return ObservabilityServer((host, port), journal, dashboard_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the BirdBrain live dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dashboard-dir", type=Path, default=_default_dashboard_dir())
    args = parser.parse_args()

    journal = EventJournal()
    director = SimulationDirector(journal, seed=args.seed)
    server = build_server(
        host=args.host,
        port=args.port,
        journal=journal,
        dashboard_dir=args.dashboard_dir,
    )
    director.start()
    print(f"BirdBrain dashboard: http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        director.stop()


def _default_dashboard_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "dashboard"


if __name__ == "__main__":
    main()
