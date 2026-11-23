"""Validation du .ics généré. Lancer : pytest -q"""
import re
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import icalendar
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
REFERENCE = ROOT / "reference" / "rappels-spirituels-yom-v8.ics"


@pytest.fixture(scope="module")
def events():
    return build.load_events()


@pytest.fixture(scope="module")
def raw(events):
    return build.build(events).encode("utf-8")


def test_committed_file_is_up_to_date(raw):
    assert build.OUTPUT.read_bytes() == raw, "Relancer python build.py"


def test_crlf_everywhere(raw):
    assert raw.endswith(b"\r\n")
    assert b"\n" not in raw.replace(b"\r\n", b"")
    assert b"\r" not in raw.replace(b"\r\n", b"")


def test_lines_max_75_bytes(raw):
    long = [l for l in raw.split(b"\r\n") if len(l) > 75]
    assert not long, long


def test_header(raw):
    text = raw.decode("utf-8")
    for line in build.HEADER:
        assert line + "\r\n" in text


def test_structure(raw, events):
    cal = icalendar.Calendar.from_ical(raw)
    vevents = cal.walk("VEVENT")
    assert len(vevents) == len(events)
    uids = [str(e["UID"]) for e in vevents]
    assert len(set(uids)) == len(uids)
    for e in vevents:
        assert len(e.walk("VALARM")) == 1, e["UID"]
        assert e["STATUS"] == "CONFIRMED" and "DTSTAMP" in e
    if any(isinstance(e["DTSTART"].dt, datetime) for e in vevents):
        assert cal.walk("VTIMEZONE")


def test_triggers_relative_hours_only(raw):
    text = raw.decode("utf-8").replace("\r\n ", "")
    triggers = re.findall(r"^TRIGGER[^\r]*", text, re.M)
    assert triggers
    for t in triggers:
        assert re.fullmatch(r"TRIGGER:-?PT(\d+H)?(\d+M)?(\d+S)?", t), t


def test_fold_counts_bytes():
    folded = build.fold("DESCRIPTION:" + "é" * 80)
    assert all(len(l.encode()) <= 75 for l in folded.split("\r\n"))
    assert folded.replace("\r\n ", "") == "DESCRIPTION:" + "é" * 80


def test_trigger_handles_dst():
    # alerte samedi 24/10 18:00 (CEST) pour lundi 26/10 20:00 (CET) : 51 h réelles
    ev = {"id": "x", "titre": "t", "debut": "2026-10-26 20:00", "fin": "2026-10-26 21:00",
          "alerte": "2026-10-24 18:00", "dtstamp": "20260101T000000Z"}
    assert "TRIGGER:-PT51H" in build.event_lines(ev)


def test_lieu_becomes_location():
    ev = {"id": "x", "titre": "t", "debut": "2026-10-26 20:00", "fin": "2026-10-26 21:00",
          "lieu": "Mosquée, 12 rue de l'Exemple; Paris", "dtstamp": "20260101T000000Z"}
    ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "\r\n".join(build.event_lines(ev))
           + "\r\nEND:VCALENDAR\r\n").encode()
    loc = icalendar.Calendar.from_ical(ics).walk("VEVENT")[0]["LOCATION"]
    assert str(loc) == "Mosquée, 12 rue de l'Exemple; Paris"


def _snapshot(ics_bytes):
    """Contenu effectif par UID, dont l'heure réelle de l'alerte."""
    out = {}
    for e in icalendar.Calendar.from_ical(ics_bytes).walk("VEVENT"):
        start = e["DTSTART"].dt
        anchor = start if isinstance(start, datetime) else datetime.combine(start, time(0), PARIS)
        alarm = e.walk("VALARM")[0]
        out[str(e["UID"])] = dict(
            summary=str(e["SUMMARY"]), description=str(e.get("DESCRIPTION", "")),
            categories=[str(c) for c in e["CATEGORIES"].cats], start=start,
            end=e["DTEND"].dt, transp=str(e["TRANSP"]), dtstamp=e["DTSTAMP"].dt,
            alarm_text=str(alarm["DESCRIPTION"]),
            alarm_at=anchor + alarm["TRIGGER"].dt,
        )
    return out


@pytest.mark.skipif(not REFERENCE.exists(), reason="référence absente")
def test_non_regression_vs_reference(raw):
    # Ne compare que les UID de la référence : les événements ajoutés depuis sont libres,
    # mais un événement de la référence modifié volontairement fera échouer ce test
    # -> dans ce cas, mettre à jour EXPECTED_CHANGES ci-dessous.
    ref, new = _snapshot(REFERENCE.read_bytes()), _snapshot(raw)
    for uid, ref_ev in ref.items():
        if uid in EXPECTED_CHANGES:
            continue
        assert uid in new, f"{uid} supprimé"
        assert new[uid] == ref_ev, uid


# UID de la référence modifiés ou supprimés volontairement depuis la v8.
EXPECTED_CHANGES = set()
