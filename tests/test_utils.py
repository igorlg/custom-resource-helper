import json
import ssl
import tempfile
from unittest.mock import patch, Mock, ANY, MagicMock

from crhelper import utils

TEST_URL = "https://test_url/this/is/the/url?query=123#aaa"


@patch('crhelper.utils.HTTPSConnection', autospec=True)
def test_send_succeeded_response(https_connection_mock):
    utils._send_response(TEST_URL, {})
    https_connection_mock.assert_called_once_with("test_url", context=ANY)
    https_connection_mock.return_value.request.assert_called_once_with(
        body='{}',
        headers={"content-type": "", "content-length": "2"},
        method="PUT",
        url="/this/is/the/url?query=123#aaa",
    )


@patch('crhelper.utils.HTTPSConnection', autospec=True)
def test_send_failed_response(https_connection_mock):
    utils._send_response(TEST_URL, Mock())
    https_connection_mock.assert_called_once_with("test_url", context=ANY)
    response = json.loads(https_connection_mock.return_value.request.call_args[1]["body"])
    expected_body = '{"Status": "FAILED", "Data": {}, "Reason": "' + response["Reason"] + '"}'
    https_connection_mock.return_value.request.assert_called_once_with(
        body=expected_body,
        headers={"content-type": "", "content-length": str(len(expected_body))},
        method="PUT",
        url="/this/is/the/url?query=123#aaa",
    )


@patch('crhelper.utils.ssl.create_default_context', autospec=True)
@patch('crhelper.utils.HTTPSConnection', autospec=True)
def test_send_response_no_ssl_verify(https_connection_mock, ssl_create_context_mock):
    ctx_mock = Mock()
    ssl_create_context_mock.return_value = ctx_mock
    utils._send_response(TEST_URL, {}, ssl_verify=False)
    https_connection_mock.assert_called_once_with("test_url", context=ctx_mock)
    assert not ctx_mock.check_hostname
    assert ctx_mock.verify_mode == ssl.CERT_NONE


@patch('crhelper.utils.ssl.create_default_context', autospec=True)
@patch('crhelper.utils.HTTPSConnection', autospec=True)
def test_send_response_custom_ca(https_connection_mock, ssl_create_context_mock):
    ctx_mock = Mock()
    ssl_create_context_mock.return_value = ctx_mock
    with tempfile.NamedTemporaryFile() as tmp:
        utils._send_response(TEST_URL, {}, ssl_verify=tmp.name)
    https_connection_mock.assert_called_once_with("test_url", context=ctx_mock)
    ctx_mock.load_verify_locations.assert_called_once_with(cafile=tmp.name)


@patch('crhelper.utils.ssl.create_default_context', autospec=True)
@patch('crhelper.utils.HTTPSConnection', autospec=True)
def test_send_response_non_existant_custom_ca(https_connection_mock, ssl_create_context_mock):
    ctx_mock = Mock()
    ssl_create_context_mock.return_value = ctx_mock
    utils._send_response(TEST_URL, {}, ssl_verify='/invalid/path/to/ca')
    https_connection_mock.assert_called_once_with("test_url", context=ANY)
    ctx_mock.load_verify_locations.assert_not_called()


@patch('crhelper.utils.logger')
@patch('crhelper.utils.HTTPSConnection')
def test_send_response_retry(mock_https_connection, mock_logger):
    # Mock the behavior of HTTPSConnection to fail on the first two attempts
    mock_connection = mock_https_connection.return_value
    mock_connection.getresponse.side_effect = [
        Exception("Unexpected failure sending response to CloudFormation"),
        Exception("Unexpected failure sending response to CloudFormation"),
        MagicMock(reason="OK"),
    ]

    response_url = "https://example.com/response"
    response_body = {"Status": "SUCCESS", "Data": {"Message": "Test message"}}
    ssl_verify = True
    utils._send_response(response_url, response_body, ssl_verify)

    # Two retries, one success
    assert mock_logger.error.call_count == 2
    assert mock_logger.info.call_count == 1
    assert mock_https_connection.call_count == 3
    assert mock_connection.getresponse.call_count == 3


@patch('crhelper.utils.time.sleep')
@patch('crhelper.utils.HTTPSConnection')
def test_send_response_does_not_retry_indefinitely(mock_https_connection, mock_sleep):
    """Persistent failures must not cause unbounded retries (regression).

    The original implementation wrapped the bounded-retry loop in an
    outer `while True` that reset retry_count each iteration, so
    MAX_RETRIES was only the inner-batch bound. Total retries were
    unbounded: on persistent network failures _send_response would
    consume the entire Lambda timeout rather than giving up.
    """
    mock_connection = mock_https_connection.return_value

    # Always fail. SystemExit (a BaseException, not Exception) is a
    # safety net so this test cannot hang the suite if the bug is
    # still present -- _send_response's `except Exception` won't
    # catch it.
    safety_cap = utils.MAX_RETRIES * 4

    def fail_or_bail(*args, **kwargs):
        if mock_connection.getresponse.call_count > safety_cap:
            raise SystemExit("retried too many times")
        raise Exception("simulated network failure")

    mock_connection.getresponse.side_effect = fail_or_bail

    try:
        utils._send_response("https://example.com/path", {})
    except SystemExit:
        pass  # captured at safety cap; assertion below surfaces the bug

    assert mock_connection.getresponse.call_count <= utils.MAX_RETRIES, (
        "_send_response made {actual} attempts, but MAX_RETRIES is {limit}. "
        "This indicates unbounded retries (outer `while True` resetting the counter)."
    ).format(
        actual=mock_connection.getresponse.call_count,
        limit=utils.MAX_RETRIES,
    )
