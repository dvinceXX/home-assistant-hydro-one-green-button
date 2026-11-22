# Hydro One Green Button for Home Assistant

A HACS custom integration that imports electricity usage from Hydro One's Green Button **Download My Data (DMD)** XML export.

## Features

- Reads a Green Button XML file or scans a dedicated folder of XML exports every 15 minutes.
- Normalizes interval energy to kWh and deduplicates overlapping exports.
- Exposes sensors for latest interval energy, imported energy total, latest reading time, imported interval count, and current Ontario TOU rate.
- Records the scheduled TOU rate as a Home Assistant measurement sensor with long-term statistics, suitable for an hourly rate graph.
- Imports historical energy into Home Assistant external long-term statistics.
- Imports a separate cumulative historical electricity-cost statistic for the Energy Dashboard.
- Calculates Ontario TOU costs using each interval's local date/time, winter/summer schedule, weekends, and Ontario TOU holidays.
- Lets you configure the three CAD/kWh rates and their effective date in the integration's Configure options.
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

## Hourly TOU rate graph

The integration exposes `sensor.hydro_one_tou_rate`, which reports the currently scheduled Ontario TOU price in CAD/kWh. It uses the same rate schedule, configured effective date, local time zone, weekends, and holidays as the cost calculator. The sensor updates at each local clock-hour boundary and records Home Assistant long-term statistics automatically.

Add this Lovelace card for the last 24 hours:

```yaml
type: statistics-graph
title: Hydro One - Hourly Electricity Rate
chart_type: line
period: hour
days_to_show: 1
stat_types:
  - mean
entities:
  - sensor.hydro_one_tou_rate
```

The graph begins collecting history after the sensor is installed; it does not backfill the previous 24 hours.

## Energy Dashboard cost setup

1. Open **Settings → Dashboards → Energy** and edit the electricity grid source using `hydro_one_green_button:historical_energy`.
2. Under cost tracking, choose **Use a statistic for cost** (not a price entity).
3. Select `hydro_one_green_button:historical_cost`.
4. Save the Energy Dashboard configuration.

The cost statistic is cumulative and uses CAD as its unit. Home Assistant uses its changes to calculate daily, monthly, and yearly costs.

## Ontario electricity pricing plans\n\nThe pricing-plan selector defaults to **Time-of-Use (TOU)** to preserve existing installations. Select **Ultra-Low Overnight (ULO)** or **Tiered (residential)** from the integration's Configure options when those match your Hydro One account.\n\n- **TOU:** weekday on-, mid- and off-peak periods change between summer (May–October) and winter (November–April); weekends and OEB holidays are off-peak all day.\n- **ULO:** every day 11 p.m.–7 a.m. is ultra-low overnight; weekdays 7 a.m.–4 p.m. and 9 p.m.–11 p.m. are mid-peak; weekdays 4 p.m.–9 p.m. are on-peak; weekends and OEB holidays 7 a.m.–11 p.m. are weekend off-peak.\n- **Tiered (residential):** Tier 1 applies to the first 1,000 kWh per calendar month in winter and 600 kWh in summer; additional monthly usage is Tier 2. Usage is accumulated chronologically from the imported intervals. Accurate Tiered cost history requires the import to include the full month's intervals from the first day; missing early-month intervals can understate Tier 2 usage.\n\nCurrent OEB residential rates effective November 1, 2026 are TOU 9.1¢/14.6¢/18.9¢, ULO 3.7¢/9.1¢/14.6¢/37.7¢, and Tiered 11.2¢/13.2¢. The integration includes historical rate schedules for each plan. OEB rates are set annually on November 1; update the configured rate values and effective date when the OEB publishes a new schedule. The integration cannot know future rates before publication. Tiered thresholds switch automatically on May 1 and November 1.\n\n## Ontario TOU defaults and historical rates

The integration applies the Ontario Energy Board (OEB) Regulated Price Plan time-of-use rates that were effective on each reading's local date. The bundled historical schedule is:

| Effective date | Off-peak | Mid-peak | On-peak |
| --- | ---: | ---: | ---: |
| November 1, 2022 | $0.074/kWh | $0.102/kWh | $0.151/kWh |
| November 1, 2023 | $0.087/kWh | $0.122/kWh | $0.182/kWh |
| November 1, 2024 | $0.076/kWh | $0.122/kWh | $0.158/kWh |
| November 1, 2025 | $0.098/kWh | $0.157/kWh | $0.203/kWh |
| November 1, 2026 | $0.091/kWh | $0.146/kWh | $0.189/kWh |

The November 1, 2026 rates are the current defaults. Readings before November 1, 2022 use the earliest bundled rate set (November 2022); those older costs should be treated as estimates until earlier OEB schedules are added.

Schedule:
- Weekends and Ontario TOU statutory holidays: off-peak all day.
- November–April: 7–11 a.m. on-peak, 11 a.m.–5 p.m. mid-peak, 5–7 p.m. on-peak, otherwise off-peak.
- May–October: 7–11 a.m. mid-peak, 11 a.m.–5 p.m. on-peak, 5–7 p.m. mid-peak, otherwise off-peak.

Holiday dates include New Year's Day, Family Day, Good Friday, Victoria Day, Canada Day, Civic Holiday, Labour Day, Thanksgiving, Christmas Day, and Boxing Day. When a listed holiday falls on a weekend, the following Monday is treated as the observed holiday. The integration uses Home Assistant's configured time zone for historical interval pricing.

To configure rates for a future OEB change, open **Settings → Devices & services → Hydro One Green Button → Configure** and enter the rates for your selected plan plus their effective date (normally November 1). Existing options without a plan selection default to TOU.

## Historical statistics correction

On the first setup after this update, the integration clears and rebuilds only its own historical_energy and historical_cost statistics over the imported history range. This corrects the previous energy interval-end timestamps and recalculates historical costs using the effective-date rate schedule. Other Home Assistant statistics are not cleared. The one-time migration is recorded in the config entry so normal restarts do not repeat the cleanup.

## Important calculation details

- Interval energy is assumed to be consumed evenly across the interval. If an interval crosses a TOU boundary, its energy is split proportionally between the applicable rates.
- The historical cost statistic includes only the configured per-kWh energy rates. It does not include fixed monthly charges, delivery charges, regulatory charges, taxes, or rebates unless those are reflected in the configured rates.
- The cost statistic is built at hourly resolution, as expected for Home Assistant external long-term statistics.
- The integration scans top-level `.xml` files only; it does not scan subfolders.
- Green Button XML can contain account and service information. Do not publish original exports or share them without sanitizing personal information.

## Development

The XML parser is in `green_button.py`, TOU, ULO and residential Tiered pricing are in `pricing.py`, and parser/pricing tests are in `tests/`. Run `pytest -q` in the repository's test environment.
