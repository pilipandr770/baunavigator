"""
Camera Service — BauNavigator
==============================
Поддерживает два типа камер:
  1. RTSP / IP-камера (ONVIF) — берём кадр через ffmpeg subprocess
  2. Telegram Bot — прораб отправляет фото в бот → анализ

Claude Vision API анализирует каждый кадр:
  - Прогресс этапа (%)
  - Список выполненных работ
  - Замеченные проблемы/отклонения
  - Рекомендации
"""
from __future__ import annotations

import base64
import json
import logging
import os
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Папка для хранения снимков (внутри static/)
SNAPSHOTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'static', 'snapshots'
)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


# ── Claude Vision prompt ──────────────────────────────────────────────────────

_VISION_SYSTEM = """Du bist ein erfahrener Bauleiter-KI bei BauNavigator.
Du analysierst Fotos von einer Baustelle in Hessen, Deutschland.

Antworte NUR mit JSON (keine Erklärungen außerhalb):
{
  "detected_stage": "walls_ceilings",
  "progress_pct": 65,
  "works_detected": ["Außenwände Erdgeschoss fertig", "Deckenschalung läuft"],
  "issues": ["Bewehrung auf Boden ohne Abstandhalter", "Feuchtigkeitsschäden an Schalung"],
  "recommendations": ["Bewehrung sofort auf Abstandhalter stellen", "Schalung trocknen lassen"],
  "summary_de": "Mauerwerk EG ca. 65% fertig. Rohdecke in Vorbereitung. Achtung: Bewehrungsproblem."
}

Gültige detected_stage-Werte: earthworks, foundation, walls_ceilings, roof,
windows_doors_raw, electrical, plumbing, flooring, tiling, plastering,
built_in_furniture, lighting, doors_stairs, facade_insulation, garage, garden,
driveway, fencing, heating, solar_pv, ventilation, final_acceptance

progress_pct: Schätzung wie weit der erkannte Bauabschnitt abgeschlossen ist (0-100).
issues: Konkrete Probleme oder Sicherheitsrisiken die du siehst. Leere Liste wenn keine.
"""


def analyze_frame_with_ai(
    image_bytes: bytes,
    project_title: str = '',
    current_stage: str = '',
) -> dict:
    """
    Отправляет кадр в Claude Vision и возвращает структурированный анализ.
    Возвращает dict с ключами: detected_stage, progress_pct, works_detected,
                                issues, recommendations, summary_de
    """
    from flask import current_app
    api_key = current_app.config.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return {'error': 'ANTHROPIC_API_KEY not set', 'summary_de': 'Kein API-Key konfiguriert'}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        img_b64 = base64.standard_b64encode(image_bytes).decode('utf-8')
        user_text = (
            f'Baustellenfoto für Projekt: "{project_title}".\n'
            f'Aktuell geplanter Bauabschnitt laut System: {current_stage}.\n'
            'Bitte analysiere das Foto und gib mir das JSON-Ergebnis.'
        )

        response = client.messages.create(
            model='claude-opus-4-5',
            max_tokens=1024,
            system=_VISION_SYSTEM,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': 'image/jpeg',
                            'data': img_b64,
                        },
                    },
                    {'type': 'text', 'text': user_text},
                ],
            }],
        )

        raw = response.content[0].text.strip()
        # Extract JSON
        start = raw.find('{')
        end   = raw.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {'summary_de': raw, 'progress_pct': None, 'issues': []}

    except json.JSONDecodeError as e:
        logger.error(f'Vision JSON parse error: {e}')
        return {'summary_de': 'JSON-Fehler bei AI-Analyse', 'issues': []}
    except Exception as e:
        logger.error(f'Vision API error: {e}')
        return {'error': str(e), 'summary_de': 'AI-Analyse fehlgeschlagen', 'issues': []}


# ── RTSP frame capture ────────────────────────────────────────────────────────

