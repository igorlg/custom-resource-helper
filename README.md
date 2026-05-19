## Custom Resource Helper

Simplify best practice Custom Resource creation, sending responses to CloudFormation and providing exception, timeout 
trapping, and detailed configurable logging.

[![CI](https://github.com/igorlg/custom-resource-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/igorlg/custom-resource-helper/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://github.com/igorlg/custom-resource-helper)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

> **Note**: this is a fork of [aws-cloudformation/custom-resource-helper](https://github.com/aws-cloudformation/custom-resource-helper),
> brought up to date with modern Python tooling, multi-arch CI, and a number of bug fixes from the upstream
> issue tracker.

## Features

* Dead simple to use, reduces the complexity of writing a CloudFormation custom resource
* Guarantees that CloudFormation will get a response even if an exception is raised
* Returns meaningful errors to CloudFormation Stack events in the case of a failure
* Polling enables run times longer than the lambda 15 minute limit
* JSON logging that includes request id's, stack id's and request type to assist in tracing logs relevant to a 
particular CloudFormation event
* Catches function timeouts and sends CloudFormation a failure response
* Static typing (mypy) compatible
* Built-in `test_mode` for unit tests and SAM-local invocations

## Installation

Install into the root folder of your lambda function

```shell
cd my-lambda-function/
pip install crhelper -t .
```

## Example Usage

[This blog](https://aws.amazon.com/blogs/infrastructure-and-automation/aws-cloudformation-custom-resource-creation-with-python-aws-lambda-and-crhelper/) covers usage in more detail.

```python
from crhelper import CfnResource
import logging

logger = logging.getLogger(__name__)
# Initialise the helper, all inputs are optional, this example shows the defaults
helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL', sleep_on_delete=120, ssl_verify=None)

try:
    ## Init code goes here
    pass
except Exception as e:
    helper.init_failure(e)


@helper.create
def create(event, context):
    logger.info("Got Create")
    # Optionally return an ID that will be used for the resource PhysicalResourceId, 
    # if None is returned an ID will be generated. If a poll_create function is defined 
    # return value is placed into the poll event as event['CrHelperData']['PhysicalResourceId']
    #
    # To add response data update the helper.Data dict
    # If poll is enabled data is placed into poll event as event['CrHelperData']
    helper.Data.update({"test": "testdata"})

    # To return an error to cloudformation you raise an exception:
    if not helper.Data.get("test"):
        raise ValueError("this error will show in the cloudformation events log and console.")
    
    return "MyResourceId"


@helper.update
def update(event, context):
    logger.info("Got Update")
    # If the update resulted in a new resource being created, return an id for the new resource. 
    # CloudFormation will send a delete event with the old id when stack update completes


@helper.delete
def delete(event, context):
    logger.info("Got Delete")
    # Delete never returns anything. Should not fail if the underlying resources are already deleted.
    # Desired state.


@helper.poll_create
def poll_create(event, context):
    logger.info("Got create poll")
    # Return a resource id or True to indicate that creation is complete. if True is returned an id 
    # will be generated
    return True


def handler(event, context):
    helper(event, context)
```

### Polling

If you need longer than the max runtime of 15 minutes, you can enable polling by adding additional decorators for 
`poll_create`, `poll_update` or `poll_delete`. When a poll function is defined for `create`/`update`/`delete` the 
function will not send a response to CloudFormation and instead a CloudWatch Events schedule will be created to 
re-invoke the lambda function every 2 minutes. When the function is invoked the matching `@helper.poll_` function will 
be called, logic to check for completion should go here, if the function returns `None` then the schedule will run again 
in 2 minutes. Once complete either return a PhysicalResourceID or `True` to have one generated. The schedule will be 
deleted and a response sent back to CloudFormation. If you use polling the following additional IAM policy must be 
attached to the function's IAM role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "events:PutRule",
        "events:DeleteRule",
        "events:PutTargets",
        "events:RemoveTargets"
      ],
      "Resource": "*"
    }
  ]
}
```
### Certificate Verification
To turn off certification verification, or to use a custom CA bundle path for the underlying boto3 clients used by this library, override the `ssl_verify` argument with the appropriate values.  These can be either:
* `False` - do not validate SSL certificates. SSL will still be used, but SSL certificates will not be verified.
* `path/to/cert/bundle.pem` - A filename of the CA cert bundle to uses. You can specify this argument if you want to use a different CA cert bundle than the one used by botocore.

### Testing crhelper Lambdas

For local invocations (SAM-local, unit tests, ad-hoc Python scripts) you usually
do **not** want crhelper to actually POST to a CloudFormation pre-signed URL.
Pass `test_mode=True` to skip the response and capture it on the helper instead:

```python
from crhelper import CfnResource

