# SPAN NetBox Importer

Import SPAN electrical panel and circuit data into [NetBox](https://netboxlabs.com/), creating power panels and power feeds with detailed custom field data.

## Prerequisites

- Python 3.10+
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
  --discover          Discover panels on network first
  --create-devices    Also create device objects with interfaces and IPs
  --verbose, -v       Verbose output
  --timeout SECONDS   MQTT data collection timeout (default: 10)
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
| `panel_circuit_id` | Text | Circuit identifier from panel (e.g., "1a", "2b") |
| `panel_space` | Integer | Physical space number in panel |
| `is_duplex` | Boolean | Whether this is a duplex (double-pole) circuit |

## How It Works

1. **Load Configuration**: Reads NetBox settings from environment variables and SPAN credentials from `~/.span-auth.json`

2. **Ensure Custom Fields**: Creates any missing custom fields in NetBox

3. **Connect to Panels**: For each panel:
   - Downloads the CA certificate (if not cached)
   - Connects to the panel's MQTT broker over TLS
   - Subscribes to topics for panel properties and circuit data
   - Collects hardware version, main breaker rating, and circuit details

4. **Sync to NetBox**:
   - Creates or updates power panels with serial number, hardware info, and ratings
   - Creates or updates power feeds for each circuit with name, amperage, and position

5. **Create Devices** (with `--create-devices`):
   - Queries mDNS for device info (MAC addresses, IP addresses)
   - Creates manufacturer "SPAN" if not exists
   - Creates device type "MAIN 32" if not exists
   - Creates device role "Smart Panel" if not exists
   - Creates device with interfaces (eth0, wlan0) and assigns IPs
   - Links device to power panel via `associated_device` custom field

6. **Report Results**: Summarizes what was created or updated

## Data Flow

```
SPAN Panel (MQTT)                    NetBox
─────────────────                    ──────
core/hardware-version        →       Power Panel.custom_fields.hardware_version
core/breaker-rating          →       Power Panel.custom_fields.main_breaker_rating
{circuit}/name               →       Power Feed.name
{circuit}/breaker-rating     →       Power Feed.amperage
{circuit}/space              →       Power Feed.custom_fields.panel_space
{circuit}/dipole             →       Power Feed.custom_fields.is_duplex

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

## License

See the repository LICENSE file.
