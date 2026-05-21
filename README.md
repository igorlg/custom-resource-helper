# Custom Resource Helper (archived)

> **This repository is archived.** The work that started here as a fork of
> [`aws-cloudformation/custom-resource-helper`][upstream] has moved to a
> ground-up rewrite under a new name and PyPI distribution:
>
> ## → [github.com/igorlg/cfn-handler](https://github.com/igorlg/cfn-handler) ←
>
> ```sh
> pip install cfn-handler
> # or with uv:
> uv add cfn-handler
> ```
>
> The new project is `Apache-2.0` licensed (preserving Amazon's original
> attribution per §4) and ships its first stable release as `cfn-handler 1.0.0`
> on PyPI: <https://pypi.org/project/cfn-handler/>

[upstream]: https://github.com/aws-cloudformation/custom-resource-helper

## Why the move?

The fork (`igorlg/custom-resource-helper`) accumulated 14 PRs that closed
long-standing upstream issues plus a complete tooling modernization (uv,
pyproject + hatchling, ruff, mypy strict, GitHub Actions matrix, release-please).
Continuing to call it `crhelper` while the codebase, public API conventions,
and release cadence had all diverged from the upstream felt dishonest. A
rename to `cfn-handler` with a fresh `1.0.0` clarifies both the identity and
the maintenance commitment.

## Migration for users

The public API of `cfn-handler` is intentionally similar to `crhelper`'s, so
a port is mostly a rename:

```diff
-from crhelper import CfnResource
-helper = CfnResource()
+from cfn_handler import CustomResource
+resource = CustomResource()

-@helper.create
+@resource.create
 def on_create(event, context):
     ...
```

See the new repo's [README][new-readme] and
[CHANGELOG][new-changelog] for full details, including the list of
upstream issues carried forward, the new lifecycle decorator names,
and the `LambdaContext` Protocol type.

[new-readme]: https://github.com/igorlg/cfn-handler/blob/main/README.md
[new-changelog]: https://github.com/igorlg/cfn-handler/blob/main/CHANGELOG.md

## What about this repository?

This repo is read-only. Issues and PRs filed here will not be triaged.
Please open them at <https://github.com/igorlg/cfn-handler/issues> instead.
