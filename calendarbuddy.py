#!/usr/bin/env python3
"""
CalendarBuddy - Sync macOS Calendar to SQLite with change tracking

Copyright (C) 2025 Sujit Patel

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

---

Sync macOS Calendar (via icalBuddy) to a local SQLite DB and print stored data.

This script:
  - Fetches today's events using `icalBuddy eventsFrom:today to:today`.
  - Keeps a compact `events` table with current/historical event versions.
  - Keeps an append-only `changes` table (audit log).
  - Can print current events or change history in table / json / csv formats.

Place this file at ~/calendarbuddy.py and make executable:
  chmod +x ~/calendarbuddy.py

Typical cron (every 30 minutes):
  */30 * * * * /usr/bin/python3 /Users/<you>/calendarbuddy.py

Run `./calendarbuddy.py --help` for full usage.
"""
from pathlib import Path
import subprocess
import re
import sqlite3
from datetime import datetime, date, time, timedelta
import hashlib
import argparse
import json
import csv
import sys

HOME = Path.home()
DB_PATH = HOME / ".calendar_events.db"
VERSION = "2.0.0"

# Patterns
BULLET_PREFIX = re.compile(r"^\s*[•\*]\s*")  # accept only • and * as title bullets
# date-range like "15 Sep 2025 - 29 Sep 2025" or "2025-09-15 - 2025-09-29"
DATE_RANGE_RE1 = re.compile(r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\s*-\s*(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})")
DATE_RANGE_RE2 = re.compile(r"(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})")
# time-range with optional full date prefix like "2025-09-21 11:30 - 12:00" or "11:30 AM - 12:00 PM"
TIME_RANGE_RE = re.compile(
    r"(?:(\d{4}-\d{2}-\d{2})\s+)?(\d{1,2}:\d{2}(?:\s*[APMapm\.]{2,4})?)\s*-\s*(\d{1,2}:\d{2}(?:\s*[APMapm\.]{2,4})?)",
    re.IGNORECASE
)
# time-range with "at" keyword like "2025-11-02 at 11:30 AM - 12:00 PM"
TIME_RANGE_AT_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s+at\s+(\d{1,2}:\d{2}(?:\s*[APMapm\.]{2,4})?)\s*-\s*(\d{1,2}:\d{2}(?:\s*[APMapm\.]{2,4})?)",
    re.IGNORECASE
)

URL_RE = re.compile(r"https?://[^\s'\")<>]+", re.IGNORECASE)
MEETING_DOMAINS_PRIORITY = [
    "zoom.us",
    "meet.google.com",
    "teams.microsoft.com",
    "webex.com",
    "gotomeeting.com",
    "gotowebinar.com",
    "jitsi",
    "whereby.com",
    "bluejeans.com",
]

def extract_meeting_link_from_lines(lines):
    """
    Given list of text lines (notes/attendees block), return best meeting URL or None.
    - Prefers known meeting provider domains; otherwise returns first http(s) url found.
    """
    urls = []
    for L in lines:
        if not L:
            continue
        for m in URL_RE.findall(L):
            u = m.rstrip(".,;:)'\"")   # strip trailing punctuation
            urls.append(u)
    if not urls:
        return None
    for domain in MEETING_DOMAINS_PRIORITY:
        for u in urls:
            if domain in u.lower():
                return u
    return urls[0]

def normalize_spaces(s: str) -> str:
    if s is None:
        return s
    s = s.replace("\u00A0", " ")
    s = s.replace("\u202F", " ")
    s = s.replace("\u2009", " ")
    s = re.sub(r"[ \t\r\f\v]+", " ", s)
    return s

