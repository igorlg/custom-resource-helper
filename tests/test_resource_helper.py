import copy
import threading
from unittest.mock import call, patch, Mock

import pytest

import crhelper


# Canonical test events for the three CFN custom-resource lifecycle phases.
# Tests should consume these via the `events` fixture rather than directly,
# so that mutation in one test doesn't leak into another.
_TEST_EVENTS = {
    "Create": {
        "RequestType": "Create",
        "RequestId": "test-event-id",
        "StackId": "arn/test-stack-id/guid",
        "LogicalResourceId": "TestResourceId",
        "ResponseURL": "response_url",
    },
    "Update": {
        "RequestType": "Update",
        "RequestId": "test-event-id",
        "StackId": "test-stack-id",
        "LogicalResourceId": "TestResourceId",
        "PhysicalResourceId": "test-pid",
        "ResponseURL": "response_url",
    },
    "Delete": {
        "RequestType": "Delete",
        "RequestId": "test-event-id",
        "StackId": "test-stack-id",
        "LogicalResourceId": "TestResourceId",
        "PhysicalResourceId": "test-pid",
        "ResponseURL": "response_url",
    },
}


@pytest.fixture
def events():
    """Fresh deep copy of the canonical test events per test. Avoids the
    cross-test mutation hazard that the original module-level dict had."""
    return copy.deepcopy(_TEST_EVENTS)


@pytest.fixture
def mock_context():
    """Lambda context double; tests can override return values per scenario."""
    ctx = Mock()
    ctx.function_name = "test-function"
    ctx.aws_request_id = "test-request-id"
    ctx.get_remaining_time_in_millis = Mock(return_value=9000)
    return ctx


