from src.meeting.models import TranscriptLine, MeetingTranscript, MeetingMinutes


def test_meeting_transcript_defaults_and_full_text():
    t = MeetingTranscript()
    assert t.title == ""
    assert t.keywords == []
    assert t.speakers == []
    assert t.lines == []
    assert t.full_text == ""

    t.lines = [
        TranscriptLine(speaker="说话人 1", timestamp="00:03", text="你好"),
        TranscriptLine(speaker="说话人 2", timestamp="00:42", text="在的"),
    ]
    assert t.full_text == "说话人 1 00:03 你好\n说话人 2 00:42 在的"


def test_meeting_minutes_defaults():
    m = MeetingMinutes()
    assert m.meeting_title == ""
    assert m.participants == []
    assert m.outline == []
    assert m.todos == []
    assert m.keywords == []
    assert m.summary_intro == ""
