"""Tests for one-work, checkpointed worker execution."""

import json

from src.orchestration.worker import run_worker


class FakePipeline:
    def __init__(self):
        self.download_calls = 0
        self.clean_calls = 0
        self.summary_calls = 0
        self.write_calls = 0

    def download(self, context):
        self.download_calls += 1
        return {"audio": "media/audio.m4a"}

    def clean(self, context):
        self.clean_calls += 1
        return {"cleaned": "artifacts/cleaned.json"}

    def summarize(self, context):
        self.summary_calls += 1
        return {"knowledge": "artifacts/knowledge.json"}

    def write(self, context):
        self.write_calls += 1
        return {"episode": "artifacts/episode.md"}


def _write_payload(tmp_path, *, task_id):
    work_dir = tmp_path / "worker"
    payload = tmp_path / "payload.json"
    payload.write_text(
        json.dumps({"task_id": task_id, "work_dir": str(work_dir), "source": {"id": "p01"}}),
        "utf-8",
    )
    return payload, work_dir


def _write_checkpoint(work_dir, *, task_id, stage, transcript_verified=False):
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "checkpoint.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "stage": stage,
                "checkpoint_revision": 3,
                "artifacts": {"transcript": "artifacts/transcript.json"},
                "transcript_verified": transcript_verified,
            }
        ),
        "utf-8",
    )


def test_worker_resumes_after_valid_transcript_without_redownloading(tmp_path):
    payload, work_dir = _write_payload(tmp_path, task_id="tsk_1")
    _write_checkpoint(work_dir, task_id="tsk_1", stage="cleaning", transcript_verified=True)
    pipeline = FakePipeline()

    assert run_worker("tsk_1", payload, pipeline=pipeline) == 0
    assert pipeline.download_calls == 0
    assert pipeline.clean_calls == 1
    assert pipeline.summary_calls == 1
    assert pipeline.write_calls == 1

    checkpoint = json.loads((work_dir / "checkpoint.json").read_text("utf-8"))
    assert checkpoint["stage"] == "completed"
    assert checkpoint["checkpoint_revision"] == 6


def test_worker_honors_parent_pause_between_stages(tmp_path):
    payload, work_dir = _write_payload(tmp_path, task_id="tsk_2")
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "control.json").write_text('{"action":"pause"}', "utf-8")
    pipeline = FakePipeline()

    assert run_worker("tsk_2", payload, pipeline=pipeline) == 0
    assert pipeline.download_calls == 0
    checkpoint = json.loads((work_dir / "checkpoint.json").read_text("utf-8"))
    assert checkpoint["stage"] == "paused"
    events = (work_dir / "events.jsonl").read_text("utf-8")
    assert '"status": "paused"' in events


def test_worker_builds_one_pipeline_from_its_payload_when_not_injected(tmp_path):
    payload, _ = _write_payload(tmp_path, task_id="tsk_factory")
    class FullPipeline(FakePipeline):
        def extract_audio(self, context):
            return {}

        def transcribe(self, context):
            return {"transcript": "artifacts/transcript.json"}

    pipeline = FullPipeline()
    built_for = []

    assert run_worker(
        "tsk_factory",
        payload,
        pipeline_factory=lambda value: built_for.append(value["task_id"]) or pipeline,
    ) == 0

    assert built_for == ["tsk_factory"]
    assert pipeline.download_calls == 1
