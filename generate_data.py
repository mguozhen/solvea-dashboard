#!/usr/bin/env python3
"""Generate data.json for the web dashboard. Run before deploying or on a cron."""

import json
import os
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, "/Users/guozhen/MailOutbound")

VOICE_LOG       = Path("/Users/guozhen/MailOutbound/voice_sdr_log.json")
FOLLOWUP_LOG    = Path("/Users/guozhen/MailOutbound/followup_log.json")
APOLLO_LOG      = Path("/Users/guozhen/solvea_outreach_log.json")
STORELEADS_PROG = Path("/Users/guozhen/storeleads_progress.json")
TRACKING_DB     = Path("/Users/guozhen/MailOutbound/tracking.db")
PR_TRACKER      = Path("/tmp/solvea-pr-agent/media/outreach_tracker.md")
BOUNCE_FILE     = Path("/Users/guozhen/MailOutbound/bounced_emails.json")
OUTPUT          = Path(__file__).parent / "data.json"


def main():
    today = date.today().isoformat()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Voice SDR
    voice = {"total_calls": 0, "total_picked": 0, "total_sms": 0,
             "today_calls": 0, "today_picked": 0, "today_sms": 0, "recent": []}
    if VOICE_LOG.exists():
        log = json.loads(VOICE_LOG.read_text())
        today_calls = [c for c in log.get("calls", []) if c.get("ts", "").startswith(today)]
        voice = {
            "total_calls": log.get("total_calls", 0),
            "total_picked": log.get("total_picked", 0),
            "total_sms": log.get("total_sms", 0),
            "today_calls": len(today_calls),
            "today_picked": sum(1 for c in today_calls if c.get("picked_up")),
            "today_sms": sum(1 for c in today_calls if c.get("sms_sent")),
            "recent": today_calls[-15:],
        }

    # Email
    apollo_total = apollo_today = 0
    if APOLLO_LOG.exists():
        log = json.loads(APOLLO_LOG.read_text())
        apollo_total = log.get("total_sent", 0)
        apollo_today = sum(1 for e in log.get("sent", [])
                          if e.get("ts", "").startswith(today) and e.get("status") == "sent")
    sl_sent = 0
    if STORELEADS_PROG.exists():
        sl_sent = json.loads(STORELEADS_PROG.read_text()).get("total_sent", 0)
    bounced = 0
    if BOUNCE_FILE.exists():
        bounced = len(json.loads(BOUNCE_FILE.read_text()))
    followups = 0
    if FOLLOWUP_LOG.exists():
        followups = json.loads(FOLLOWUP_LOG.read_text()).get("total", 0)

    email = {"apollo_total": apollo_total, "apollo_today": apollo_today,
             "sl_sent": sl_sent, "bounced": bounced, "followups": followups}

    # Tracking
    tracking = {"tracked": 0, "opens": 0, "clicks": 0, "replies": 0, "booked": 0, "hot_leads": []}
    if TRACKING_DB.exists():
        db = sqlite3.connect(str(TRACKING_DB))
        tracking["tracked"] = db.execute("SELECT COUNT(DISTINCT email_id) FROM sent").fetchone()[0]
        tracking["opens"] = db.execute("SELECT COUNT(DISTINCT email_id) FROM opens").fetchone()[0]
        tracking["clicks"] = db.execute("SELECT COUNT(DISTINCT email_id) FROM clicks").fetchone()[0]
        hot = db.execute("""
            SELECT s.to_addr, s.subject, s.email_id, s.ts,
                   (SELECT COUNT(*) FROM opens o WHERE o.email_id = s.email_id) as oc,
                   (SELECT COUNT(*) FROM clicks c WHERE c.email_id = s.email_id) as cc
            FROM sent s
            WHERE s.to_addr IS NOT NULL AND s.to_addr != ''
              AND (EXISTS (SELECT 1 FROM opens o WHERE o.email_id = s.email_id)
                   OR EXISTS (SELECT 1 FROM clicks c WHERE c.email_id = s.email_id))
            ORDER BY cc DESC, oc DESC LIMIT 20
        """).fetchall()
        tracking["hot_leads"] = [{"email": r[0], "subject": (r[1] or "")[:40],
                                   "sent_at": (r[3] or "")[:16], "opens": r[4], "clicks": r[5]} for r in hot]
        db.close()

    # PR
    pitched = pending = 0
    if PR_TRACKER.exists():
        text = PR_TRACKER.read_text()
        pitched = text.count("已投") + text.count("已发送")
        pending = text.count("待投")
    total_targets = 0
    for pattern in ["*MEDIA*.md", "*TARGETS*.md", "*SOLOPRENEUR*.md", "*ECOMMERCE*.md", "*LEGAL*.md"]:
        for f in Path("/Users/guozhen/MailOutbound").glob(pattern):
            lines = f.read_text().split("\n")
            rows = [l for l in lines if l.startswith("|") and "---" not in l
                    and "Name" not in l[:10] and "#" not in l[:5] and "Metric" not in l[:10]]
            total_targets += len(rows)
    pr = {"pitched": pitched, "pending": pending, "total_targets": total_targets, "replies": 0}

    data = {
        "generated": now,
        "date": today,
        "voice": voice,
        "email": email,
        "tracking": tracking,
        "pr": pr,
    }

    OUTPUT.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"data.json written to {OUTPUT}")


if __name__ == "__main__":
    main()
