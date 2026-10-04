# SPAN NetBox Importer

[![Release](https://img.shields.io/github/v/release/electrification-bus/span-netbox-importer)](https://github.com/electrification-bus/span-netbox-importer/releases)
[![Test](https://github.com/electrification-bus/span-netbox-importer/actions/workflows/test.yml/badge.svg)](https://github.com/electrification-bus/span-netbox-importer/actions/workflows/test.yml)
[![Lint](https://github.com/electrification-bus/span-netbox-importer/actions/workflows/lint.yml/badge.svg)](https://github.com/electrification-bus/span-netbox-importer/actions/workflows/lint.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![NetBox](https://img.shields.io/badge/NetBox-4.7-blue)](https://netboxlabs.com/)

Import SPAN electrical panel and circuit data into [NetBox](https://netboxlabs.com/), creating power panels and power feeds with detailed custom field data.

## Prerequisites

- Python 3.10+
- `openssl` on `PATH`, to check cached CA certificates for expiry
- SPAN Panel firmware r202633 or later (eBus data model `1.0`, parent/child devices)
- SPAN credentials configured via `span-auth setup` (from [SPAN-API](https://github.com/spanio/SPAN-API-Client-Docs))
- NetBox instance with API access
- Network access to your SPAN panel(s)

## Installation

```bash
git clone https://github.com/electrification-bus/span-netbox-importer.git
cd span-netbox-importer
pip install -r requirements.txt
```

## Configuration

### SPAN Credentials

Before using the importer, configure credentials for your SPAN panel(s):

```bash
# From the scripts directory
./span-auth setup

# Or for a specific panel
./span-auth setup ab-1234-c5d67
```

This stores credentials in `~/.span-auth.json`.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NETBOX_URL` | Yes | NetBox instance URL (e.g., `https://netbox.example.com`) |
| `NETBOX_TOKEN` | Yes | NetBox API token with write permissions |
| `NETBOX_SITE` | Yes | Site name where panels will be created |
| `NETBOX_LOCATION` | No | Optional location within the site |
| `SPAN_AUTH_FILE` | No | Override credential file path (default: `~/.span-auth.json`) |
| `SPAN_CA_CERT_DIR` | No | Override the CA certificate cache, shared with `span-auth` (default: `~/.span-ca-certs`) |

Example:

```bash
export NETBOX_URL="https://netbox.example.com"
export NETBOX_TOKEN="your-api-token-here"
export NETBOX_SITE="Home"
export NETBOX_LOCATION="Garage"
```

## Usage

```bash
span-netbox-importer [OPTIONS]

Options:
  --dry-run           Show what would be done without making changes
  --panel SERIAL      Import specific panel (can be repeated)
  --all-panels        Import all configured panels
  --discover          Import panels advertising eBus over mDNS (_ebus._tcp)
  --create-devices    Also create device objects with interfaces and IPs
  --verbose, -v       Verbose output
  --timeout SECONDS   MQTT data collection timeout (default: 10)
  --version           Show version
  --help              Show help
```

### Examples

```bash
# Preview what would be imported (dry run)
./span-netbox-importer --all-panels --dry-run

# Import all configured panels
./span-netbox-importer --all-panels

# Import a specific panel
./span-netbox-importer --panel ab-1234-c5d67

# Import multiple specific panels
./span-netbox-importer --panel ab-1234-c5d67 --panel xy-9876-z4321

# Verbose output for troubleshooting
./span-netbox-importer --panel ab-1234-c5d67 --verbose

# Discover panels and import (requires credentials to be pre-configured)
./span-netbox-importer --discover

# Create device objects with network interfaces and IP addresses
./span-netbox-importer --all-panels --create-devices
```

## NetBox Custom Fields

The importer automatically creates the following custom fields in NetBox:

### Power Panel Custom Fields

| Field | Type | Description |
|-------|------|-------------|
| `serial_number` | Text | Device serial number |
| `vendor_name` | Text | Equipment vendor/manufacturer |
| `hardware_version` | Text | Hardware revision identifier |
| `main_breaker_rating` | Integer | Main breaker rating in amps |
| `upstream_panel` | Object (Power Panel) | Power panel feeding this panel |
| `downstream_panel` | Object (Power Panel) | Power panel fed by this panel |
| `upstream_source` | Text | Description of upstream power source |
| `associated_device` | Object (Device) | Device object for smart panel controller |

### Power Feed Custom Fields

| Field | Type | Description |
|-------|------|-------------|
| `panel_circuit_id` | Text | Circuit device ID from the panel (e.g., `ac3dccda46a94b98878a227df6fed588`) |
| `panel_space` | Integer | First physical space the circuit occupies in the panel |
| `is_duplex` | Boolean | Whether this is a duplex (two or more poles) circuit |

## How It Works

1. **Load Configuration**: Reads NetBox settings from environment variables and SPAN credentials from `~/.span-auth.json`

2. **Ensure Custom Fields**: Creates any missing custom fields in NetBox

3. **Connect to Panels**: For each panel:
   - Downloads the CA certificate (if not cached)
   - Connects to the panel's MQTT broker over TLS
   - Reads the panel device's `$description` and its `children` list
   - Reads each child's `$description` and keeps those of type `energy.ebus.device.circuit`
   - Collects hardware version, main breaker rating, and circuit details

4. **Sync to NetBox**:
   - Creates or updates power panels with serial number, hardware info, and ratings
   - Creates or updates power feeds for each circuit with name, amperage, voltage (240 V for two or more poles, else 120 V), and position

5. **Create Devices** (with `--create-devices`):
   - Queries mDNS for device info (MAC addresses, IP addresses)
   - Creates manufacturer "SPAN" if not exists
   - Creates a device type named for the panel model (`MAIN_32` becomes "MAIN 32") if not exists
   - Creates device role "Smart Panel" if not exists
   - Creates device with interfaces (eth0, wlan0) and assigns IPs
   - Links device to power panel via `associated_device` custom field

6. **Report Results**: Summarizes what was created or updated

## Data Flow

```
SPAN Panel (MQTT)                    NetBox
─────────────────                    ──────
{panel}/info/hardware-version  →     Power Panel.custom_fields.hardware_version
{panel}/breaker/rating         →     Power Panel.custom_fields.main_breaker_rating
{circuit}/info/name            →     Power Feed.name
{circuit}/breaker/rating       →     Power Feed.amperage
{circuit}/info/spaces          →     Power Feed.custom_fields.panel_space (first space)
{circuit}/breaker/poles        →     Power Feed.custom_fields.is_duplex, Power Feed.voltage

mDNS (_device-info)                  NetBox Device (with --create-devices)
───────────────────                  ─────────────
serial_number                →       Device.serial
eth0_mac                     →       Interface(eth0).mac_address
wlan0_mac                    →       Interface(wlan0).mac_address
IP addresses                 →       IP Address → Interface(eth0)
```

## Troubleshooting

### "No credentials for panel"

Run `span-auth setup` to configure credentials. The `span-auth` tool is available from [SPAN-API](https://github.com/spanio/SPAN-API-Client-Docs):

```bash
# Clone SPAN-API if you haven't already
git clone https://github.com/spanio/SPAN-API-Client-Docs.git
cd SPAN-API-Client-Docs/scripts
./span-auth setup
```

### "Connection refused" or MQTT errors

- Ensure the panel is powered on and connected to the network
- Verify you can ping the panel: `ping span-{serial}.local`
- Check that credentials are current: `span-auth refresh`

### Custom fields not created

Ensure your NetBox API token has permissions to create custom fields. The token needs the following permissions:

- `extras.add_customfield`
- `dcim.add_powerpanel`
- `dcim.change_powerpanel`
- `dcim.add_powerfeed`
- `dcim.change_powerfeed`

### Site not found

The site specified in `NETBOX_SITE` must either:

- Already exist in NetBox, OR
- The API token must have `dcim.add_site` permission to create it

## Known Limitations

- The importer does not delete circuits that have been removed from the panel

## Development

```bash
pip install -r requirements.txt pytest ruff==0.16.1
ruff check . && ruff format --check .
pytest
```

The tests run offline: they feed synthetic MQTT messages to the collector and use stand-ins for the NetBox API. See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution and release process, and [CHANGELOG.md](CHANGELOG.md) for release history.

## License

MIT. See [LICENSE](LICENSE).
