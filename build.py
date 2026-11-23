"""Génère rappels-spirituels-yom.ics à partir de events.yaml.

Usage : python build.py
"""
import re
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).parent
SOURCE = ROOT / "events.yaml"
OUTPUT = ROOT / "rappels-spirituels-yom.ics"
PARIS = ZoneInfo("Europe/Paris")

HEADER = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Rappels Spirituels YOM//FR",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    "X-WR-CALNAME:Rappels Spirituels YOM",
    "X-WR-TIMEZONE:Europe/Paris",
    "REFRESH-INTERVAL;VALUE=DURATION:P1D",
    "X-PUBLISHED-TTL:P1D",
]
VTIMEZONE = [
    "BEGIN:VTIMEZONE",
    "TZID:Europe/Paris",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
]


def escape(text):
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """Plie à 75 octets max (CRLF + espace), sans couper un caractère UTF-8."""
    out, current, limit = [], b"", 75
    for ch in line:
        b = ch.encode("utf-8")
        if len(current) + len(b) > limit:
            out.append(current)
            current, limit = b"", 74  # la ligne de suite commence par une espace
        current += b
    out.append(current)
    return b"\r\n ".join(out).decode("utf-8")


def parse_alert(alerte, start_day):
    """'veille HH:MM' | 'jour_meme HH:MM' | 'AAAA-MM-JJ HH:MM' -> datetime Paris."""
    m = re.fullmatch(r"(veille|jour_meme)\s+(\d{1,2}):(\d{2})", alerte.strip())
    if m:
        day = start_day - timedelta(days=1) if m[1] == "veille" else start_day
        return datetime.combine(day, time(int(m[2]), int(m[3])), PARIS)
    return datetime.strptime(alerte.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=PARIS)


def duration(delta):
    """timedelta -> durée iCal en heures/minutes/secondes uniquement (jamais de jours)."""
    secs = int(delta.total_seconds())
    sign, secs = ("-" if secs < 0 else ""), abs(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    body = (f"{h}H" if h else "") + (f"{m}M" if m else "") + (f"{s}S" if s else "")
    return f"{sign}PT{body or '0S'}"


def event_lines(ev):
    uid, titre = ev["id"], ev["titre"]
    allday = ev.get("journee_entiere", False)
    stamp = ev.get("dtstamp") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}"]
    if allday:
        du = date.fromisoformat(str(ev["du"]))
        au = date.fromisoformat(str(ev.get("au", ev["du"])))
        if au < du:
            raise ValueError(f"{uid}: 'au' avant 'du'")
        start = datetime.combine(du, time(0), PARIS)
        lines += [f"DTSTART;VALUE=DATE:{du:%Y%m%d}",
                  f"DTEND;VALUE=DATE:{au + timedelta(days=1):%Y%m%d}"]
    else:
        start = datetime.strptime(str(ev["debut"]), "%Y-%m-%d %H:%M").replace(tzinfo=PARIS)
        end = datetime.strptime(str(ev["fin"]), "%Y-%m-%d %H:%M").replace(tzinfo=PARIS)
        if end <= start:
            raise ValueError(f"{uid}: 'fin' doit être après 'debut'")
        lines += [f"DTSTART;TZID=Europe/Paris:{start:%Y%m%dT%H%M%S}",
                  f"DTEND;TZID=Europe/Paris:{end:%Y%m%dT%H%M%S}"]
    lines.append(f"SUMMARY:{escape(titre)}")
    if ev.get("description"):
        lines.append(f"DESCRIPTION:{escape(ev['description'])}")
    if ev.get("categorie"):
        lines.append(f"CATEGORIES:{escape(ev['categorie'])}")
    lines += ["STATUS:CONFIRMED", f"TRANSP:{'TRANSPARENT' if allday else 'OPAQUE'}"]
    if ev.get("alerte"):
        # différence en temps réel (UTC) : tient compte du passage heure d'été/hiver
        # (même tzinfo => Python soustrait en heure murale, d'où le passage par UTC)
        trigger = (parse_alert(ev["alerte"], start.date()).astimezone(timezone.utc)
                   - start.astimezone(timezone.utc))
        texte = ev.get("alerte_texte") or f"Rappel : {titre}"
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{escape(texte)}",
                  f"TRIGGER:{duration(trigger)}", "END:VALARM"]
    lines.append("END:VEVENT")
    return lines


def load_events(path=SOURCE):
    events = yaml.safe_load(path.read_text(encoding="utf-8"))["evenements"] or []
    ids = [e["id"] for e in events]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ValueError(f"UID en double : {dup}")
    return events


def build(events):
    lines = list(HEADER)
    if any(not e.get("journee_entiere") for e in events):
        lines += VTIMEZONE
    for ev in events:
        lines += event_lines(ev)
    lines.append("END:VCALENDAR")
    return "".join(fold(l) + "\r\n" for l in lines)


if __name__ == "__main__":
    events = load_events()
    OUTPUT.write_bytes(build(events).encode("utf-8"))
    print(f"{OUTPUT.name} : {len(events)} événements", file=sys.stderr)
