# Hydro One Green Button for Home Assistant

A HACS custom integration that imports electricity usage from Hydro One's Green Button **Download My Data (DMD)** XML export. The parser is isolated from Home Assistant entities so a future Connect My Data (CMD) source can reuse the same normalized data model.

> Early development / testing release. Green Button XML exports can vary. If your export is rejected, open an issue with a sanitized sample that contains no account numbers, service addresses, names, or other personal information.

## Features

- Reads a Green Button XML file or scans a dedicated folder of XML exports on the Home Assistant machine.
- Scans the configured source every 15 minutes, so new XML files can be dropped into a watched folder.
- Normalizes interval energy to kWh using the reading type's unit, multiplier, and power-of-ten multiplier.
- Exposes four sensors: latest interval energy (kWh), imported energy total (kWh), latest reading time, and imported interval count.
- Imports the full interval history into Home Assistant's external long-term energy statistics, preserving timestamps so historical usage can be explored in Energy-related statistics.
- No Hydro One credentials are stored or used.

The imported energy total is the sum of all interval readings in the current file, not a cumulative lifetime meter register. If a file contains multiple meter readings or overlapping records, the sum may not represent a single service's billable total. Check your export and sensor attributes before using it for billing calculations.

## Install with HACS (custom repository)

1. In HACS, open **Integrations**.
2. Use the menu in the upper-right and choose **Custom repositories**.
3. Add `https://github.com/dvinceXX/home-assistant-hydro-one-green-button` and select category **Integration**.
4. Install **Hydro One Green Button** and restart Home Assistant.

## Prepare the XML file

1. Sign in to Hydro One myAccount and download your Green Button data using **Download My Data**.
2. Create a dedicated folder accessible to Home Assistant, for example `/config/hydro-one-xml/`.
3. Copy each weekly (or otherwise scheduled) Hydro One XML export into that folder. Keep older files there if possible; overlapping readings are deduplicated.

Do not publish or share the original XML. It can contain sensitive energy and account information.

## Configure

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Hydro One Green Button**.
3. Enter the absolute path to the dedicated folder, for example `/config/hydro-one-xml/`. A single XML file path is still supported for compatibility.
4. If the integration is already configured to a single file, open its **Configure** options and change the path to the folder; this preserves the existing import tracking state.
5. Confirm the integration creates the four sensors and allows time for the initial historical-statistics import.

Home Assistant must be able to read the file. The integration scans top-level `.xml` files in the folder at setup and every 15 minutes thereafter; it does not scan subfolders. It does not provide a browser-based file upload; copy the file to Home Assistant using your normal file-transfer method.

## Data interpretation and limitations

- Green Button interval timestamps are interpreted as Unix timestamps in UTC.
- Energy unit codes 72 (Wh), 73 (kWh), 74 (MWh), and 75 (GWh) are supported, as are common textual equivalents.
- Historical statistics are imported under `hydro_one_green_button:historical_energy`. When the combined readings change, the integration rebuilds and submits the complete cumulative series. This allows later exports to fill missing hourly intervals on a day that was only partially available before and recalculates later cumulative sums. Keep older XML files in the folder so the full history is available during each rebuild.
- This release focuses on interval energy readings. Billing, cost, demand, transaction, and meter-register values are not exposed yet.
- If the export contains multiple meter readings with different reading types, the parser uses each interval's associated `MeterReading` metadata when available.
- The integration does not connect to Hydro One's CMD service. Hydro One requires third-party onboarding/approval for CMD apps; a future implementation must follow that process.

## Development

The parser is in `custom_components/hydro_one_green_button/green_button.py` and has no Home Assistant dependency. A future CMD client should normalize API responses to the same `GreenButtonData` structure and reuse the sensor platform.

Run parser tests with `pytest -q` after installing `pytest`.
