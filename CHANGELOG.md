# Changelog

All notable changes to this fork of `crhelper` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-05-19

First release of this fork. Baselined against upstream
[`aws-cloudformation/custom-resource-helper`](https://github.com/aws-cloudformation/custom-resource-helper)
@ `2.0.12` (commit `b07bd4e`).

### Added

- `CfnResource(test_mode=True)` and `helper.LastResponse` for local
  invocations (SAM-local, unit tests, ad-hoc Python). Captures the
  response body that would have been sent to CloudFormation rather than
  POSTing it. Closes upstream
  [#52](https://github.com/aws-cloudformation/custom-resource-helper/issues/52),
  [#54](https://github.com/aws-cloudformation/custom-resource-helper/issues/54).

### Changed

- Build system migrated from `setup.py` to `pyproject.toml` (PEP 621);
  license metadata uses PEP 639 SPDX form.
- **Python floor raised to 3.11** (was 3.6 in upstream classifiers).
  3.11–3.14 supported and tested.
- CI on `{ubuntu-24.04, ubuntu-24.04-arm} × {3.11, 3.12, 3.13, 3.14}`
  GitHub Actions matrix; replaces the now-defunct Travis configuration.
- Tests modernized to plain pytest functions; shared mutable state
  replaced with fixtures so tests are order-independent.
- ruff and mypy enforced in CI.
- Stub typing widened: `log_level` and `boto_level` accept `int | str`
  (matches stdlib `logging.Logger.setLevel`). Closes upstream
  [#66](https://github.com/aws-cloudformation/custom-resource-helper/issues/66).
- README polished: fork note, refreshed badges, expanded
  [CDK Provider compatibility](https://github.com/aws-cloudformation/custom-resource-helper/issues/78)
  warning, new "Tips" section covering already-supported features that
  weren't documented (`Reason`, `NoEcho`, `helper.Data` lifecycle).
  Closes upstream
  [#19](https://github.com/aws-cloudformation/custom-resource-helper/issues/19),
  [#36](https://github.com/aws-cloudformation/custom-resource-helper/issues/36),
  [#62](https://github.com/aws-cloudformation/custom-resource-helper/issues/62),
  [#78](https://github.com/aws-cloudformation/custom-resource-helper/issues/78).

### Fixed

- **Unbounded retry loop in `_send_response`**: the outer `while True`
  reset the retry counter every iteration, so `MAX_RETRIES` only
  bounded a single inner batch and total retries were unbounded. On
  persistent failures (VPC misconfigurations, S3 endpoint policies)
  Lambdas burned their entire timeout instead of giving up. Closes
  upstream
  [#20](https://github.com/aws-cloudformation/custom-resource-helper/issues/20),
  [#34](https://github.com/aws-cloudformation/custom-resource-helper/issues/34),
  [#39](https://github.com/aws-cloudformation/custom-resource-helper/issues/39),
  [#51](https://github.com/aws-cloudformation/custom-resource-helper/issues/51).
- **`init_failure()` skipped PhysicalResourceId resolution**, sending
  FAILED responses with empty PID and leaving stacks in
  ROLLBACK_FAILED. Now mirrors `_cfn_response`: prefer the event's PID
  on Update/Delete, generate one on Create. Closes upstream
  [#7](https://github.com/aws-cloudformation/custom-resource-helper/issues/7),
  [#67](https://github.com/aws-cloudformation/custom-resource-helper/issues/67).
- **`_set_timeout` and `_wait_for_cwlogs` raised AttributeError** when
  context wasn't a real `LambdaContext` (SAM-local, tests, third-party
  wrappers passing a dict). Both methods now degrade gracefully via a
  shared helper that returns `None` when remaining-time isn't
  available. Closes upstream
  [#76](https://github.com/aws-cloudformation/custom-resource-helper/issues/76).
- **`test_remove_polling`** was passing by accident: an
  `assertRaises(Exception)` was catching an unrelated `AssertionError`
  raised by an `assertEqual` inside the with-block. Replaced with
  direct assertions that exercise the real behaviour.

### Removed

- `setup.py`, `requirements.txt`, `.coveragerc`, `.travis.yml` —
  consolidated into `pyproject.toml` and GitHub Actions.

### Internal

- `Justfile` for local task running.
- `.actrc` for running the CI workflow locally via `act`.
- `[dependency-groups]` (PEP 735) for dev tooling: `test`, `lint`, and
  a `dev` meta-group.
- `uv.lock` committed for reproducible builds.

[2.1.0]: https://github.com/igorlg/custom-resource-helper/releases/tag/v2.1.0
