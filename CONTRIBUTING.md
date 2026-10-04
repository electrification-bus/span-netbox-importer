# Contributing to span-netbox-importer

Thanks for your interest in contributing! `span-netbox-importer` models SPAN smart electrical panels in [NetBox](https://netboxlabs.com/): panels as power panels and circuits as power feeds, read from each panel's local MQTT broker via the [SPAN API](https://github.com/spanio/SPAN-API-Client-Docs).

## How to contribute

### Discussions

Use [Discussions](https://github.com/electrification-bus/span-netbox-importer/discussions) for open-ended questions about how SPAN data should map onto NetBox objects, setup questions, and proposed changes worth aligning on before writing code.

### Issues

Use [Issues](https://github.com/electrification-bus/span-netbox-importer/issues) for actionable changes:

- Bug reports with reproduction steps: panel firmware version (`info/firmware-version`), NetBox version, the command run, and `--verbose` output.
- Concrete feature requests with a clear scope.
- Documentation gaps.

### Pull requests

Pull requests are welcome.

- For small fixes (a mapping correction with a test, a docs fix), open a PR directly. For substantive changes (a new NetBox object type, a change to a custom field, a new dependency), open a Discussion or Issue first.
- **Follow the SPAN API documentation.** Topics, property names and value formats come from [SPAN-API-Client-Docs](https://github.com/spanio/SPAN-API-Client-Docs). Classify devices by their `$description` type and treat device IDs as opaque.
- **NetBox data is the user's.** Existing objects are matched by `serial_number` (power panels) and `panel_circuit_id` (power feeds) and updated in place. Power panel names are kept; power feed names follow the panel's circuit names. A change that would rewrite more of an existing record needs a stated reason in the PR.
- **Never commit credentials or captured panel data.** Broker passwords, API tokens and real panel captures stay out of the repo; tests use synthetic values.
- **Lint and test before sending.** Run `ruff check .`, `ruff format --check .` and `pytest` locally; CI runs them, with pytest on Python 3.10 and 3.12.
- Add a `CHANGELOG.md` entry under `[Unreleased]` describing what changed.
- **Keep comments to a minimum.** Prefer self-explanatory code, with comments reserved for non-obvious *why*.

## Releases

A maintainer bumps `__version__` in `span-netbox-importer`, moves the `[Unreleased]` section of `CHANGELOG.md` under a new `## [X.Y.Z] - YYYY-MM-DD` heading, merges, and pushes a `vX.Y.Z` tag on the merged commit. The release workflow checks the tag against `__version__` and the CHANGELOG date against the current UTC date, then publishes a GitHub Release with that CHANGELOG section as its notes.

## Code of conduct

Be respectful and constructive. We appreciate everyone who files an issue, starts a discussion, or sends a pull request.

## Maintenance posture

`span-netbox-importer` is an alpha project. Updates and maintenance, including responses to issues, take place on an "as time and resources permit" basis.