helper = CfnResource(test_mode=True)

@helper.create
def create(event, context):
    helper.Data["MyOutput"] = "computed-value"
    return "MyResourceId"

def handler(event, context):
    helper(event, context)

# Drive the handler with a fake event/context, then assert on the response
# that *would* have been sent to CloudFormation:
handler(fake_event, fake_context)

assert helper.LastResponse["Status"] == "SUCCESS"
assert helper.LastResponse["PhysicalResourceId"] == "MyResourceId"
assert helper.LastResponse["Data"]["MyOutput"] == "computed-value"
```

`LastResponse` is `None` until `_send` runs; afterwards it contains the dict
that would have been PUT to `event['ResponseURL']`. With `test_mode=True`,
the HTTPS call itself is skipped entirely.

### Use CDK to deploy a Custom Resource that uses Custom Resource Helper

You can use the [AWS Cloud Development Kit (AWS CDK)](https://docs.aws.amazon.com/cdk/v2/guide/home.html) to deploy a Custom Resource that uses Custom Resource Helper. AWS CDK is an open-source software development framework for defining cloud infrastructure in code and provisioning it through AWS CloudFormation.

> **Important**: `crhelper` is **not** compatible with AWS CDK's [`Provider`](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.custom_resources.Provider.html) construct.
>
> The `Provider` framework deploys an internal "framework" Lambda that wraps your handler and **expects your handler to return a response object** (`{ PhysicalResourceId, Data, NoEcho, ... }`). The framework Lambda then takes care of POSTing to CloudFormation's `ResponseURL` for you.
>
> `crhelper`, in contrast, POSTs directly to `event['ResponseURL']` itself — which is what CloudFormation expects when it invokes a custom-resource Lambda *directly* (i.e. `serviceToken: <lambda_arn>`), but **not** when invoked through the `Provider` framework. Using `crhelper` inside a `Provider`-managed Lambda will cause the response to be sent twice in incompatible formats and the resource will hang.
>
> **If you're using `Provider`:** write a plain handler that returns the response dict; don't use `crhelper`. See AWS CDK's [Custom Resources guide](https://docs.aws.amazon.com/cdk/v2/guide/develop-resources.html).
>
> **If you're using `CustomResource` directly with a `serviceToken`:** `crhelper` is the right fit. See the example below.

#### AWS CDK template example

```python
from aws_cdk import (
    ...
    aws_lambda as _lambda,
    CustomResource,
)

crhelperSumResource = _lambda.Function(...)

customResource = CustomResource(
  self,
  'MyCustomResource',
  serviceToken=crhelperSumResource.function_arn,
  properties={
    'No1': 1,
    'No2': 2,
  },
)
```

## Development

Development tasks are wired up in the project [`Justfile`](./Justfile). With [`uv`](https://docs.astral.sh/uv/) installed:

```shell
uv sync                # install all dev dependencies (test + lint)
just test              # run the test suite on the host Python
just test-cov          # with coverage report
just lint              # ruff + mypy
just lint-fix          # apply ruff's safe auto-fixes
just test-matrix       # run the full CI matrix locally via `act` (requires Docker)
just build             # build wheel + sdist into ./dist
```

The CI workflow at [`.github/workflows/ci.yml`](.github/workflows/ci.yml) is the single source of truth for the test matrix: 8 jobs across `{ubuntu-24.04, ubuntu-24.04-arm} × {python 3.11, 3.12, 3.13, 3.14}`, plus a separate lint job.

## Credits

Decorator implementation inspired by https://github.com/ryansb/cfn-wrapper-python

Log implementation inspired by https://gitlab.com/hadrien/aws_lambda_logging

## License

This library is licensed under the Apache 2.0 License.
