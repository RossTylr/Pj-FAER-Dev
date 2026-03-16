"""XES 2.0 XML exporter for FAER-M event store.

Phase 4 Iter 5. PRD section 7.5, CP4 gate criterion #8.

Exports event store to XES format compatible with PM4Py, Disco, Celonis.

Mapping:
- Case = patient (casualty_id)
- Activity = event_type
- Timestamp = sim_time (converted to ISO datetime via deterministic epoch offset)
- Resource = facility_id
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Optional

from faer_dev.events.queries import TemporalQuery
from faer_dev.events.store import EventStore

# Deterministic base time for sim_time -> ISO datetime conversion.
# Using a fixed epoch avoids wall-clock drift between events.
_SIM_EPOCH = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class XESExporter:
    """Export event store to XES 2.0 XML format.

    Usage::

        exporter = XESExporter()
        exporter.export(engine.event_store, "output.xes")
    """

    def export(
        self,
        store: EventStore,
        filepath: str,
        base_time: Optional[datetime] = None,
    ) -> None:
        """Export event store to XES file.

        Args:
            store: The event store to export.
            filepath: Output file path (.xes).
            base_time: Base datetime for sim_time offset. Defaults to
                a fixed epoch (2024-01-01T00:00:00Z) so that timestamps
                are deterministic and properly spaced by sim_time minutes.
        """
        epoch = base_time or _SIM_EPOCH
        query = TemporalQuery(store)

        root = ET.Element("log")
        root.set("xes.version", "2.0")
        root.set("xmlns", "http://www.xes-standard.org/")

        # Extensions
        _add_extension(root, "Concept", "concept", "http://www.xes-standard.org/concept.xesext")
        _add_extension(root, "Time", "time", "http://www.xes-standard.org/time.xesext")
        _add_extension(root, "Organizational", "org", "http://www.xes-standard.org/org.xesext")

        # Global event classifier
        classifier = ET.SubElement(root, "classifier")
        classifier.set("name", "Event Name")
        classifier.set("keys", "concept:name")

        # Global event attributes
        global_evt = ET.SubElement(root, "global")
        global_evt.set("scope", "event")
        _add_string(global_evt, "concept:name", "UNKNOWN")

        # One trace per patient
        for cid in query.patient_ids():
            trace = ET.SubElement(root, "trace")
            _add_string(trace, "concept:name", cid)

            for event in query.patient_journey(cid):
                evt = ET.SubElement(trace, "event")
                _add_string(evt, "concept:name", event.event_type)

                # Timestamp: deterministic, derived from sim_time offset
                ts = epoch + timedelta(minutes=event.sim_time)
                _add_date(evt, "time:timestamp", ts.isoformat())

                # Sim time as additional attribute
                _add_float(evt, "sim:time", event.sim_time)

                # Resource = facility
                if event.facility_id:
                    _add_string(evt, "org:resource", event.facility_id)

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(filepath, encoding="unicode", xml_declaration=True)


def _add_extension(parent: ET.Element, name: str, prefix: str, uri: str) -> None:
    ext = ET.SubElement(parent, "extension")
    ext.set("name", name)
    ext.set("prefix", prefix)
    ext.set("uri", uri)


def _add_string(parent: ET.Element, key: str, value: str) -> None:
    elem = ET.SubElement(parent, "string")
    elem.set("key", key)
    elem.set("value", value)


def _add_date(parent: ET.Element, key: str, value: str) -> None:
    elem = ET.SubElement(parent, "date")
    elem.set("key", key)
    elem.set("value", value)


def _add_float(parent: ET.Element, key: str, value: float) -> None:
    elem = ET.SubElement(parent, "float")
    elem.set("key", key)
    elem.set("value", str(value))
