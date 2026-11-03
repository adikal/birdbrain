"""BirdBrain dashboard server: a read-only, loopback-only view of the mind.

    birdbrain-dashboard                         # replay recorded runs from data/runs
    birdbrain-dashboard --live --seed 3         # also run a live playroom at real time

Routes (GET only): `/` and static dashboard files, `/api/status`,
`/api/runs`, `/api/runs/<id>`, `/api/runs/<id>/events`, and `/api/events`
(Server-Sent Events from the live run). The server binds to a loopback
address and refuses any other; to view it from another machine, forward the
port over SSH.

In live mode the playroom also publishes `TRUTH` events (true duck and toy
positions) for the viewer's comparison overlay. They go to the event log
only; the mind never receives them.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import mimetypes
import re
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from birdbrain.observability.events import SCHEMA_VERSION
from birdbrain.observability.journal import EventJournal
from birdbrain.observability.store import JsonlRunStore

_CAMERA_FILE = re.compile(r"^[0-9]{8}\.jpg$")


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], dashboard_dir: Path, store: JsonlRunStore,
                 journal: EventJournal | None = None) -> None:
        if not _is_loopback(address[0]):
            raise ValueError("the dashboard binds to loopback only; use an SSH tunnel to reach it remotely")
        super().__init__(address, Handler)
        self.dashboard_dir, self.store, self.journal = dashboard_dir.resolve(), store, journal

    def handle_error(self, request: object, client_address: object) -> None:
        if isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):
            return
        super().handle_error(request, client_address)


class Handler(BaseHTTPRequestHandler):
    server: DashboardServer

    def do_GET(self) -> None:
        if not self._host_allowed():
            self.send_error(HTTPStatus.MISDIRECTED_REQUEST, "unexpected Host header")
            return
        parsed = urlparse(self.path)
        route = parsed.path
        if route == "/api/status":
            journal = self.server.journal
            self._json({"service": "birdbrain-dashboard", "schema_version": SCHEMA_VERSION,
                        "live_run_id": journal.run_id if journal else None,
                        "latest_sequence": journal.latest_sequence if journal else 0})
        elif route == "/api/runs":
            self._json({"live_run_id": self.server.journal.run_id if self.server.journal else None,
                        "runs": self.server.store.list_runs()})
        elif route == "/api/events":
            self._stream()
        elif route.startswith("/api/runs/") and "/camera/" in route:
            self._camera(unquote(route.removeprefix("/api/runs/")))
        elif route.startswith("/api/runs/"):
            self._recorded(unquote(route.removeprefix("/api/runs/")), parse_qs(parsed.query))
        else:
            self._static(route)

    def _host_allowed(self) -> bool:
        """Reject requests whose Host is not this loopback server: a DNS-rebinding page
        would otherwise be able to read run logs through the browser."""
        port = self.server.server_port
        allowed = {f"{h}:{port}" for h in ("127.0.0.1", "localhost", "[::1]")}
        return (self.headers.get("Host") or "") in allowed

    def do_POST(self) -> None:
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED, "read-only")

    do_PUT = do_DELETE = do_PATCH = do_POST

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _recorded(self, suffix: str, query: dict[str, list[str]]) -> None:
        events = suffix.endswith("/events")
        run_id = suffix.removesuffix("/events")
        try:
            if events:
                after = int(query.get("after", ["0"])[0])
                limit = int(query.get("limit", ["10000"])[0])
                self._json({"run_id": run_id,
                            "events": self.server.store.read_events(run_id, after_sequence=after, limit=limit)})
            else:
                summary = self.server.store.get_summary(run_id)
                if summary is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                else:
                    self._json(summary)
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "invalid run id or query")

    def _camera(self, suffix: str) -> None:
        run_id, _, name = suffix.partition("/camera/")
        try:
            folder = self.server.store.run_dir(run_id) / "camera"
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "invalid run id")
            return
        if not _CAMERA_FILE.fullmatch(name) or not (folder / name).is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = (folder / name).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Cache-Control", "max-age=86400, immutable")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream(self) -> None:
        journal = self.server.journal
        if journal is None:
            self.send_error(HTTPStatus.NOT_FOUND, "no live run")
            return
        try:
            sequence = int(self.headers.get("Last-Event-ID", "0"))
        except ValueError:
            sequence = 0
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                events = journal.wait_since(sequence, timeout=10.0)
                if not events:
                    self.wfile.write(b": keepalive\n\n")
                for event in events:
                    data = json.dumps(event.to_dict(), separators=(",", ":"))
                    self.wfile.write(f"id: {event.sequence}\nevent: birdbrain\ndata: {data}\n\n".encode())
                    sequence = event.sequence
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def _static(self, route: str) -> None:
        relative = "index.html" if route == "/" else route.lstrip("/")
        path = (self.server.dashboard_dir / relative).resolve()
        if self.server.dashboard_dir not in path.parents or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def live_loop(session: Any, seconds: float, speed: float, stop: threading.Event,
              camera: Any = None) -> None:
    """Step a playroom at `speed` times real time, publishing truth and camera images
    at 2 Hz for the viewer."""
    t_wall, t_sim, next_truth, next_shot = time.monotonic(), session.t, 0.0, 0.0
    try:
        while session.t < seconds and not stop.is_set():
            session.step()
            if session.t >= next_truth:
                next_truth = session.t + 0.5
                session.journal.publish("TRUTH", sim_time=session.t, payload=session.truth())
            if camera is not None and session.t >= next_shot and session.camera_event(camera):
                next_shot = session.t + 0.5
            ahead = (session.t - t_sim) / speed - (time.monotonic() - t_wall)
            if ahead > 0:
                stop.wait(ahead)
    except Exception as error:  # noqa: BLE001 - the failure is recorded in the run
        session.journal.publish("RUN_FAILED", sim_time=session.t,
                                payload={"error": type(error).__name__, "message": str(error)[:300]})
        return
    finally:
        if camera is not None:
            camera.close()
        session.close()
    session.journal.publish("RUN_STOPPED", sim_time=session.t,
                            payload={"result": session.result(time.monotonic() - t_wall), "truth": session.truth()})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1", help="a loopback address")
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--runs-dir", type=Path, default=Path("data/runs"))
    ap.add_argument("--dashboard-dir", type=Path, default=_default_dashboard_dir())
    ap.add_argument("--live", action="store_true", help="run a live playroom")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seconds", type=float, default=300.0)
    ap.add_argument("--speed", type=float, default=1.0, help="simulated seconds per wall second")
    ap.add_argument("--provider", choices=["local", "bedrock"], default="local")
    ap.add_argument("--needs", action="store_true", help="no task: the duck acts on its needs (Milestone 3)")
    ap.add_argument("--room", choices=["messy", "tidy"], default="messy")
    ap.add_argument("--owner", choices=["none", "basket", "wall", "leave"], default=None,
                    help="Milestone 3b: a scripted owner with this hidden preference")
    ap.add_argument("--no-camera", action="store_true", help="do not render head-camera images")
    args = ap.parse_args()
    if not _is_loopback(args.host):
        ap.error("--host must be a loopback address (127.0.0.1 or ::1); use an SSH tunnel for remote viewing")
    store = JsonlRunStore(args.runs_dir)
    journal, stop = None, threading.Event()
    if args.live:
        from birdbrain.run import PlayroomSession
        journal = EventJournal(run_id=f"live-s{args.seed}-{args.provider}-{int(time.time()) % 10**6}", store=store)
        session = PlayroomSession(args.seed, provider=args.provider, journal=journal, needs=args.needs, room=args.room, owner=args.owner)
        camera = None
        if not args.no_camera:
            from birdbrain.observability.camera import HeadCamera
            camera = HeadCamera(session.world, session.duck, store.run_dir(journal.run_id) / "camera")
        threading.Thread(target=live_loop, args=(session, args.seconds, args.speed, stop, camera),
                         daemon=True).start()
    server = DashboardServer((args.host, args.port), args.dashboard_dir, store, journal)
    print(f"BirdBrain dashboard: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _default_dashboard_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "dashboard" / "index.html").is_file():
            return parent / "dashboard"
    return Path("dashboard")


if __name__ == "__main__":
    main()