def run_icalbuddy(write_raw=False, lookback_days=0):
    """
    Call icalBuddy with absolute date/time (no relative dates) and return normalized lines.
    Uses the two-arg form for range with lookback support.
    
    Args:
        write_raw: Whether to write raw output to file for debugging
        lookback_days: Number of days to look back from today (0 = today only)
    """
    today = date.today()
    start_date = today - timedelta(days=lookback_days)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = today.strftime("%Y-%m-%d")
    
    cmd = ["icalBuddy", "-nrd", "-df", "%Y-%m-%d", "-tf", "%I:%M %p", f"eventsFrom:{start_str}", f"to:{end_str}"]
    try:
        rc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise SystemExit("icalBuddy command timed out after 30 seconds")
    except FileNotFoundError:
        raise SystemExit("icalBuddy not found. Install with: brew install ical-buddy")
    
    used = f"eventsFrom:{start_str} to:{end_str}"
    if rc.returncode != 0 or not rc.stdout.strip():
        # fallback to today only if range fails
        cmd2 = ["icalBuddy", "-nrd", "-df", "%Y-%m-%d", "-tf", "%I:%M %p", "eventsToday"]
        try:
            rc = subprocess.run(cmd2, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            raise SystemExit("icalBuddy command timed out after 30 seconds")
        
        used = "eventsToday (fallback)"
        if rc.returncode != 0:
            raise SystemExit(f"icalBuddy failed: {rc.stderr.strip()}")
    
    out = rc.stdout
    if write_raw:
        try:
            Path.home().joinpath("icalbuddy_raw.txt").write_text(out, encoding="utf-8")
        except Exception:
            pass
    return normalize_spaces(out).splitlines()

# date parsing helpers
def try_parse_date_to_iso(s: str):
    """Parse dates like '15 Sep 2025' or '2025-09-15' into 'YYYY-MM-DD' (string)"""
    if not s:
        return None
    s = s.strip()
    s = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', s, flags=re.IGNORECASE)
    fmts = ["%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%b %d %Y", "%B %d %Y"]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except Exception:
            pass
    # last resort: try parsing with datetime's flexible parsing (limited)
    try:
        p = datetime.fromisoformat(s)
        return p.date().isoformat()
    except Exception:
        return None

def parse_time_with_optional_am_pm(time_str: str):
    """
    Parse time fragments like "11:30", "11:30 AM", "11:30PM" into (hour, minute).
    Returns (hour, minute) in 24-hour clock.
    """
    t = time_str.strip().replace(".", "")
    # try with AM/PM
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            dt = datetime.strptime(t.upper(), fmt)
            return dt.hour, dt.minute
        except Exception:
            pass
    # fallback: parse "HH:MM" naive
    m = re.match(r"^(\d{1,2}):(\d{2})", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None

def to_iso_datetime_str(date_iso: str, hour: int, minute: int):
    """Return 'YYYY-MM-DDThh:mm:ss' string using given date and hour/minute (no timezone changes)."""
    if date_iso is None:
        return None
    hh = f"{hour:02d}"
    mm = f"{minute:02d}"
    return f"{date_iso}T{hh}:{mm}:00"

def parse_events(lines):
    """
    Parse icalBuddy lines into list of (title, start_time_iso, end_time_iso, meeting_link).
    - For timed events: parse date and times to ISO datetimes YYYY-MM-DDThh:mm:ss
    - For all-day/multi-day: parse date range and create start_time = YYYY-MM-DDT00:00:00,
      end_time = YYYY-MM-DDT23:59:59 (so whole-day coverage)
    - Collect subsequent non-title lines into a buffer to scan for meeting links.
    """
    events = []
    cur_title = None
    cur_start = None
    cur_end = None
    buffer_lines = []

    def commit():
        nonlocal cur_title, cur_start, cur_end, buffer_lines
        if cur_title is not None:
            link = extract_meeting_link_from_lines(buffer_lines)
            events.append((cur_title, cur_start, cur_end, link))
        cur_title = None
        cur_start = None
        cur_end = None
        buffer_lines = []

    for raw in lines:
        if raw is None:
            continue
        line = raw.rstrip()
        if not line:
            continue
        line = normalize_spaces(line)

        # Title lines
        if BULLET_PREFIX.match(line):
            if cur_title is not None:
                commit()
            title = BULLET_PREFIX.sub("", line).strip()
            title = re.sub(r"\s*\([^)]*@[^)]*\)$", "", title).strip()
            cur_title = title
            cur_start = None
            cur_end = None
            buffer_lines = []
            continue

        # Buffer non-title lines and parse for dates/times
        if cur_title is not None:
            buffer_lines.append(line)

            m1 = DATE_RANGE_RE1.search(line)
            if m1:
                s_iso = try_parse_date_to_iso(m1.group(1))
                e_iso = try_parse_date_to_iso(m1.group(2))
                if s_iso and e_iso:
                    cur_start = f"{s_iso}T00:00:00"
                    cur_end = f"{e_iso}T23:59:59"
                    continue

            m2 = DATE_RANGE_RE2.search(line)
            if m2:
                s_iso = try_parse_date_to_iso(m2.group(1))
                e_iso = try_parse_date_to_iso(m2.group(2))
                if s_iso and e_iso:
                    cur_start = f"{s_iso}T00:00:00"
                    cur_end = f"{e_iso}T23:59:59"
                    continue

            # Check for "YYYY-MM-DD at HH:MM AM/PM - HH:MM AM/PM" format first
            mt_at = TIME_RANGE_AT_RE.search(line)
            if mt_at:
                date_prefix = mt_at.group(1)
                t1 = mt_at.group(2)
                t2 = mt_at.group(3)
                date_iso = try_parse_date_to_iso(date_prefix)
                h1, m1 = parse_time_with_optional_am_pm(t1)
                h2, m2 = parse_time_with_optional_am_pm(t2)
                if date_iso and h1 is not None and h2 is not None:
                    cur_start = to_iso_datetime_str(date_iso, h1, m1)
                    cur_end = to_iso_datetime_str(date_iso, h2, m2)
                    continue

            # Check for regular time range format
            mt = TIME_RANGE_RE.search(line)
            if mt:
                date_prefix = mt.group(1)
                t1 = mt.group(2)
                t2 = mt.group(3)
                if date_prefix:
                    date_iso = try_parse_date_to_iso(date_prefix)
                else:
                    date_iso = date.today().isoformat()
                h1, m1 = parse_time_with_optional_am_pm(t1)
                h2, m2 = parse_time_with_optional_am_pm(t2)
                if h1 is not None and h2 is not None:
                    cur_start = to_iso_datetime_str(date_iso, h1, m1)
                    cur_end = to_iso_datetime_str(date_iso, h2, m2)
                    continue

            if re.match(r"^\d{4}-\d{2}-\d{2}$", line.strip()):
                d = line.strip()
                cur_start = f"{d}T00:00:00"
                cur_end = f"{d}T23:59:59"
                continue

            continue

    if cur_title is not None:
        commit()
    return events

# DB helpers & migrations
def init_db(conn):
    c = conn.cursor()
    # Create events table if not exists (with start_time and end_time)
    c.execute("""
    CREATE TABLE IF NOT EXISTS events (
        uid TEXT PRIMARY KEY,
        title TEXT,
        start_time TEXT,
        end_time TEXT,
        first_seen TEXT,
        last_seen TEXT,
        meeting_link TEXT,
        deleted INTEGER DEFAULT 0
    )""")
    # create changes table if not exists (store start_time/end_time)
    c.execute("""
    CREATE TABLE IF NOT EXISTS changes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        action TEXT,
        uid TEXT,
        title TEXT,
        start_time TEXT,
        end_time TEXT,
        meeting_link TEXT
    )""")
    # Add indexes for better performance
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_start_time ON events(start_time)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_events_deleted ON events(deleted)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_changes_ts ON changes(ts)")
    conn.commit()
    
    # Ensure columns exist for older DBs (safe additive)
    ensure_column(conn, "events", "start_time")
    ensure_column(conn, "events", "end_time")
    ensure_column(conn, "events", "meeting_link")
    ensure_column(conn, "changes", "start_time")
    ensure_column(conn, "changes", "end_time")
    ensure_column(conn, "changes", "meeting_link")
    conn.commit()

def ensure_column(conn, table, column):
    """Add column if missing (no-op if exists)."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")

def load_db_map(conn):
    c = conn.cursor()
    rows = c.execute("SELECT uid, title, start_time, end_time, first_seen, last_seen, deleted, meeting_link FROM events").fetchall()
    return {
        r[0]: {
            "uid": r[0],
            "title": r[1],
            "start_time": r[2],
            "end_time": r[3],
            "first_seen": r[4],
            "last_seen": r[5],
            "deleted": r[6],
            "meeting_link": r[7] if len(r) > 7 else None,
        }
        for r in rows
    }

def record_change(conn, action, uid, title, start_time, end_time, meeting_link):
    ts = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO changes (ts, action, uid, title, start_time, end_time, meeting_link) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ts, action, uid, title, start_time, end_time, meeting_link),
    )

def uid_for(title, start_time, end_time):
    raw = (title or "") + "||" + (start_time or "") + "||" + (end_time or "")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def process_and_sync(events, conn, dry_run=False, lookback_mode=False):
    """
    events: list of (title, start_time_iso, end_time_iso, meeting_link)
    lookback_mode: if True, don't mark events as removed (since we're not syncing all current events)
    """
    now = datetime.now().isoformat()
    db_map = load_db_map(conn)
    current_uids = set()

    for title, s_iso, e_iso, mlink in events:
        uid = uid_for(title, s_iso, e_iso)
        current_uids.add(uid)
        
        if uid in db_map:
            # Event already exists, just update last_seen and ensure it's not deleted
            if not dry_run:
                conn.execute("UPDATE events SET last_seen=?, deleted=0, meeting_link=? WHERE uid=?", (now, mlink, uid))
        else:
            # New event - check for existing records with same title (active) -> treat as update if times differ
            existing_same_title = [r for r in db_map.values() if r["title"] == title and r["deleted"] == 0]
            if existing_same_title:
                for old in existing_same_title:
                    if not dry_run:
                        conn.execute("UPDATE events SET deleted=1, last_seen=? WHERE uid=?", (now, old["uid"]))
                        record_change(conn, "updated-old-marked-deleted", old["uid"], old["title"], old["start_time"], old["end_time"], old.get("meeting_link"))
                
                # Use INSERT OR REPLACE to handle potential constraint violations
                if not dry_run:
                    conn.execute(
                        "INSERT OR REPLACE INTO events (uid, title, start_time, end_time, first_seen, last_seen, deleted, meeting_link) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                        (uid, title, s_iso, e_iso, now, now, mlink),
                    )
                    record_change(conn, "added (updated)", uid, title, s_iso, e_iso, mlink)
            else:
                # Completely new event - use INSERT OR REPLACE to be safe
                if not dry_run:
                    conn.execute(
                        "INSERT OR REPLACE INTO events (uid, title, start_time, end_time, first_seen, last_seen, deleted, meeting_link) VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                        (uid, title, s_iso, e_iso, now, now, mlink),
                    )
                    record_change(conn, "added", uid, title, s_iso, e_iso, mlink)

    # Only mark events as removed if we're not in lookback mode
    # In lookback mode, we're syncing historical events, not current state
    if not lookback_mode:
        for uid, row in db_map.items():
            if row["deleted"] == 0 and uid not in current_uids:
                if not dry_run:
                    conn.execute("UPDATE events SET deleted=1, last_seen=? WHERE uid=?", (now, uid))
                    record_change(conn, "removed", uid, row["title"], row["start_time"], row["end_time"], row.get("meeting_link"))

    if not dry_run:
        conn.commit()

# printing helpers (updated headers to include start_time/end_time)
def rows_to_table(rows, headers):
    col_widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            s = "" if cell is None else str(cell)
            if len(s) > col_widths[i]:
                col_widths[i] = len(s)
    sep = "  "
    lines = []
    header_line = sep.join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_line)
    lines.append(sep.join("-" * col_widths[i] for i in range(len(headers))))
    for r in rows:
        lines.append(sep.join((("" if c is None else str(c)).ljust(col_widths[i])) for i, c in enumerate(r)))
    return "\n".join(lines)

def print_table(rows, headers):
    print(rows_to_table(rows, headers))

def print_json(rows, headers):
    out = [dict(zip(headers, r)) for r in rows]
    print(json.dumps(out, indent=2, ensure_ascii=False))

def print_csv(rows, headers):
    w = csv.writer(sys.stdout)
    w.writerow(headers)
    for r in rows:
        w.writerow([("" if c is None else c) for c in r])

# queries
def events_on_date_query(conn, target_date):
    """
    Return rows for events that overlap target_date.
    The start_time/end_time are stored as 'YYYY-MM-DDThh:mm:ss' (or 'YYYY-MM-DDT00:00:00' for all-day).
    We use date(start_time) and date(end_time) to compare.
    """
    c = conn.cursor()
    rows = c.execute(
        """
        SELECT title, start_time, end_time, meeting_link
        FROM events
        WHERE deleted=0
          AND date(start_time) <= date(?)
          AND date(end_time)   >= date(?)
        ORDER BY start_time
        """,
        (target_date, target_date)
    ).fetchall()
    return rows

def events_in_range_query(conn, from_date=None, to_date=None):
    """
    Return rows for events that overlap the [from_date, to_date] range (both inclusive).
    If from_date is None -> treat as unbounded past. If to_date None -> unbounded future.
    """
    c = conn.cursor()
    if from_date and to_date:
        rows = c.execute(
            """
            SELECT title, start_time, end_time, meeting_link
            FROM events
            WHERE deleted=0
              AND date(start_time) <= date(?)
              AND date(end_time)   >= date(?)
            ORDER BY start_time
            """,
            (to_date, from_date)
        ).fetchall()
        return rows
    elif from_date:
        rows = c.execute(
            """
            SELECT title, start_time, end_time, meeting_link
            FROM events
            WHERE deleted=0
              AND date(end_time) >= date(?)
            ORDER BY start_time
            """,
            (from_date,)
        ).fetchall()
        return rows
    elif to_date:
        rows = c.execute(
            """
            SELECT title, start_time, end_time, meeting_link
            FROM events
            WHERE deleted=0
              AND date(start_time) <= date(?)
            ORDER BY start_time
            """,
            (to_date,)
        ).fetchall()
        return rows
    else:
        # no bounds -> return all active events
        return c.execute("SELECT title, start_time, end_time, meeting_link FROM events WHERE deleted=0 ORDER BY start_time").fetchall()

def get_changes(conn, since_ts=None):
    c = conn.cursor()
    if since_ts:
        rows = c.execute("SELECT ts, action, uid, title, start_time, end_time, meeting_link FROM changes WHERE ts >= ? ORDER BY ts", (since_ts,)).fetchall()
    else:
        rows = c.execute("SELECT ts, action, uid, title, start_time, end_time, meeting_link FROM changes ORDER BY ts").fetchall()
    return rows

def show_db(conn):
    c = conn.cursor()
    print("=== events ===")
    for r in c.execute("SELECT uid, title, start_time, end_time, first_seen, last_seen, meeting_link, deleted FROM events ORDER BY first_seen"):
        print(r)
    print("\n=== changes (last 50) ===")
    for r in c.execute("SELECT id, ts, action, uid, title, start_time, end_time, meeting_link FROM changes ORDER BY id DESC LIMIT 50"):
        print(r)

# CLI and main
def parse_since_arg(s):
    if not s:
        return None
    if s.lower().endswith("h"):
        try:
            hrs = int(s[:-1])
            return (datetime.now() - timedelta(hours=hrs)).isoformat()
        except:
            raise ValueError("Invalid hours format for --since (e.g. 48h)")
    try:
        _ = datetime.fromisoformat(s)
        return s
    except:
        raise ValueError("Invalid --since value; provide ISO datetime or e.g. 48h")

def validate_iso_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except Exception:
        return False

def main():
    epilog = f"""
Examples:
  Sync today only (typically run by cron):
    ./calendarbuddy.py

  Sync with 7-day lookback:
    ./calendarbuddy.py --lookback 7

  Sync with 30-day lookback:
    ./calendarbuddy.py --lookback 30

  View today's events:
    ./calendarbuddy.py --view --format table

  View events for a single date:
    ./calendarbuddy.py --view --date 2025-10-21 --format table

  View events in a date range:
    ./calendarbuddy.py --view --from 2025-10-01 --to 2025-10-31 --format json

  View changes in the last 6 hours:
    ./calendarbuddy.py --print-changes --since 6h --format table

DB file: {DB_PATH}
CalendarBuddy v{VERSION} - https://github.com/yourusername/CalendarBuddy
"""
    p = argparse.ArgumentParser(description="Sync macOS Calendar (icalBuddy) to SQLite and print in table/json/csv formats.", epilog=epilog, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"CalendarBuddy {VERSION}")
    p.add_argument("--view", action="store_true", help="View active (non-deleted) events and exit.")
    p.add_argument("--print-current", action="store_true", help=argparse.SUPPRESS)  # Hidden backward compatibility
    p.add_argument("--date", help="(YYYY-MM-DD) Show events for a specific date. Mutually exclusive with --from/--to.")
    p.add_argument("--from", dest="from_date", help="(YYYY-MM-DD) Start date for range filter (inclusive).")
    p.add_argument("--to", dest="to_date", help="(YYYY-MM-DD) End date for range filter (inclusive).")
    p.add_argument("--print-changes", action="store_true", help="Print changes history and exit.")
    p.add_argument("--format", choices=["table","json","csv"], default="table", help="Output format for print commands.")
    p.add_argument("--since", help="Filter changes since ISO timestamp or '<Nh' (hours). Only for --print-changes.")
    p.add_argument("--show-db", action="store_true", help="Debug: dump raw DB rows.")
    p.add_argument("--dry-run", action="store_true", help="Run sync logic but don't write DB/changes (useful for testing).")
    p.add_argument("--lookback", type=int, default=0, help="Number of days to look back from today for syncing (default: 0, today only).")
    args = p.parse_args()

    # validate mutually exclusive usage
    if args.date and (args.from_date or args.to_date):
        print("Error: --date is mutually exclusive with --from/--to", file=sys.stderr)
        sys.exit(1)
    if args.date and not validate_iso_date(args.date):
        print("Error: --date must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    if args.from_date and not validate_iso_date(args.from_date):
        print("Error: --from must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)
    if args.to_date and not validate_iso_date(args.to_date):
        print("Error: --to must be YYYY-MM-DD", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    init_db(conn)

    # Handle backward compatibility
    if args.print_current:
        args.view = True
    
    # Print / debug modes (do not sync)
    if args.view or args.print_changes or args.show_db:
        if args.show_db:
            show_db(conn)
            conn.close()
            return

        if args.view:
            # determine filter
            if args.date:
                rows = events_on_date_query(conn, args.date)
            elif args.from_date or args.to_date:
                rows = events_in_range_query(conn, args.from_date, args.to_date)
            else:
                # default: today's date
                rows = events_on_date_query(conn, date.today().isoformat())

            headers = ["title", "start_time", "end_time", "meeting_link"]
            if args.format == "table":
                print_table(rows, headers)
            elif args.format == "json":
                print_json(rows, headers)
            else:
                print_csv(rows, headers)
            conn.close()
            return

        if args.print_changes:
            since_ts = None
            if args.since:
                try:
                    since_ts = parse_since_arg(args.since)
                except Exception as e:
                    print("Invalid --since:", e, file=sys.stderr)
                    conn.close()
                    sys.exit(1)
            rows = get_changes(conn, since_ts)
            headers = ["ts","action","uid","title","start_time","end_time","meeting_link"]
            if args.format == "table":
                print_table(rows, headers)
            elif args.format == "json":
                print_json(rows, headers)
            else:
                print_csv(rows, headers)
            conn.close()
            return

    # Default: fetch and sync
    try:
        raw_lines = run_icalbuddy(write_raw=True, lookback_days=args.lookback)
    except SystemExit as e:
        print("Error running icalBuddy:", e, file=sys.stderr)
        conn.close()
        sys.exit(1)

    events = parse_events(raw_lines)
    lookback_mode = args.lookback > 0
    process_and_sync(events, conn, dry_run=args.dry_run, lookback_mode=lookback_mode)
    conn.close()
    
    if args.dry_run:
        lookback_msg = f" (lookback: {args.lookback} days)" if args.lookback > 0 else ""
        print(f"DRY RUN: Would have processed {len(events)} events{lookback_msg}. DB at: {DB_PATH}")
    else:
        lookback_msg = f" (lookback: {args.lookback} days)" if args.lookback > 0 else ""
        print(f"Processed {len(events)} events{lookback_msg}. DB stored at: {DB_PATH}")

if __name__ == "__main__":
    main()
