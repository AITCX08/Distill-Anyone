"""Tests for stage-scoped concurrency limits."""

from src.orchestration.resources import ResourceSlots


def test_only_one_asr_task_receives_the_asr_slot():
    slots = ResourceSlots(download=2, asr=1, llm=1)

    assert slots.acquire("tsk_1", "transcribing")
    assert not slots.acquire("tsk_2", "transcribing")
    slots.release("tsk_1", "transcribing")
    assert slots.acquire("tsk_2", "transcribing")


def test_download_slots_are_independent_from_llm_slots():
    slots = ResourceSlots(download=2, asr=1, llm=1)

    assert slots.acquire("tsk_1", "downloading")
    assert slots.acquire("tsk_2", "downloading")
    assert not slots.acquire("tsk_3", "downloading")
    assert slots.acquire("tsk_3", "summarizing")
