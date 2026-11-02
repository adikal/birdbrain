import json
import threading
import urllib.request
from pathlib import Path

from birdbrain.observability import SCHEMA_VERSION, EventJournal
from birdbrain.observability.server import build_server


def test_event_journal_orders_and_replays_versioned_events() -> None:
    journal = EventJournal(run_id="test-run", capacity=2)
    first = journal.publish("RUN_STARTED", sim_time=0.0, payload={"seed": 42})
    second = journal.publish("STATE_SNAPSHOT", sim_time=0.1, payload={"mode": "idle"})

    assert first.schema_version == SCHEMA_VERSION
    assert second.sequence == first.sequence + 1
    assert journal.since(first.sequence) == [second]
    assert journal.latest("STATE_SNAPSHOT") == second


def test_read_only_bridge_reports_status_and_latest_snapshot() -> None:
    journal = EventJournal(run_id="bridge-test")
    snapshot = journal.publish(
        "STATE_SNAPSHOT", sim_time=1.25, payload={"duck": {"position": [0, 0, 0.2]}}
    )
    dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
    server = build_server(
        host="127.0.0.1", port=0, journal=journal, dashboard_dir=dashboard_dir
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(f"{base_url}/api/status") as response:
            status = json.load(response)
        with urllib.request.urlopen(f"{base_url}/api/snapshot") as response:
            latest = json.load(response)

        assert status["schema_version"] == SCHEMA_VERSION
        assert status["run_id"] == "bridge-test"
        assert latest == snapshot.to_dict()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
