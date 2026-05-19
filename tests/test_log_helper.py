import json
import logging

from crhelper.log_helper import JsonFormatter, setupLogger


# --- setupLogger ----------------------------------------------------------

def test_no_formatting_when_formatter_cls_is_none():
    logger = logging.getLogger('1')
    logger.addHandler(logging.StreamHandler())
    orig_formatters = [h.formatter for h in logging.root.handlers]
    setupLogger(level='DEBUG', formatter_cls=None, boto_level='CRITICAL')
    new_formatters = [h.formatter for h in logging.root.handlers]
    assert orig_formatters == new_formatters


def test_explicit_boto_level_is_applied():
    logger = logging.getLogger('2')
    logger.addHandler(logging.StreamHandler())
    setupLogger(level='DEBUG', formatter_cls=None, boto_level='CRITICAL')
    for name in ['boto', 'boto3', 'botocore', 'urllib3']:
        assert logging.getLogger(name).level == logging.CRITICAL


def test_json_formatter_applied_to_all_root_handlers():
    logger = logging.getLogger('3')
    logger.addHandler(logging.StreamHandler())
    setupLogger(level='DEBUG', formatter_cls=JsonFormatter, RequestType='ContainerInit')
    for handler in logging.root.handlers:
        assert isinstance(handler.formatter, JsonFormatter)


def test_implicit_boto_level_inherits_root_level():
    logger = logging.getLogger('4')
    logger.addHandler(logging.StreamHandler())
    setupLogger(level='DEBUG', formatter_cls=JsonFormatter, RequestType='ContainerInit')
    for name in ['boto', 'boto3', 'botocore', 'urllib3']:
        assert logging.getLogger(name).level == logging.DEBUG


# --- JsonFormatter --------------------------------------------------------

def _capture_formatted(caplog, msg, **setup_kwargs):
    """Configure the root logger with JsonFormatter, log msg, return the
    formatted JSON-decoded record (dict)."""
    logger = logging.getLogger()
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    setupLogger(level='DEBUG', formatter_cls=JsonFormatter, **setup_kwargs)
    with caplog.at_level(logging.DEBUG):
        logger.info(msg)
    return json.loads(handler.formatter.format(caplog.records[0]))


def test_json_formatter_emits_expected_keys(caplog):
    log_dict = _capture_formatted(caplog, "test", RequestType='ContainerInit')
    assert list(log_dict.keys()) == ["timestamp", "level", "location", "RequestType", "message"]


def test_json_formatter_parses_message_as_json_when_possible(caplog):
    log_dict = _capture_formatted(caplog, "{}", RequestType='ContainerInit')
    assert log_dict["message"] == {}


def test_json_formatter_includes_exception(caplog):
    logger = logging.getLogger()
    logger.addHandler(logging.StreamHandler())
    setupLogger(level='DEBUG', formatter_cls=JsonFormatter, RequestType='ContainerInit')
    with caplog.at_level(logging.DEBUG):
        try:
            1 + 't'
        except Exception:
            logger.info("[]", exc_info=True)
    handler = logging.root.handlers[0]
    log_dict = json.loads(handler.formatter.format(caplog.records[0]))
    assert "exception" in log_dict
