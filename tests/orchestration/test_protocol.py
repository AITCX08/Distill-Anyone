"""Behavioural tests for the worker-to-manager JSONL boundary."""

import json

import pytest

from src.orchestration.protocol import ProtocolError, parse_worker_event


def test_transfer_event_requires_matching_task_and_nonnegative_values():
    event = parse_worker_event(
        '{"v":1,"type":"transfer","task_id":"tsk_1","completed_bytes":2,"total_bytes":4,"bytes_per_second":1}',
        "tsk_1",
    )

    assert event.kind == "transfer"
    assert event.payload["completed_bytes"] == 2

    with pytest.raises(ProtocolError):
        parse_worker_event(
            '{"v":1,"type":"transfer","task_id":"other","completed_bytes":-1}',
            "tsk_1",
        )


def test_stage_event_rejects_unknown_stage_and_redacts_text_fields():
    event = parse_worker_event(
        '{"v":1,"type":"log","task_id":"tsk_1","line":"SESSDATA=secret"}',
        "tsk_1",
    )

    assert "secret" not in event.payload["line"]

    with pytest.raises(ProtocolError):
        parse_worker_event(
            '{"v":1,"type":"stage","task_id":"tsk_1","stage":"invented"}',
            "tsk_1",
        )


def test_protocol_rejects_oversized_or_invalid_terminal_event():
    oversized = json.dumps(
        {"v": 1, "type": "log", "task_id": "tsk_1", "line": "x" * (16 * 1024)}
    )
    with pytest.raises(ProtocolError):
        parse_worker_event(oversized, "tsk_1")
    with pytest.raises(ProtocolError):
        parse_worker_event(
            '{"v":1,"type":"terminal","task_id":"tsk_1","status":"running"}',
            "tsk_1",
        )
