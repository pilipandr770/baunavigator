"""
Notification Service — BauNavigator
=====================================
Создаёт уведомления в БД и отправляет email-дайджест.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from flask import current_app, url_for

logger = logging.getLogger(__name__)


# ── Создание уведомления ───────────────────────────────────────────────────

def notify(
    user_id: str,
    type_: str,          # NotificationType value
    title: str,
    message: str = '',
    link: str = '',
    project_id: Optional[str] = None,
) -> None:
    """Создаёт запись Notification в БД. Безопасно вызывать из фоновых задач."""
    try:
        from app import db
        from app.models.models import Notification
        from app.models.enums import NotificationType
        n = Notification(
            user_id=user_id,
            project_id=project_id,
            type=NotificationType(type_),
            title=title,
            message=message,
            link=link,
        )
        db.session.add(n)
        db.session.commit()
    except Exception as exc:
        logger.error(f'notify() error: {exc}')


# ── Получение непрочитанных ────────────────────────────────────────────────

def get_unread_count(user_id: str) -> int:
    try:
        from app.models.models import Notification
        return Notification.query.filter_by(user_id=user_id, is_read=False).count()
    except Exception:
        return 0


def get_notifications(user_id: str, limit: int = 30):
    from app.models.models import Notification
    return (
        Notification.query
        .filter_by(user_id=user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


# ── Email дайджест (вызывается из APScheduler) ────────────────────────────

def send_daily_digest(app=None):
    """
    Отправляет email с непрочитанными уведомлениями за последние 24 часа
    каждому пользователю у которого они есть.
    Вызывается APScheduler'ом каждый день в 07:30.
    """
    _app = app or current_app._get_current_object()
    with _app.app_context():
        try:
            from app import db, mail
            from app.models.models import Notification, User
            from flask_mail import Message

            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

            # Все непрочитанные уведомления за последние 24 ч
            rows = (
                db.session.query(Notification.user_id, db.func.count(Notification.id))
                .filter(
                    Notification.is_read == False,
                    Notification.email_sent == False,
                    Notification.created_at >= cutoff,
                )
                .group_by(Notification.user_id)
                .all()
            )

            for user_id, count in rows:
                user = User.query.get(user_id)
                if not user or not user.email:
                    continue

                notifications = (
                    Notification.query
                    .filter(
                        Notification.user_id == user_id,
                        Notification.is_read == False,
                        Notification.email_sent == False,
                        Notification.created_at >= cutoff,
                    )
                    .order_by(Notification.created_at.desc())
                    .all()
                )

                # Build HTML email
                items_html = ''.join([
                    f'<tr><td style="padding:8px 12px;border-bottom:1px solid #f1f5f9;">'
                    f'<strong>{n.title}</strong><br>'
                    f'<span style="color:#64748b;font-size:12px;">{n.message or ""}</span>'
                    f'</td></tr>'
                    for n in notifications
                ])

                html_body = f"""
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;">
  <div style="background:#1e3a5f;padding:20px 24px;">
    <h2 style="color:#fff;margin:0;font-size:18px;">⌂ BauNavigator — Ihr Tagesüberblick</h2>
  </div>
  <div style="padding:20px 24px;">
    <p style="color:#374151;">Guten Morgen, {user.full_name or user.email}!</p>
    <p style="color:#64748b;">Sie haben <strong>{count} neue Benachrichtigung{'en' if count > 1 else ''}</strong>:</p>
    <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      {items_html}
    </table>
    <div style="margin-top:20px;">
      <a href="{_app.config.get('BASE_URL', 'https://baunavigator.de')}/notifications"
         style="background:#1e3a5f;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px;">
        Alle Benachrichtigungen anzeigen →
      </a>
    </div>
  </div>
  <div style="padding:12px 24px;background:#f8fafc;font-size:11px;color:#94a3b8;">
    BauNavigator — Ihr KI-Assistent für den Hausbau in Hessen
  </div>
</div>
"""
                try:
                    msg = Message(
                        subject=f'BauNavigator: {count} neue Benachrichtigung{"en" if count > 1 else ""}',
                        recipients=[user.email],
                        html=html_body,
                    )
                    mail.send(msg)
                    # MarkEmailSent
                    for n in notifications:
                        n.email_sent = True
                    db.session.commit()
                    logger.info(f'Digest sent to {user.email} ({count} notifications)')
                except Exception as mail_err:
                    logger.error(f'Digest mail error for {user.email}: {mail_err}')

        except Exception as exc:
            logger.error(f'send_daily_digest error: {exc}')


# ── Иконки типов уведомлений ───────────────────────────────────────────────

NOTIFICATION_ICONS = {
    'stage_change':     '🏗',
    'law_update':       '⚖️',
    'finance_alert':    '💰',
    'document_missing': '📄',
    'camera_report':    '📷',
    'deadline':         '⏰',
    'system':           'ℹ️',
}
