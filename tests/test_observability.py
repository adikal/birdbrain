import json
import threading
import urllib.request
from pathlib import Path

from birdbrain.observability import SCHEMA_VERSION, EventJournal, JsonlRunStore
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


def test_jsonl_store_survives_restart_and_indexes_terminal_run(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path / "runs")
    journal = EventJournal(run_id="durable-run", store=store)
    journal.publish("RUN_STARTED", sim_time=0.0, payload={"seed": 7})
    stopped = journal.publish("RUN_STOPPED", sim_time=1.5, payload={"summary": "done"})

    reopened = JsonlRunStore(tmp_path / "runs")
    summary = reopened.get_summary("durable-run")
    assert summary is not None
    assert summary["status"] == "completed"
    assert summary["event_count"] == 2
    assert reopened.list_runs() == [summary]
    assert reopened.read_events("durable-run", after_sequence=1) == [stopped.to_dict()]


def test_store_rejects_unsafe_run_ids(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path / "runs")
    try:
        store.read_events("../outside")
    except ValueError as error:
        assert str(error) == "invalid run id"
    else:
        raise AssertionError("unsafe run id was accepted")


def test_bridge_lists_and_replays_persisted_runs(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path / "runs")
    journal = EventJournal(run_id="bridge-history", store=store)
    event = journal.publish("RUN_STARTED", sim_time=0.0, payload={"seed": 42})
    dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
    server = build_server(
        host="127.0.0.1",
        port=0,
        journal=journal,
        dashboard_dir=dashboard_dir,
        store=store,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(f"{base_url}/api/runs") as response:
            catalog = json.load(response)
        with urllib.request.urlopen(
            f"{base_url}/api/runs/bridge-history/events?limit=10"
        ) as response:
            replay = json.load(response)

        assert catalog["current_run_id"] == "bridge-history"
        assert catalog["runs"][0]["event_count"] == 1
        assert replay["events"] == [event.to_dict()]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_bridge_compares_two_runs(tmp_path: Path) -> None:
    store = JsonlRunStore(tmp_path / "runs")
    left = EventJournal(run_id="left-run", store=store)
    right = EventJournal(run_id="right-run", store=store)
    left.publish("ANOMALY", sim_time=0.1, payload={"code": "slip"})
    left.publish("RUN_STOPPED", sim_time=1.0, payload={})
    right.publish("PLAN_CREATED", sim_time=0.2, payload={"steps": []})
    right.publish("RUN_STOPPED", sim_time=1.0, payload={})

    dashboard_dir = Path(__file__).resolve().parents[1] / "dashboard"
    server = build_server(
        host="127.0.0.1",
        port=0,
        journal=right,
        dashboard_dir=dashboard_dir,
        store=store,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = (
            f"http://127.0.0.1:{server.server_port}"
            "/api/compare?left=left-run&right=right-run"
        )
        with urllib.request.urlopen(url) as response:
            comparison = json.load(response)
        assert comparison["winner"] == "right"
        assert comparison["right_run_id"] == "right-run"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
