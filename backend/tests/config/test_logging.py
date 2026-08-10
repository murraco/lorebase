import json
import logging
import sys

from config.logging import JSONFormatter


def _record(**overrides) -> logging.LogRecord:
    defaults = dict(
        name="lorebase.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="something happened",
        args=(),
        exc_info=None,
    )
    defaults.update(overrides)
    return logging.LogRecord(**defaults)


def test_formats_a_plain_message_as_one_json_object() -> None:
    payload = json.loads(JSONFormatter().format(_record()))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "lorebase.test"
    assert payload["message"] == "something happened"
    assert "exception" not in payload


def test_message_args_are_interpolated_before_serializing() -> None:
    record = _record(msg="user %s did %s", args=("mauricio", "a thing"))

    payload = json.loads(JSONFormatter().format(record))

    assert payload["message"] == "user mauricio did a thing"


def test_exception_info_is_included_when_present() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record(exc_info=sys.exc_info())

    payload = json.loads(JSONFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]
