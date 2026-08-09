"""Bilibili downloader telemetry at the worker protocol boundary."""

import json

from src.orchestration.worker import run_worker


class FakeBilibiliPipeline:
    def download(self, context):
        context.emit_transfer(25, 100, 25)
        return {"audio": "media/audio.wav"}

    def extract_audio(self, context):
        return {}

    def transcribe(self, context):
        return {"transcript": "artifacts/transcript.json"}

    def clean(self, context):
        return {"cleaned": "artifacts/cleaned.json"}

    def summarize(self, context):
        return {"knowledge": "artifacts/knowledge.json"}

    def write(self, context):
        return {"episode": "artifacts/episode.md"}


def test_bilibili_worker_forwards_download_hook_as_transfer_event(tmp_path):
    work_dir = tmp_path / "worker"
    payload = tmp_path / "payload.json"
    payload.write_text(
        json.dumps({"task_id": "tsk_bili", "work_dir": str(work_dir), "source": {"id": "BV1"}}),
        "utf-8",
    )

    assert run_worker("tsk_bili", payload, pipeline=FakeBilibiliPipeline()) == 0
    events = [json.loads(line) for line in (work_dir / "events.jsonl").read_text("utf-8").splitlines()]
    transfer = next(event for event in events if event["type"] == "transfer")
    assert transfer["total_bytes"] == 100
    assert transfer["bytes_per_second"] == 25
    assert all(event["type"] != "transfer" for event in events[events.index(transfer) + 1 :])
