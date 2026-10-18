"""Unit tests for the Home Assistant-independent XML parser."""
from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys
import pytest

PARSER_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "hydro_one_green_button" / "green_button.py"
SPEC = importlib.util.spec_from_file_location("green_button_parser", PARSER_PATH)
assert SPEC and SPEC.loader
PARSER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PARSER
SPEC.loader.exec_module(PARSER)
GreenButtonParseError = PARSER.GreenButtonParseError
parse_green_button_xml = PARSER.parse_green_button_xml


def make_xml(uom: int = 73, value: int = 1250, multiplier: int = 1, power: int = 0) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:espi="http://naesb.org/espi">
      <entry><content><espi:ReadingType>
        <espi:uom>{uom}</espi:uom><espi:multiplier>{multiplier}</espi:multiplier>
        <espi:powerOfTenMultiplier>{power}</espi:powerOfTenMultiplier>
      </espi:ReadingType></content></entry>
      <entry><content><espi:MeterReading>
        <espi:ReadingType><espi:uom>{uom}</espi:uom><espi:multiplier>{multiplier}</espi:multiplier>
        <espi:powerOfTenMultiplier>{power}</espi:powerOfTenMultiplier></espi:ReadingType>
        <espi:IntervalBlock>
          <espi:IntervalReading><espi:timePeriod><espi:start>1700000000</espi:start><espi:duration>900</espi:duration></espi:timePeriod><espi:value>{value}</espi:value></espi:IntervalReading>
          <espi:IntervalReading><espi:timePeriod><espi:start>1700000900</espi:start><espi:duration>900</espi:duration></espi:timePeriod><espi:value>{value}</espi:value></espi:IntervalReading>
        </espi:IntervalBlock>
      </espi:MeterReading></content></entry>
    </feed>'''


def test_parses_interval_readings_and_total():
    data = parse_green_button_xml(make_xml())
    assert len(data.readings) == 2
    assert data.readings[0].energy_kwh == 1250
    assert data.total_energy_kwh == 2500
    assert data.latest_reading.start == datetime.fromtimestamp(1700000900, UTC)
    assert data.latest_reading.duration_seconds == 900


def test_converts_wh_to_kwh():
    assert parse_green_button_xml(make_xml(uom=72, value=500)).readings[0].energy_kwh == pytest.approx(0.5)


def test_applies_multiplier_and_power_of_ten():
    assert parse_green_button_xml(make_xml(uom=73, value=12, multiplier=2, power=-1)).readings[0].energy_kwh == pytest.approx(2.4)


def test_rejects_invalid_xml():
    with pytest.raises(GreenButtonParseError, match="valid XML"):
        parse_green_button_xml("<not-closed>")


def test_rejects_unknown_units():
    with pytest.raises(GreenButtonParseError, match="unit of measure"):
        parse_green_button_xml(make_xml(uom=999, value=10))


def test_rejects_no_interval_readings():
    with pytest.raises(GreenButtonParseError, match="No supported IntervalReading"):
        parse_green_button_xml("<feed />")


def test_resolves_split_atom_resources_by_href():
    xml = '''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:espi="http://naesb.org/espi">
      <entry><id>/MeterReading/mr1</id><link rel="self" href="/MeterReading/mr1"/><content><espi:MeterReading><espi:ReadingType href="/ReadingType/rt1"/><espi:IntervalBlock href="/IntervalBlock/ib1"/></espi:MeterReading></content></entry>
      <entry><id>/ReadingType/rt1</id><link rel="self" href="/ReadingType/rt1"/><content><espi:ReadingType><espi:uom>72</espi:uom><espi:multiplier>1</espi:multiplier><espi:powerOfTenMultiplier>0</espi:powerOfTenMultiplier></espi:ReadingType></content></entry>
      <entry><id>/IntervalBlock/ib1</id><link rel="self" href="/IntervalBlock/ib1"/><content><espi:IntervalBlock><espi:IntervalReading><espi:timePeriod><espi:start>1700000000</espi:start><espi:duration>900</espi:duration></espi:timePeriod><espi:value>750</espi:value></espi:IntervalReading></espi:IntervalBlock></content></entry>
    </feed>'''
    data = parse_green_button_xml(xml)
    assert len(data.readings) == 1
    assert data.total_energy_kwh == pytest.approx(0.75)