def grab_rtsp_frame(rtsp_url: str, timeout: int = 30) -> Optional[bytes]:
    """
    Захватывает один кадр из RTSP-потока через ffmpeg.
    Требует ffmpeg в PATH (в Docker-образе установлен через apt).
    Возвращает bytes (JPEG) или None при ошибке.
    """
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        tmp_path = f.name

    try:
        cmd = [
            'ffmpeg',
            '-loglevel', 'error',
            '-rtsp_transport', 'tcp',
            '-i', rtsp_url,
            '-vframes', '1',
            '-vf', 'scale=1280:-1',  # ограничиваем ширину до 1280px
            '-q:v', '3',             # качество JPEG (1=лучшее, 31=худшее)
            '-y', tmp_path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if result.returncode != 0:
            logger.warning(f'ffmpeg error for {rtsp_url}: {result.stderr.decode()[:200]}')
            return None
        with open(tmp_path, 'rb') as fh:
            return fh.read()
    except subprocess.TimeoutExpired:
        logger.warning(f'ffmpeg timeout for {rtsp_url}')
        return None
    except FileNotFoundError:
        logger.error('ffmpeg not found in PATH — cannot capture RTSP frames')
        return None
    except Exception as e:
        logger.error(f'grab_rtsp_frame error: {e}')
        return None
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def save_snapshot_image(image_bytes: bytes, snapshot_id: str) -> str:
    """Сохраняет JPEG на диск, возвращает relative URL для шаблона."""
    filename = f'{snapshot_id}.jpg'
    path = os.path.join(SNAPSHOTS_DIR, filename)
    with open(path, 'wb') as f:
        f.write(image_bytes)
    return f'snapshots/{filename}'


# ── Process one RTSP camera ───────────────────────────────────────────────────

def process_camera_snapshot(camera, project) -> Optional[object]:
    """
    Делает снимок с камеры, анализирует, сохраняет CameraSnapshot.
    Возвращает сохранённый объект или None.
    """
    from app import db
    from app.models.models import CameraSnapshot
    from app.models.enums import StageKey
    from app.services.notification_service import notify

    logger.info(f'Processing RTSP camera "{camera.name}" for project "{project.title}"')

    image_bytes = grab_rtsp_frame(camera.rtsp_url)
    if not image_bytes:
        logger.warning(f'No frame from camera {camera.id}')
        return None

    current_stage_val = project.current_stage.value if project.current_stage else ''
    analysis = analyze_frame_with_ai(image_bytes, project.title, current_stage_val)

    snap = CameraSnapshot(
        camera_id=camera.id,
        project_id=project.id,
        source_type='rtsp',
        stage_key=_safe_stage_key(analysis.get('detected_stage')),
        ai_summary=analysis.get('summary_de', ''),
        ai_progress_pct=analysis.get('progress_pct'),
        ai_issues='\n'.join(analysis.get('issues', [])),
        ai_raw_json=json.dumps(analysis, ensure_ascii=False),
    )
    # Save image
    snap.image_path = save_snapshot_image(image_bytes, snap.id)

    db.session.add(snap)
    camera.last_snapshot_at = datetime.now(timezone.utc)
    db.session.commit()

    # Notify if issues detected
    issues = analysis.get('issues', [])
    if issues:
        notify(
            user_id=project.user_id,
            type_='camera_report',
            title=f'📷 Kamera {camera.name}: {len(issues)} Problem(e) erkannt',
            message=issues[0][:120] if issues else '',
            link=f'/project/{project.id}/cameras',
            project_id=project.id,
        )

    logger.info(f'Snapshot saved for camera {camera.id}, progress={snap.ai_progress_pct}%')
    return snap


def _safe_stage_key(val: Optional[str]):
    from app.models.enums import StageKey
    if not val:
        return None
    try:
        return StageKey(val)
    except ValueError:
        return None


# ── Scheduled job: check all RTSP cameras ────────────────────────────────────

def check_all_rtsp_cameras(app=None):
    """
    Проверяет все активные RTSP-камеры, у которых пришло время снимка.
    Вызывается APScheduler каждый час.
    """
    from flask import current_app
    _app = app or current_app._get_current_object()
    with _app.app_context():
        try:
            from app.models.models import CameraFeed, Project
            from app.models.enums import CameraFeedType

            now = datetime.now(timezone.utc)
            cameras = CameraFeed.query.filter_by(
                is_active=True, feed_type=CameraFeedType.RTSP
            ).all()

            for cam in cameras:
                # Check interval
                if cam.last_snapshot_at:
                    next_check = cam.last_snapshot_at + timedelta(
                        minutes=cam.check_interval_minutes or 60
                    )
                    if now < next_check:
                        continue
                project = Project.query.get(cam.project_id)
                if not project:
                    continue
                try:
                    process_camera_snapshot(cam, project)
                except Exception as e:
                    logger.error(f'Camera {cam.id} snapshot error: {e}')

        except Exception as exc:
            logger.error(f'check_all_rtsp_cameras error: {exc}')


# ── Telegram photo processing ─────────────────────────────────────────────────

def process_telegram_photo(
    camera,
    project,
    image_bytes: bytes,
    telegram_file_id: str = '',
) -> Optional[object]:
    """
    Обрабатывает фото, полученное через Telegram-бот.
    Используется в telegram_bot route.
    """
    from app import db
    from app.models.models import CameraSnapshot
    from app.services.notification_service import notify

    current_stage_val = project.current_stage.value if project.current_stage else ''
    analysis = analyze_frame_with_ai(image_bytes, project.title, current_stage_val)

    snap = CameraSnapshot(
        camera_id=camera.id,
        project_id=project.id,
        source_type='telegram',
        telegram_file_id=telegram_file_id,
        stage_key=_safe_stage_key(analysis.get('detected_stage')),
        ai_summary=analysis.get('summary_de', ''),
        ai_progress_pct=analysis.get('progress_pct'),
        ai_issues='\n'.join(analysis.get('issues', [])),
        ai_raw_json=json.dumps(analysis, ensure_ascii=False),
    )
    snap.image_path = save_snapshot_image(image_bytes, snap.id)

    db.session.add(snap)
    camera.last_snapshot_at = datetime.now(timezone.utc)
    db.session.commit()

    # Send notification to project owner
    notify(
        user_id=project.user_id,
        type_='camera_report',
        title=f'📷 Neues Baufoto: {camera.name}',
        message=analysis.get('summary_de', '')[:120],
        link=f'/project/{project.id}/cameras',
        project_id=project.id,
    )

    return snap, analysis


# ── Telegram: download file ───────────────────────────────────────────────────

def download_telegram_file(file_id: str, bot_token: str) -> Optional[bytes]:
    """Загружает файл с Telegram серверов по file_id."""
    try:
        # Step 1: get file path
        api_url = f'https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}'
        with urllib.request.urlopen(api_url, timeout=15) as resp:
            data = json.loads(resp.read())
        if not data.get('ok'):
            return None
        file_path = data['result']['file_path']

        # Step 2: download
        dl_url = f'https://api.telegram.org/file/bot{bot_token}/{file_path}'
        with urllib.request.urlopen(dl_url, timeout=30) as resp:
            return resp.read()
    except Exception as e:
        logger.error(f'Telegram file download error: {e}')
        return None


def send_telegram_message(chat_id: str, text: str, bot_token: str) -> bool:
    """Отправляет текстовое сообщение в Telegram."""
    try:
        import urllib.parse
        params = urllib.parse.urlencode({'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'})
        url = f'https://api.telegram.org/bot{bot_token}/sendMessage?{params}'
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read()).get('ok', False)
    except Exception as e:
        logger.error(f'Telegram send error: {e}')
        return False
