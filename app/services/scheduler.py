"""
APScheduler background jobs for BauNavigator.
Initialised once in create_app(); safe for multi-worker setups because
we guard against duplicate scheduler starts.
"""
from __future__ import annotations
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

_scheduler = None  # module-level singleton


def init_scheduler(app):
    global _scheduler
    if _scheduler is not None:
        return  # already running

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("apscheduler not installed — deadline reminders disabled.")
        return

    _scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Berlin")
    _scheduler.add_job(
        func=lambda: _send_deadline_reminders(app),
        trigger=CronTrigger(hour=8, minute=0),   # every day at 08:00 Berlin
        id="deadline_reminders",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Law Update Agent — runs on the 1st of every month at 03:00
    _scheduler.add_job(
        func=lambda: _run_law_agent(app),
        trigger=CronTrigger(day=1, hour=3, minute=0),
        id="law_updates",
        replace_existing=True,
        misfire_grace_time=7200,
    )
    _scheduler.start()
    logger.info("APScheduler started — deadline_reminders + law_updates jobs registered.")


def _send_deadline_reminders(app):
    """
    Scan for project stages whose deadline_at is TODAY or in 3 / 7 days.
    Send an email reminder to the project owner.
    """
    with app.app_context():
        try:
            from app import db, mail
            from app.models.models import ProjectStage, Project, User
            from app.models.enums import StageStatus, STAGE_LABELS
            from flask_mail import Message as MailMessage

            today = date.today()
            warn_days = [0, 3, 7]
            target_dates = [today + timedelta(days=d) for d in warn_days]

            stages = (
                ProjectStage.query
                .filter(
                    ProjectStage.deadline_at.in_(target_dates),
                    ProjectStage.status.notin_([StageStatus.DONE]),
                )
                .all()
            )

            if not stages:
                return

            # Group by user
            user_stages: dict[str, list] = {}
            for stage in stages:
                uid = stage.project.user_id
                user_stages.setdefault(uid, []).append(stage)

            for uid, user_stage_list in user_stages.items():
                user = User.query.get(uid)
                if not user or not user.email:
                    continue

                rows = []
                for s in user_stage_list:
                    days_left = (s.deadline_at - today).days
                    label = STAGE_LABELS.get(s.stage_key, s.stage_key.value)
                    project_title = s.project.title
                    rows.append((project_title, label, s.deadline_at, days_left))

                lines_html = "".join(
                    f"<tr>"
                    f"<td>{r[0]}</td>"
                    f"<td>{r[1]}</td>"
                    f"<td>{r[2].strftime('%d.%m.%Y')}</td>"
                    f"<td style='color:{'red' if r[3]==0 else 'orange' if r[3]<=3 else 'black'}'>"
                    f"{'HEUTE' if r[3]==0 else f'in {r[3]} Tagen'}</td>"
                    f"</tr>"
                    for r in rows
                )

                body = f"""
<p>Hallo {user.full_name or user.email},</p>
<p>folgende Bauabschnitte haben bald einen Fristablauf:</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:13px;">
  <thead>
    <tr style="background:#f3f4f6;">
      <th>Projekt</th><th>Bauschritt</th><th>Frist</th><th>Status</th>
    </tr>
  </thead>
  <tbody>{lines_html}</tbody>
</table>
<p style="margin-top:16px;">
  <a href="https://baunavigator.de/project/" style="background:#2563eb;color:#fff;
  padding:8px 16px;border-radius:6px;text-decoration:none;">Zum Projekt</a>
</p>
<p style="color:#888;font-size:11px;margin-top:20px;">
  Diese E-Mail wurde automatisch von BauNavigator gesendet.
</p>
"""
                try:
                    msg = MailMessage(
                        subject=f"BauNavigator — Frist-Erinnerung: {len(rows)} Bauschritt(e)",
                        recipients=[user.email],
                        html=body,
                    )
                    mail.send(msg)
                    logger.info("Deadline reminder sent to %s (%d stages)", user.email, len(rows))
                except Exception as exc:
                    logger.error("Failed to send reminder to %s: %s", user.email, exc)

        except Exception as exc:
            logger.error("Deadline reminder job error: %s", exc)


def _run_law_agent(app):
    """Monthly job: check all due law sources for content changes."""
    with app.app_context():
        try:
            from app.services.law_agent import check_due_sources, seed_default_sources
            # Ensure default sources exist
            seed_default_sources()
            stats = check_due_sources()
            logger.info(
                "Law update job done — checked:%d changed:%d errors:%d",
                stats.get('checked', 0), stats.get('changed', 0), stats.get('errors', 0),
            )
        except Exception as exc:
            logger.error("Law update job error: %s", exc)