@pytest.fixture(autouse=True)
def aws_region_env(monkeypatch):
    """All tests run with AWS_REGION set so boto3 client creation succeeds."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")


# --- __init__ -------------------------------------------------------------

@patch('crhelper.log_helper.setupLogger', return_value=None)
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
def test_init(mock_method):
    crhelper.resource_helper.CfnResource()
    mock_method.assert_called_once_with('DEBUG', boto_level='ERROR', formatter_cls=None)

    crhelper.resource_helper.CfnResource(json_logging=True)
    mock_method.assert_called_with('DEBUG', boto_level='ERROR', RequestType='ContainerInit')


@patch('crhelper.log_helper.setupLogger', return_value=None)
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
def test_init_failure(mock_method):
    mock_method.side_effect = Exception("test")
    c = crhelper.resource_helper.CfnResource(json_logging=True)
    assert c._init_failed


@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._polling_init', Mock())
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send')
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
@patch('crhelper.resource_helper.CfnResource._wrap_function', Mock())
def test_init_failure_call(mock_send, events, mock_context):
    c = crhelper.resource_helper.CfnResource()
    c.init_failure(Exception('TestException'))

    c.__call__(events["Create"], mock_context)

    assert mock_send.call_args_list == [call('FAILED', 'TestException')]


# --- __call__ -------------------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._polling_init', Mock())
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
@patch('crhelper.resource_helper.CfnResource._wrap_function', Mock())
@patch('crhelper.resource_helper.CfnResource._cfn_response', return_value=None)
def test_call(cfn_response_mock, events, mock_context):
    c = crhelper.resource_helper.CfnResource()
    create_event = events["Create"]

    c.__call__(create_event, mock_context)
    assert c._send_response
    cfn_response_mock.assert_called_once_with(create_event)

    # SAM-local mode short-circuits polling.
    c._sam_local = True
    c._poll_enabled = Mock(return_value=True)
    c._polling_init = Mock()
    c.__call__(create_event, mock_context)
    c._polling_init.assert_not_called()
    assert len(cfn_response_mock.call_args_list) == 1

    # Outside SAM-local with polling enabled, polling_init is called and
    # cfn_response is NOT called for that invocation.
    c._sam_local = False
    c._send_response = False
    c.__call__(create_event, mock_context)
    c._polling_init.assert_called()
    assert len(cfn_response_mock.call_args_list) == 1

    # Delete events trigger _wait_for_cwlogs.
    delete_event = events["Delete"]
    c._wait_for_cwlogs = Mock()
    c._poll_enabled = Mock(return_value=False)
    c.__call__(delete_event, mock_context)
    c._wait_for_cwlogs.assert_called()

    # Exceptions in cfn_response are reported via _send.
    c._send = Mock()
    cfn_response_mock.side_effect = Exception("test")
    c.__call__(delete_event, mock_context)
    c._send.assert_called_with('FAILED', "test")


@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._polling_init', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
@patch('crhelper.resource_helper.CfnResource._wrap_function', Mock())
@patch('crhelper.resource_helper.CfnResource._cfn_response', Mock(return_value=None))
def test_wait_for_cwlogs(mock_context):
    c = crhelper.resource_helper.CfnResource()
    c._context = mock_context

    sleep_mock = Mock()
    c._wait_for_cwlogs(sleep=sleep_mock)
    sleep_mock.assert_not_called()

    # With more remaining time than _sleep_on_delete, we sleep.
    mock_context.get_remaining_time_in_millis.return_value = 140000
    c._wait_for_cwlogs(sleep=sleep_mock)
    sleep_mock.assert_called_once()


# --- polling --------------------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
@patch('crhelper.resource_helper.CfnResource._wrap_function', Mock())
@patch('crhelper.resource_helper.CfnResource._cfn_response', Mock())
def test_polling_init(events):
    c = crhelper.resource_helper.CfnResource()
    event = events['Create']
    c._setup_polling = Mock()
    c._remove_polling = Mock()

    # Initial create with no CrHelperPoll: setup polling.
    c._polling_init(event)
    c._setup_polling.assert_called_once()
    c._remove_polling.assert_not_called()
    assert c.PhysicalResourceId is None

    # Status FAILED on the same instance: still no extra setup_polling call.
    c.Status = 'FAILED'
    c._setup_polling.assert_called_once()

    # Fresh instance, event with CrHelperPoll, PhysicalResourceId=None: no setup.
    c = crhelper.resource_helper.CfnResource()
    event = events['Create']
    c._setup_polling = Mock()
    c._remove_polling = Mock()
    event['CrHelperPoll'] = "Some stuff"
    c.PhysicalResourceId = None
    c._polling_init(event)
    c._remove_polling.assert_not_called()
    c._setup_polling.assert_not_called()

    # Status FAILED with CrHelperPoll: remove polling.
    c.Status = 'FAILED'
    c._polling_init(event)
    c._remove_polling.assert_called_once()
    c._setup_polling.assert_not_called()

    # Reset to non-FAILED but with a real PhysicalResourceId: still removed.
    c.Status = ''
    c.PhysicalResourceId = "some-id"
    c._remove_polling.assert_called()
    c._setup_polling.assert_not_called()


# --- _cfn_response --------------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
@patch('crhelper.resource_helper.CfnResource._wrap_function', Mock())
def test_cfn_response(events):
    c = crhelper.resource_helper.CfnResource()
    event = events['Create']
    c._send = Mock()

    # No PhysicalResourceId set -> generated from event.
    assert c.PhysicalResourceId == ''
    c._cfn_response(event)
    c._send.assert_called_once()
    assert c.PhysicalResourceId.startswith('test-stack-id_TestResourceId_')

    # Existing string PhysicalResourceId is preserved.
    c._send = Mock()
    c.PhysicalResourceId = 'testpid'
    c._cfn_response(event)
    c._send.assert_called_once()
    assert c.PhysicalResourceId == 'testpid'

    # PhysicalResourceId == True triggers generation.
    c._send = Mock()
    c.PhysicalResourceId = True
    c._cfn_response(event)
    c._send.assert_called_once()
    assert c.PhysicalResourceId.startswith('test-stack-id_TestResourceId_')

    # Empty string + event has PhysicalResourceId -> use event's.
    c._send = Mock()
    c.PhysicalResourceId = ''
    event['PhysicalResourceId'] = 'pid-from-event'
    c._cfn_response(event)
    c._send.assert_called_once()
    assert c.PhysicalResourceId == 'pid-from-event'


# --- decorated user function wrapping ------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
def test_wrap_function():
    c = crhelper.resource_helper.CfnResource()

    def returns_pid(e, c):
        return 'testpid'

    c._wrap_function(returns_pid)
    assert c.PhysicalResourceId == 'testpid'
    assert c.Status != 'FAILED'

    def raises(e, c):
        raise Exception('test exception')

    c._wrap_function(raises)
    assert c.Status == 'FAILED'
    assert c.Reason == 'test exception'


# --- _send ----------------------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
def test_send():
    c = crhelper.resource_helper.CfnResource()
    send_response_mock = Mock()
    c._send(send_response=send_response_mock)
    send_response_mock.assert_called_once()


# --- timeout watchdog -----------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', return_value=None)
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
def test_timeout(mock_send):
    c = crhelper.resource_helper.CfnResource()
    c._timeout()
    mock_send.assert_called_with('FAILED', "Execution timed out")


@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
def test_set_timeout(mock_context):
    c = crhelper.resource_helper.CfnResource()
    c._context = mock_context

    c._set_timeout()
    expected = threading.Timer(1000, lambda: None)
    assert type(c._timer) is type(expected)
    expected.cancel()
    c._timer.cancel()


# --- response cleanup -----------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
def test_cleanup_response():
    c = crhelper.resource_helper.CfnResource()
    c.Data = {"CrHelperPoll": 1, "CrHelperPermission": 2, "CrHelperRule": 3}
    c._cleanup_response()
    assert c.Data == {}


# --- _remove_polling ------------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
def test_remove_polling(mock_context):
    c = crhelper.resource_helper.CfnResource()
    c._context = mock_context

    c._events_client.remove_targets = Mock()
    c._events_client.delete_rule = Mock()
    c._lambda_client.remove_permission = Mock()

    # With no CrHelperRule/Permission in event, _remove_polling logs errors
    # but does not call any AWS client.
    c._remove_polling()
    c._events_client.remove_targets.assert_not_called()
    c._events_client.delete_rule.assert_not_called()
    c._lambda_client.remove_permission.assert_not_called()

    # With CrHelperRule and CrHelperPermission set, the corresponding
    # AWS client methods are called.
    c._event["CrHelperRule"] = "1/2"
    c._event["CrHelperPermission"] = "1/2"
    c._remove_polling()
    c._events_client.remove_targets.assert_called()
    c._events_client.delete_rule.assert_called()
    c._lambda_client.remove_permission.assert_called()


# --- _setup_polling -------------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
@patch('crhelper.resource_helper.CfnResource._rand_string', Mock(return_value='PLURAL=1'))
def test_setup_polling(events, mock_context):
    c = crhelper.resource_helper.CfnResource()
    c._context = mock_context
    c._event = events["Update"]
    c._lambda_client.add_permission = Mock()
    c._events_client.put_rule = Mock(
        return_value={"RuleArn": "arn:aws:lambda:blah:blah:function:blah/blah"}
    )
    c._events_client.put_targets = Mock()

    c._setup_polling()

    c._events_client.put_targets.assert_called()
    c._events_client.put_rule.assert_called_with(
        Name='TestResourceIdPLURAL=1',
        ScheduleExpression='rate(2 minutes)',
        State='ENABLED',
    )
    c._lambda_client.add_permission.assert_called()


@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
@patch('crhelper.resource_helper.CfnResource._rand_string', Mock(return_value='PLURAL=0'))
def test_setup_polling_plural_0(events, mock_context):
    c = crhelper.resource_helper.CfnResource(polling_interval=1)
    c._context = mock_context
    c._event = events["Update"]
    c._lambda_client.add_permission = Mock()
    c._events_client.put_rule = Mock(
        return_value={"RuleArn": "arn:aws:lambda:blah:blah:function:blah/blah"}
    )
    c._events_client.put_targets = Mock()

    c._setup_polling()

    c._events_client.put_targets.assert_called()
    c._events_client.put_rule.assert_called_with(
        Name='TestResourceIdPLURAL=0',
        ScheduleExpression='rate(1 minute)',
        State='ENABLED',
    )
    c._lambda_client.add_permission.assert_called()


# --- decorator wrappers ---------------------------------------------------

@patch('crhelper.log_helper.setupLogger', Mock())
@patch('crhelper.resource_helper.CfnResource._poll_enabled', Mock(return_value=False))
@patch('crhelper.resource_helper.CfnResource._wait_for_cwlogs', Mock())
@patch('crhelper.resource_helper.CfnResource._send', Mock())
@patch('crhelper.resource_helper.CfnResource._set_timeout', Mock())
def test_wrappers():
    c = crhelper.resource_helper.CfnResource()

    def func():
        pass

    for f in ["create", "update", "delete", "poll_create", "poll_update", "poll_delete"]:
        assert getattr(c, "_%s_func" % f) is None
        getattr(c, f)(func)
        assert getattr(c, "_%s_func" % f) is func
