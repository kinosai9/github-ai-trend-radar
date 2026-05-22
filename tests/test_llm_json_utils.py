from github_ai_trend_radar.llm.json_utils import extract_json_from_text, parse_json_or_error


def test_json_fence_extract():
    assert extract_json_from_text('```json\n{"ok": true}\n```') == '{"ok": true}'


def test_json_object_inside_text_extract():
    assert extract_json_from_text('before {"ok": true, "nested": {"x": 1}} after') == '{"ok": true, "nested": {"x": 1}}'


def test_parse_json_or_error():
    payload, error = parse_json_or_error('text {"ok": true}')

    assert payload == {"ok": True}
    assert error is None
