"""
Telegram Bot Webhook — BauNavigator
=====================================
Обрабатывает входящие обновления от Telegram-бота.

Команды:
  /start <project_id>  — привязать чат к камере проекта
  /status              — получить статус текущего проекта
  /help                — список команд

При получении фото:
  → Скачивается, анализируется Claude Vision, результат отправляется обратно.

Настройка:
  1. Создай бота через @BotFather → получи TELEGRAM_BOT_TOKEN
  2. Задай webhook:
     curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
          -d url=https://baunavigator.de/telegram/webhook
  3. Добавь TELEGRAM_BOT_TOKEN в .env
"""
import logging

from flask import Blueprint, request, jsonify, current_app

from app import db, csrf
from app.models.models import CameraFeed, Project
from app.models.enums import CameraFeedType

logger = logging.getLogger(__name__)

telegram_bp = Blueprint('telegram', __name__)


@telegram_bp.route('/webhook', methods=['POST'])
@csrf.exempt
def webhook():
    """Telegram calls this URL with every update (message, photo, etc.)."""
    bot_token = current_app.config.get('TELEGRAM_BOT_TOKEN', '')
    if not bot_token:
        return jsonify({'ok': False}), 200   # always 200 to Telegram

    data = request.get_json(silent=True) or {}
    message = data.get('message') or data.get('channel_post') or {}

    if not message:
        return jsonify({'ok': True}), 200

    chat_id   = str(message.get('chat', {}).get('id', ''))
    text      = message.get('text', '')
    photos    = message.get('photo', [])

    # ── Commands ──────────────────────────────────────────────────────────────
    if text.startswith('/start'):
        _handle_start(chat_id, text, bot_token)

    elif text.startswith('/status'):
        _handle_status(chat_id, bot_token)

    elif text.startswith('/help'):
        _send_help(chat_id, bot_token)

    # ── Photo received ────────────────────────────────────────────────────────
    elif photos:
        _handle_photo(chat_id, photos, message, bot_token)

    return jsonify({'ok': True}), 200


# ── Command handlers ──────────────────────────────────────────────────────────

def _handle_start(chat_id: str, text: str, bot_token: str):
    """
    /start <project_id>
    Links this Telegram chat to a project's first Telegram camera (or creates one).
    """
    from app.services.camera_service import send_telegram_message

    parts = text.strip().split()
    project_id = parts[1] if len(parts) > 1 else None

    if not project_id:
        send_telegram_message(chat_id,
            '👋 Willkommen beim <b>BauNavigator Kamera-Bot</b>!\n\n'
            'Sende <code>/start &lt;Projekt-ID&gt;</code> um diesen Chat mit Ihrem Projekt zu verknüpfen.\n'
            'Die Projekt-ID finden Sie in BauNavigator unter Projekt → Kameras.',
            bot_token)
        return

    project = Project.query.get(project_id)
    if not project:
        send_telegram_message(chat_id, '❌ Projekt nicht gefunden. Bitte ID prüfen.', bot_token)
        return

    # Check if a Telegram camera already exists for this chat
    existing = CameraFeed.query.filter_by(
        project_id=project_id,
        feed_type=CameraFeedType.TELEGRAM,
        telegram_chat_id=chat_id,
    ).first()

    if existing:
        send_telegram_message(chat_id,
            f'✅ Dieser Chat ist bereits mit Projekt <b>{project.title}</b> verknüpft.\n'
            'Senden Sie einfach Fotos, sie werden automatisch analysiert.',
            bot_token)
        return

    # Create new Telegram camera feed
    cam = CameraFeed(
        project_id=project_id,
        name=f'Telegram-Kamera {chat_id[-4:]}',
        feed_type=CameraFeedType.TELEGRAM,
        telegram_chat_id=chat_id,
        is_active=True,
        check_interval_minutes=0,  # on-demand
    )
    db.session.add(cam)
    db.session.commit()

    send_telegram_message(chat_id,
        f'✅ Chat erfolgreich mit Projekt <b>{project.title}</b> verknüpft!\n\n'
        '📷 Senden Sie jetzt Fotos von der Baustelle.\n'
        'Der KI-Assistent analysiert jeden Snapshot automatisch:\n'
        '• Baufortschritt (%)\n'
        '• Erkannte Arbeiten\n'
        '• Probleme & Empfehlungen',
        bot_token)


