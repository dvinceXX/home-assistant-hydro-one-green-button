"""Parser for Green Button (ESPI) XML Download My Data files.

The parser has no Home Assistant dependency, allowing a future approved
Connect My Data source to reuse the normalized data model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import xml.etree.ElementTree as ET


class GreenButtonParseError(ValueError):
    """Raised when a Green Button XML file cannot be interpreted."""


@dataclass(frozen=True, slots=True)
class IntervalReading:
    """One normalized interval energy reading."""
    start: datetime
    duration_seconds: int
    energy_kwh: float


@dataclass(frozen=True, slots=True)
class GreenButtonData:
    """Normalized usage data extracted from a Green Button file."""
    readings: tuple[IntervalReading, ...]
    total_energy_kwh: float
    latest_reading: IntervalReading


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].split(":")[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == name and child.text is not None:
            return child.text.strip()
    return None


def _descendant_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local_name(child.tag) == name and child.text is not None:
            return child.text.strip()
    return None


def _number(element: ET.Element, name: str, default: float | None = None) -> float:
    raw = _child_text(element, name)
    if raw is None:
        if default is not None:
            return default
        raise GreenButtonParseError(f"Missing required XML field: {name}")
    try:
        return float(raw)
    except ValueError as err:
        raise GreenButtonParseError(f"Invalid numeric XML field {name}: {raw!r}") from err


def _to_kwh(value: float, multiplier: float, power_of_ten: float, uom: str | None) -> float:
    """Convert common ESPI energy units to kWh."""
    scaled = value * multiplier * (10 ** power_of_ten)
    unit = (uom or "").strip().lower()
    factors = {
        "72": 0.001, "wh": 0.001, "watt-hour": 0.001, "watt hours": 0.001,
        "73": 1.0, "kwh": 1.0, "kilowatt-hour": 1.0, "kilowatt hours": 1.0,
        "74": 1000.0, "mwh": 1000.0, "megawatt-hour": 1000.0,
        "75": 1_000_000.0, "gwh": 1_000_000.0,
    }
    if unit not in factors:
        raise GreenButtonParseError(f"Unsupported or missing energy unit of measure (uom={uom!r})")
    return scaled * factors[unit]


def _parse_timestamp(raw: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (ValueError, OverflowError, OSError) as err:
        raise GreenButtonParseError(f"Invalid interval start timestamp: {raw!r}") from err


def parse_green_button_xml(xml_text: str) -> GreenButtonData:
    """Parse embedded and href-linked Atom/ESPI interval readings."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as err:
        raise GreenButtonParseError("File is not valid XML") from err

    parent_map = {child: parent for parent in root.iter() for child in parent}

    def direct_resource(entry: ET.Element) -> ET.Element | None:
        content = next((child for child in entry if _local_name(child.tag) == "content"), None)
        return next(iter(content), None) if content is not None else None

    def normalize_ref(ref: str | None) -> str | None:
        return ref.rstrip("/") if ref else None

    resources_by_ref: dict[str, ET.Element] = {}
    entry_resources: list[tuple[ET.Element, ET.Element]] = []
    for entry in (e for e in root.iter() if _local_name(e.tag) == "entry"):
        resource = direct_resource(entry)
        if resource is None:
            continue
        entry_resources.append((entry, resource))
        entry_id = _child_text(entry, "id")
        if entry_id:
            resources_by_ref[normalize_ref(entry_id)] = resource
        for link in (e for e in entry if _local_name(e.tag) == "link"):
            if link.attrib.get("rel") == "self" and link.attrib.get("href"):
                resources_by_ref[normalize_ref(link.attrib["href"])] = resource

    def resolve_resource(ref: str | None) -> ET.Element | None:
        return resources_by_ref.get(normalize_ref(ref)) if ref else None

    def linked_or_embedded(resource: ET.Element, child_name: str) -> ET.Element | None:
        child = next((e for e in resource if _local_name(e.tag) == child_name), None)
        if child is None:
            return None
        href = child.attrib.get("href")
        if href:
            return resolve_resource(href)
        return child if len(child) else None

    reading_type_by_block: dict[int, ET.Element] = {}
    for entry, resource in entry_resources:
        if _local_name(resource.tag) != "MeterReading":
            continue
        reading_type = linked_or_embedded(resource, "ReadingType")
        block = linked_or_embedded(resource, "IntervalBlock")
        if reading_type is None:
            for link in (e for e in entry if _local_name(e.tag) == "link"):
                resolved = resolve_resource(link.attrib.get("href"))
                if resolved is None:
                    continue
                if _local_name(resolved.tag) == "ReadingType":
                    reading_type = resolved
                elif _local_name(resolved.tag) == "IntervalBlock":
                    block = resolved
        if reading_type is None:
            continue
        if block is not None:
            reading_type_by_block[id(block)] = reading_type
        for descendant in resource.iter():
            if _local_name(descendant.tag) == "IntervalBlock":
                reading_type_by_block[id(descendant)] = reading_type

    parsed: list[IntervalReading] = []
    all_types = [e for e in root.iter() if _local_name(e.tag) == "ReadingType"]
    for interval in (e for e in root.iter() if _local_name(e.tag) == "IntervalReading"):
        value_text = _child_text(interval, "value")
        period = next((e for e in interval if _local_name(e.tag) == "timePeriod"), None)
        if value_text is None or period is None:
            continue
        start_text, duration_text = _child_text(period, "start"), _child_text(period, "duration")
        if start_text is None or duration_text is None:
            continue
        try:
            value, duration = float(value_text), int(duration_text)
        except ValueError as err:
            raise GreenButtonParseError("Invalid interval reading value or duration") from err
        if duration <= 0:
            raise GreenButtonParseError("Interval duration must be greater than zero")

        reading_type = None
        ancestor = parent_map.get(interval)
        interval_block = None
        while ancestor is not None:
            if _local_name(ancestor.tag) == "MeterReading":
                reading_type = linked_or_embedded(ancestor, "ReadingType")
                if reading_type is None:
                    for link in (e for e in ancestor.iter() if _local_name(e.tag) == "link"):
                        candidate = resolve_resource(link.attrib.get("href"))
                        if candidate is not None and _local_name(candidate.tag) == "ReadingType":
                            reading_type = candidate
                            break
                break
            if _local_name(ancestor.tag) == "IntervalBlock":
                interval_block = ancestor
            ancestor = parent_map.get(ancestor)
        if reading_type is None and interval_block is not None:
            reading_type = reading_type_by_block.get(id(interval_block))
        if reading_type is None and len(all_types) == 1:
            reading_type = all_types[0]
        if reading_type is None:
            raise GreenButtonParseError("Could not find ReadingType metadata for an interval")

        uom = _descendant_text(reading_type, "uom")
        multiplier = _number(reading_type, "multiplier", 1)
        power_of_ten = _number(reading_type, "powerOfTenMultiplier", 0)
        parsed.append(IntervalReading(_parse_timestamp(start_text), duration,
                                      _to_kwh(value, multiplier, power_of_ten, uom)))

    if not parsed:
        raise GreenButtonParseError(
            "No supported IntervalReading records found; confirm this is a Green Button usage XML export"
        )
    parsed.sort(key=lambda item: item.start)
    readings = tuple(parsed)
    return GreenButtonData(readings, sum(item.energy_kwh for item in readings), readings[-1])


def parse_green_button_file(file_path: str | Path) -> GreenButtonData:
    """Read and parse a Green Button XML file from disk."""
    xml_text = Path(file_path).expanduser().read_text(encoding="utf-8-sig")
    return parse_green_button_xml(xml_text)


def build_energy_statistics(readings: tuple[IntervalReading, ...]) -> list[dict[str, object]]:
    """Build cumulative Home Assistant energy statistics from interval usage.

    Add a zero-use baseline at the first interval start, then record the
    cumulative total at each interval end. This aligns each interval's usage
    with the period it describes when Home Assistant compares adjacent sums.
    """
    if not readings:
        return []

    cumulative_kwh = 0.0
    statistics: list[dict[str, object]] = [
        {"start": readings[0].start, "state": 0.0, "sum": 0.0}
    ]
    for reading in readings:
        cumulative_kwh = round(cumulative_kwh + reading.energy_kwh, 6)
        statistics.append(
            {
                "start": reading.start.timestamp() + reading.duration_seconds,
                "state": cumulative_kwh,
                "sum": cumulative_kwh,
            }
        )
        statistics[-1]["start"] = datetime.fromtimestamp(
            statistics[-1]["start"], tz=reading.start.tzinfo
        )
    return statistics
