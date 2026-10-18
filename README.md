# Hydro One Green Button for Home Assistant

A HACS custom integration that imports electricity usage from Hydro One's Green Button **Download My Data (DMD)** XML export. The parser is isolated from Home Assistant entities so a future Connect My Data (CMD) source can reuse the same normalized data model.

> Early development / testing release. Green Button XML exports can vary. If your export is rejected, open an issue with a sanitized sample that contains no account numbers, service addresses, names, or other personal information.

## Features

- Reads a Green Button XML file stored on the Home Assistant machine.
- Refreshes the file every 15 minutes, so replacing it with an updated export updates the sensors.
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
2. Copy the XML file into a directory accessible to Home Assistant, such as `/config/hydro-one-green-button.xml`.
3. Keep the file in place; future exports can replace that file.

Do not publish or share the original XML. It can contain sensitive energy and account information.

## Configure

1. Go to **Settings → Devices & services → Add integration**.
2. Search for **Hydro One Green Button**.
3. Enter the absolute path to the XML file, for example `/config/hydro-one-green-button.xml`.
4. Confirm the integration creates the four sensors and allows time for the initial historical-statistics import.

Home Assistant must be able to read the file. The integration checks the file at setup and every 15 minutes thereafter. It does not provide a browser-based file upload; copy the file to Home Assistant using your normal file-transfer method.

## Data interpretation and limitations

- Green Button interval timestamps are interpreted as Unix timestamps in UTC.
- Energy unit codes 72 (Wh), 73 (kWh), 74 (MWh), and 75 (GWh) are supported, as are common textual equivalents.
- Historical statistics are imported under `hydro_one_green_button:historical_energy`. The import uses cumulative sums from interval readings, with a zero baseline before the first interval. If you replace the XML with a file that omits older history, the cumulative series may need to be rebuilt.
- This release focuses on interval energy readings. Billing, cost, demand, transaction, and meter-register values are not exposed yet.
- If the export contains multiple meter readings with different reading types, the parser uses each interval's associated `MeterReading` metadata when available.
- The integration does not connect to Hydro One's CMD service. Hydro One requires third-party onboarding/approval for CMD apps; a future implementation must follow that process.

## Development

The parser is in `custom_components/hydro_one_green_button/green_button.py` and has no Home Assistant dependency. A future CMD client should normalize API responses to the same `GreenButtonData` structure and reuse the sensor platform.

Run parser tests with `pytest -q` after installing `pytest`.
