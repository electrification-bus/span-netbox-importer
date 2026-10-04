# Changelog

All notable changes to `span-netbox-importer` are recorded here. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- The importer no longer needs a SPAN-API-Client-Docs checkout. It reads `span-auth`'s credential file (`~/.span-auth.json`, or `SPAN_AUTH_FILE`) itself, downloads and caches each panel's CA certificate in the same cache `span-auth` uses (`~/.span-ca-certs`, or `SPAN_CA_CERT_DIR`), and `--discover` browses mDNS for `_ebus._tcp` instead of running `span-discover`, listening for 6 seconds rather than 3, which missed a panel in testing. `span-auth setup` is still how credentials are created.
- A CA certificate download that is not a PEM certificate is rejected rather than cached, and the download uses 10-second connect and read timeouts.
- An invalid credential file, or one whose `panels` is empty or null, is reported as an error instead of ending in a traceback.

### Removed

- `SPAN_API_DIR`.

## [0.2.0] - 2026-10-04

### Changed

- **Requires SPAN Panel firmware r202633 or later.** The importer reads the parent/child eBus data model (`info/data-model-version` `1.0`): it walks the panel device's `children`, keeps the children whose `$description` type is `energy.ebus.device.circuit`, and reads each circuit's `info/name`, `info/spaces`, `breaker/rating` and `breaker/poles`. Panel fields come from the panel's `info/*` and `breaker/rating`. Version 0.1.0 read the flat model, which r202633 no longer publishes, so on current firmware it found no data. Circuit device IDs are the circuit UUIDs the flat model used as node IDs, so existing power feeds are matched by `panel_circuit_id` and updated in place.
- `panel_space` is the first position in `info/spaces`, and `is_duplex` is true for two or more `breaker/poles`.
- Power feed voltage follows the pole count: 240 V for two or more poles, otherwise 120 V, on both create and update. Feeds were previously always created at 120 V.
- The device type created with `--create-devices` is named from the panel's MQTT `info/model`, with underscores as spaces (`MAIN_32` becomes `MAIN 32`). The mDNS `model` record is used only when MQTT supplies none. Existing devices keep their device type.

### Added

- `SPAN_API_DIR` locates the SPAN-API-Client-Docs checkout that provides `span_auth_utils` and `span-discover`.
- `--version`.
- CI: ruff lint and format, pytest on Python 3.10 and 3.12, and a GitHub Release on each `vX.Y.Z` tag.
- `LICENSE` (MIT), `CONTRIBUTING.md` and this changelog.

### Fixed

- A failed or partial MQTT collection no longer overwrites NetBox with defaults. A panel is skipped and counted as an error when the broker connection fails or when its data-model version, hardware version or main breaker rating is not received, and a circuit missing its name, spaces or pole count is skipped with a warning. Previously the panel's `main_breaker_rating` could be saved as 0 and its `hardware_version` as empty.
- The summary's created and updated counts for power panels and devices. New objects were counted as updated.
- A failure to create a custom field raised `NameError` instead of printing a warning, because `pynetbox` was not bound at module level.
- A missing `span_auth_utils` now says to set `SPAN_API_DIR` instead of suggesting `pip install`.

## [0.1.0] - 2026-02-08

### Added

- Initial importer: SPAN panels as NetBox power panels and circuits as power feeds over the panel's eBus MQTT broker, with optional devices, interfaces, MAC and IP addresses from mDNS.

[Unreleased]: https://github.com/electrification-bus/span-netbox-importer/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/electrification-bus/span-netbox-importer/releases/tag/v0.2.0
[0.1.0]: https://github.com/electrification-bus/span-netbox-importer/commit/c89279e
