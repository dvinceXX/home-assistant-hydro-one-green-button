# Hydro One Green Button for Home Assistant

A HACS custom integration that imports electricity usage from Hydro One's Green Button **Download My Data (DMD)** XML export.

## Features

- Reads a Green Button XML file or scans a dedicated folder of XML exports every 15 minutes.
- Normalizes interval energy to kWh and deduplicates overlapping exports.
- Exposes sensors for latest interval energy, imported energy total, latest reading time, and imported interval count.
- Imports historical energy into Home Assistant external long-term statistics.
- Imports a separate cumulative historical electricity-cost statistic for the Energy Dashboard.
- Calculates Ontario TOU costs using each interval's local date/time, winter/summer schedule, weekends, and Ontario TOU holidays.
- Lets you configure the three CAD/kWh rates in the integration's Configure options.
- Rebuilds both complete cumulative series when readings or configured rates change, so later exports can fill gaps in earlier partial days.
- Does not store or use Hydro One credentials.

## Install with HACS

1. In HACS, open **Integrations** and choose **Custom repositories**.
2. Add `https://github.com/dvinceXX/home-assistant-hydro-one-green-button` with category **Integration**.
3. Install **Hydro One Green Button** and restart Home Assistant.

## Configure

1. Download your Green Button data from Hydro One myAccount.
2. Copy the XML export(s) into a folder accessible to Home Assistant, for example `/config/hydro-one-xml/`.
3. Add **Hydro One Green Button** from **Settings → Devices & services** and enter that folder path. Existing single-file configuration remains supported.
4. Keep older XML exports in the folder; overlapping intervals are deduplicated and the complete history is rebuilt when new files arrive.

## Energy Dashboard cost setup

1. Open **Settings → Dashboards → Energy** and edit the electricity grid source using `hydro_one_green_button:historical_energy`.
2. Under cost tracking, choose **Use a statistic for cost** (not a price entity).
3. Select `hydro_one_green_button:historical_cost`.
4. Save the Energy Dashboard configuration.

The cost statistic is cumulative and uses CAD as its unit. Home Assistant uses its changes to calculate daily, monthly, and yearly costs.

## Ontario TOU defaults

- Off-peak: **$0.091/kWh**
- Mid-peak: **$0.146/kWh**
- On-peak: **$0.189/kWh**

Schedule:
- Weekends and Ontario TOU statutory holidays: off-peak all day.
- November–April: 7–11 a.m. on-peak, 11 a.m.–5 p.m. mid-peak, 5–7 p.m. on-peak, otherwise off-peak.
- May–October: 7–11 a.m. mid-peak, 11 a.m.–5 p.m. on-peak, 5–7 p.m. mid-peak, otherwise off-peak.

Holiday dates include New Year's Day, Family Day, Good Friday, Victoria Day, Canada Day, Labour Day, Thanksgiving, Christmas Day, and Boxing Day. The Civic Holiday is not included. The integration uses Home Assistant's configured time zone for historical interval pricing.

To change rates, open **Settings → Devices & services → Hydro One Green Button → Configure**.

## Important calculation details

- Interval energy is assumed to be consumed evenly across the interval. If an interval crosses a TOU boundary, its energy is split proportionally between the applicable rates.
- The historical cost statistic includes only the configured per-kWh energy rates. It does not include fixed monthly charges, delivery charges, regulatory charges, taxes, or rebates unless those are reflected in the configured rates.
- The cost statistic is built at hourly resolution, as expected for Home Assistant external long-term statistics.
- The integration scans top-level `.xml` files only; it does not scan subfolders.
- Green Button XML can contain account and service information. Do not publish original exports or share them without sanitizing personal information.

## Development

The XML parser is in `green_button.py`, TOU pricing is in `pricing.py`, and parser/pricing tests are in `tests/`. Run `pytest -q` in the repository's test environment.
