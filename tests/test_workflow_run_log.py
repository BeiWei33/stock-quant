from __future__ import annotations

from datetime import datetime, timedelta

from quant.core.models import WorkflowLock, WorkflowRun
from quant.core.persistence.sqlite_store import SqliteStore


def test_store_persists_and_loads_latest_workflow_run(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    first = WorkflowRun(
        run_id="run-1",
        workflow_name="daily",
        status="RUNNING",
        started_at=datetime(2024, 1, 1, 17, 0, 0),
        summary_path="a.json",
    )
    second = WorkflowRun(
        run_id="run-2",
        workflow_name="daily",
        status="SUCCESS",
        started_at=datetime(2024, 1, 2, 17, 0, 0),
        ended_at=datetime(2024, 1, 2, 17, 1, 0),
        summary_path="b.json",
    )

    store.save_workflow_run(first)
    store.save_workflow_run(second)

    latest = store.load_latest_workflow_run("daily")
    assert latest is not None
    assert latest.run_id == "run-2"
    assert latest.status == "SUCCESS"


def test_store_updates_existing_workflow_run_status(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    run = WorkflowRun(
        run_id="run-1",
        workflow_name="daily",
        status="RUNNING",
        started_at=datetime(2024, 1, 1, 17, 0, 0),
    )
    store.save_workflow_run(run)
    store.save_workflow_run(
        WorkflowRun(
            run_id="run-1",
            workflow_name="daily",
            status="FAILED",
            started_at=run.started_at,
            ended_at=datetime(2024, 1, 1, 17, 1, 0),
            error_msg="boom",
        )
    )

    latest = store.load_latest_workflow_run("daily")
    assert latest is not None
    assert latest.status == "FAILED"
    assert latest.error_msg == "boom"


def test_workflow_lock_blocks_reentry_and_releases(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    now = datetime(2024, 1, 1, 17, 0, 0)
    lock = WorkflowLock(
        workflow_name="daily",
        run_id="run-1",
        acquired_at=now,
        expires_at=now + timedelta(minutes=30),
    )

    assert store.acquire_workflow_lock(lock)
    assert not store.acquire_workflow_lock(
        WorkflowLock(
            workflow_name="daily",
            run_id="run-2",
            acquired_at=now + timedelta(minutes=1),
            expires_at=now + timedelta(minutes=31),
        )
    )
    store.release_workflow_lock("daily", "run-1")
    assert store.acquire_workflow_lock(
        WorkflowLock(
            workflow_name="daily",
            run_id="run-3",
            acquired_at=now + timedelta(minutes=2),
            expires_at=now + timedelta(minutes=32),
        )
    )


def test_workflow_lock_expires(tmp_path) -> None:
    store = SqliteStore(tmp_path / "paper.sqlite3")
    store.init_schema()
    now = datetime(2024, 1, 1, 17, 0, 0)
    assert store.acquire_workflow_lock(
        WorkflowLock(
            workflow_name="daily",
            run_id="run-1",
            acquired_at=now,
            expires_at=now + timedelta(minutes=1),
        )
    )

    assert store.acquire_workflow_lock(
        WorkflowLock(
            workflow_name="daily",
            run_id="run-2",
            acquired_at=now + timedelta(minutes=2),
            expires_at=now + timedelta(minutes=32),
        )
    )