def _handle_status(chat_id: str, bot_token: str):
    """Returns current project status for the linked camera."""
    from app.services.camera_service import send_telegram_message

    cam = CameraFeed.query.filter_by(
        feed_type=CameraFeedType.TELEGRAM,
        telegram_chat_id=chat_id,
        is_active=True,
    ).first()

    if not cam:
        send_telegram_message(chat_id,
            'Kein verknüpftes Projekt. Sende /start &lt;Projekt-ID&gt;', bot_token)
        return

    project = Project.query.get(cam.project_id)
    if not project:
        send_telegram_message(chat_id, 'Projekt nicht gefunden.', bot_token)
        return

    from app.models.enums import STAGE_LABELS
    stage_label = STAGE_LABELS.get(project.current_stage, str(project.current_stage))

    # Last snapshot info
    last_snap = cam.snapshots.first()
    snap_info = ''
    if last_snap:
        snap_info = (
            f'\n\n📷 Letzter Snapshot: {last_snap.captured_at.strftime("%d.%m.%Y %H:%M")}'
            f'\n📊 Fortschritt: {last_snap.ai_progress_pct or "?"}%'
        )

    send_telegram_message(chat_id,
        f'📋 <b>{project.title}</b>\n'
        f'🏗 Aktueller Abschnitt: {stage_label}\n'
        f'📍 Standort: {project.address_city or "–"}'
        f'{snap_info}',
        bot_token)


def _handle_photo(chat_id: str, photos: list, message: dict, bot_token: str):
    """Downloads the best-quality photo and runs AI analysis."""
    from app.services.camera_service import (
        download_telegram_file, process_telegram_photo, send_telegram_message
    )

    # Find camera linked to this chat
    cam = CameraFeed.query.filter_by(
        feed_type=CameraFeedType.TELEGRAM,
        telegram_chat_id=chat_id,
        is_active=True,
    ).first()

    if not cam:
        send_telegram_message(chat_id,
            'Sende zuerst /start &lt;Projekt-ID&gt; um diesen Chat zu verknüpfen.', bot_token)
        return

    project = Project.query.get(cam.project_id)
    if not project:
        return

    # Pick largest photo (last in array = highest resolution)
    best_photo = max(photos, key=lambda p: p.get('file_size', 0))
    file_id = best_photo['file_id']

    send_telegram_message(chat_id, '⏳ Analysiere Foto, einen Moment…', bot_token)

    image_bytes = download_telegram_file(file_id, bot_token)
    if not image_bytes:
        send_telegram_message(chat_id, '❌ Foto konnte nicht heruntergeladen werden.', bot_token)
        return

    try:
        snap, analysis = process_telegram_photo(cam, project, image_bytes, file_id)
    except Exception as e:
        logger.error(f'process_telegram_photo error: {e}')
        send_telegram_message(chat_id, '❌ Fehler bei der KI-Analyse. Bitte erneut versuchen.', bot_token)
        return

    # Build reply
    progress = analysis.get('progress_pct')
    issues   = analysis.get('issues', [])
    works    = analysis.get('works_detected', [])
    summary  = analysis.get('summary_de', '')

    reply_parts = [f'📊 <b>Baufortschritt:</b> {progress}%' if progress else '']
    if summary:
        reply_parts.append(f'\n📝 {summary}')
    if works:
        reply_parts.append('\n\n✅ <b>Erkannte Arbeiten:</b>\n' + '\n'.join(f'• {w}' for w in works[:4]))
    if issues:
        reply_parts.append('\n\n⚠️ <b>Probleme:</b>\n' + '\n'.join(f'• {i}' for i in issues[:3]))

    recs = analysis.get('recommendations', [])
    if recs:
        reply_parts.append('\n\n💡 <b>Empfehlungen:</b>\n' + '\n'.join(f'• {r}' for r in recs[:2]))

    reply_parts.append(
        f'\n\n🔗 <a href="{current_app.config.get("BASE_URL", "https://baunavigator.de")}'
        f'/project/{project.id}/cameras">In BauNavigator anzeigen</a>'
    )

    send_telegram_message(chat_id, ''.join(reply_parts), bot_token)


def _send_help(chat_id: str, bot_token: str):
    from app.services.camera_service import send_telegram_message
    send_telegram_message(chat_id,
        '🤖 <b>BauNavigator Kamera-Bot</b>\n\n'
        '<b>Befehle:</b>\n'
        '/start &lt;Projekt-ID&gt; — Chat mit Projekt verknüpfen\n'
        '/status — Projektstatus anzeigen\n'
        '/help — Diese Hilfe\n\n'
        '<b>Fotos senden:</b>\n'
        'Senden Sie einfach ein Foto von der Baustelle.\n'
        'Der KI-Assistent analysiert automatisch:\n'
        '• Welcher Bauabschnitt zu sehen ist\n'
        '• Wie weit der Fortschritt ist\n'
        '• Ob Probleme erkennbar sind',
        bot_token)
