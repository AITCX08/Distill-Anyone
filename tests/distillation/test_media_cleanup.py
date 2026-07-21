import json

from src.distillation.processors import safe_cleanup_media


def test_media_is_not_deleted_until_transcript_reopens_valid(tmp_path):
    media = tmp_path / "media.mp4"
    media.write_bytes(b"media")
    transcript = tmp_path / "transcript.json"
    transcript.write_text('{"full_text": "", "segments": []}', "utf-8")

    assert safe_cleanup_media(media, transcript_path=transcript) is False
    assert media.exists()


def test_valid_reopened_transcript_allows_cleanup(tmp_path):
    media = tmp_path / "media.mp4"
    media.write_bytes(b"media")
    transcript = tmp_path / "transcript.json"
    transcript.write_text(
        json.dumps(
            {
                "full_text": "complete",
                "segments": [{"text": "complete", "start": 0, "end": 1}],
            }
        ),
        "utf-8",
    )

    assert safe_cleanup_media(media, transcript_path=transcript) is True
    assert not media.exists()

