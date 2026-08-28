"""
Notifications management + EMI reminder job.

OPS-facing config for every automated notification the system sends. Built with
an extensible schema (keyed by `type`) so more notification types can be added
later with no rework — this build ships a single hardcoded "EMI Reminder" entry.

Persistence: Mongo collection `notification_configs`, one document per type:
    {
      id, type, name, description, variables: [...],
      email: { enabled, to, from_addr, subject, body_html },
      sms:   { enabled, template_id },
      updated_at
    }

Reminder job (POST /api/ops/notifications/emi_reminder/run):
  - Reminder window is FIXED: day 5 → day 24 of the cycle (day-of-month).
    No reminders after day 24 — day 25 onward is bank-led handling (out of scope).
  - Reads Email/SMS config (incl. enabled toggles) from the saved notification,
    substitutes template variables, and STUBS sending via a mock provider (logs
    the rendered HTML + the SMS Template ID that would be dispatched).
  - Edge cases: both channels disabled -> skip entirely (no error); a variable
    with no value -> falls back to blank string rather than breaking the send.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

logger = logging.getLogger("biglyp")

OPS_ROLES = ["super_admin", "credit_ops"]

# Fixed reminder window (day-of-month, inclusive)
WINDOW_START_DAY = 5
WINDOW_END_DAY = 24

# ---------------------------------------------------------------------------
# Default seed config — the single supported notification type for this build.
# Schema is generic; adding more types later = insert another doc like this.
# ---------------------------------------------------------------------------
DEFAULT_CONFIGS = [
    {
        "type": "emi_reminder",
        "name": "EMI Reminder",
        "description": "Reminds parents about an upcoming / ongoing monthly EMI payment.",
        "variables": ["parent_name", "student_name", "emi_amount", "due_date", "school_name"],
        "email": {
            "enabled": True,
            "to": "{{parent_email}}",
            "from_addr": "fees@biglyp.com",
            "subject": "Reminder: {{student_name}}'s EMI of {{emi_amount}} is due on {{due_date}}",
            "body_html": (
                "<p>Hi {{parent_name}},</p>"
                "<p>This is a friendly reminder that the EMI of <b>{{emi_amount}}</b> "
                "for <b>{{student_name}}</b> at {{school_name}} is due on <b>{{due_date}}</b>.</p>"
                "<p>Please keep sufficient balance in your linked account so the auto-debit "
                "goes through smoothly.</p>"
                "<p>Warm regards,<br/>Team Biglyp</p>"
            ),
        },
        "sms": {
            "enabled": True,
            "template_id": "1707160000000012345",
        },
    },
]

# ---------------------------------------------------------------------------
# Dummy EMI records the reminder job runs against (stand-in for live EMI data).
# Each record carries everything needed to fill the template variables.
# ---------------------------------------------------------------------------
DUMMY_EMIS = [
    {
        "application_id": "APP-24817", "parent_name": "Rajesh Malhotra",
        "parent_email": "rajesh.m@example.com", "parent_phone": "+91 98200 11223",
        "student_name": "Aarav Malhotra", "emi_amount": 8500,
        "due_date": "10 Sep 2026", "school_name": "Horizon International School",
    },
    {
        "application_id": "APP-24790", "parent_name": "Sneha Iyer",
        "parent_email": "sneha.iyer@example.com", "parent_phone": "+91 99870 55412",
        "student_name": "Diya Iyer", "emi_amount": 12000,
        "due_date": "10 Sep 2026", "school_name": "Greenwood Academy",
    },
    {
        # NOTE: missing parent_name on purpose -> demonstrates blank fallback
        "application_id": "APP-24702", "parent_name": "",
        "parent_email": "guardian.reddy@example.com", "parent_phone": "+91 90000 34567",
        "student_name": "Kabir Reddy", "emi_amount": 9750,
        "due_date": "10 Sep 2026", "school_name": "St. Xavier's High",
    },
]

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class EmailChannel(BaseModel):
    enabled: bool = True
    to: str = ""
    from_addr: str = ""
    subject: str = ""
    body_html: str = ""


class SmsChannel(BaseModel):
    enabled: bool = False
    template_id: str = ""


class NotificationConfigIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    email: EmailChannel
    sms: SmsChannel


class RunJobIn(BaseModel):
    # Optional override of the "current day of month" to demo the window gate.
    run_day: Optional[int] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_VAR_RE = re.compile(r"{{\s*(\w+)\s*}}")


def render_template(template: str, ctx: dict) -> str:
    """Substitute {{var}} placeholders. Missing value -> blank string."""
    if not template:
        return ""
    return _VAR_RE.sub(lambda m: str(ctx.get(m.group(1), "")), template)


def _public(doc: dict) -> dict:
    doc = dict(doc)
    doc.pop("_id", None)
    return doc


def create_notifications_router(db, deps: dict):
    router = APIRouter(prefix="/api")
    require_roles = deps["require_roles"]

    async def _ensure_seed():
        for cfg in DEFAULT_CONFIGS:
            existing = await db.notification_configs.find_one({"type": cfg["type"]})
            if not existing:
                await db.notification_configs.insert_one({
                    "id": uuid.uuid4().hex,
                    **cfg,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })

    @router.get("/ops/notifications")
    async def list_notifications(user: dict = Depends(require_roles(*OPS_ROLES))):
        await _ensure_seed()
        out = []
        async for doc in db.notification_configs.find({}):
            out.append(_public(doc))
        return out

    @router.get("/ops/notifications/{ntype}")
    async def get_notification(ntype: str, user: dict = Depends(require_roles(*OPS_ROLES))):
        await _ensure_seed()
        doc = await db.notification_configs.find_one({"type": ntype})
        if not doc:
            return {"detail": "not found"}
        return _public(doc)

    @router.put("/ops/notifications/{ntype}")
    async def save_notification(ntype: str, body: NotificationConfigIn,
                                user: dict = Depends(require_roles(*OPS_ROLES))):
        await _ensure_seed()
        update = {
            "email": body.email.model_dump(),
            "sms": body.sms.model_dump(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if body.name is not None:
            update["name"] = body.name
        if body.description is not None:
            update["description"] = body.description
        await db.notification_configs.update_one(
            {"type": ntype}, {"$set": update}, upsert=True
        )
        doc = await db.notification_configs.find_one({"type": ntype})
        return _public(doc)

    @router.post("/ops/notifications/{ntype}/run")
    async def run_reminder_job(ntype: str, body: RunJobIn,
                               user: dict = Depends(require_roles(*OPS_ROLES))):
        await _ensure_seed()
        cfg = await db.notification_configs.find_one({"type": ntype})
        if not cfg:
            return {"ran": False, "reason": "notification config not found", "sends": []}

        email = cfg.get("email") or {}
        sms = cfg.get("sms") or {}
        email_enabled = bool(email.get("enabled"))
        sms_enabled = bool(sms.get("enabled"))

        run_day = body.run_day if body.run_day is not None else datetime.now(timezone.utc).day
        window_open = WINDOW_START_DAY <= run_day <= WINDOW_END_DAY

        base = {
            "ran": False,
            "run_day": run_day,
            "window": {"start": WINDOW_START_DAY, "end": WINDOW_END_DAY},
            "window_open": window_open,
            "email_enabled": email_enabled,
            "sms_enabled": sms_enabled,
            "sends": [],
        }

        # Edge case: both channels off -> skip entirely, no error.
        if not email_enabled and not sms_enabled:
            base["reason"] = "Both Email and SMS are disabled — nothing sent."
            logger.info("[EMI Reminder] both channels disabled — job skipped.")
            return base

        # Window gate: only send between day 5 and 24 of the cycle.
        if not window_open:
            base["reason"] = (
                f"Day {run_day} is outside the reminder window "
                f"({WINDOW_START_DAY}–{WINDOW_END_DAY}). Day 25+ is bank-led — nothing sent."
            )
            logger.info("[EMI Reminder] day %s outside window %s-%s — job skipped.",
                        run_day, WINDOW_START_DAY, WINDOW_END_DAY)
            return base

        sends = []
        for rec in DUMMY_EMIS:
            ctx = {
                "parent_name": rec.get("parent_name", ""),
                "student_name": rec.get("student_name", ""),
                "emi_amount": f"₹{rec.get('emi_amount', 0):,}",
                "due_date": rec.get("due_date", ""),
                "school_name": rec.get("school_name", ""),
                "parent_email": rec.get("parent_email", ""),
                "parent_phone": rec.get("parent_phone", ""),
            }
            entry = {
                "application_id": rec.get("application_id"),
                "recipient": rec.get("parent_name") or "(no name)",
                "due_date": rec.get("due_date"),
                "channels": [],
            }

            if email_enabled:
                rendered = {
                    "channel": "email",
                    "to": render_template(email.get("to", ""), ctx),
                    "from_addr": email.get("from_addr", ""),
                    "subject": render_template(email.get("subject", ""), ctx),
                    "body_html": render_template(email.get("body_html", ""), ctx),
                }
                entry["channels"].append(rendered)
                # ---- MOCK send (log only) ----
                logger.info("[EMI Reminder][MOCK EMAIL] to=%s from=%s subject=%s\nHTML:\n%s",
                            rendered["to"], rendered["from_addr"], rendered["subject"],
                            rendered["body_html"])

            if sms_enabled:
                rendered = {
                    "channel": "sms",
                    "to": ctx["parent_phone"],
                    "template_id": sms.get("template_id", ""),
                }
                entry["channels"].append(rendered)
                # ---- MOCK send (log only) ----
                logger.info("[EMI Reminder][MOCK SMS] to=%s template_id=%s (copy lives with DLT provider)",
                            rendered["to"], rendered["template_id"])

            sends.append(entry)

        base["ran"] = True
        base["sends"] = sends
        base["reason"] = (
            f"Sent via {', '.join([c for c, on in [('Email', email_enabled), ('SMS', sms_enabled)] if on])} "
            f"to {len(sends)} recipient(s) (mock provider — logged, not actually dispatched)."
        )
        logger.info("[EMI Reminder] job ran on day %s — %s recipient(s).", run_day, len(sends))
        return base

    return {"router": router, "ensure_seed": _ensure_seed}
