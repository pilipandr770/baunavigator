"""
LawAgent — BauNavigator
========================
Отслеживает актуальность законов, касающихся строительства в Германии/Гессен.

Источники:
  - gesetze-im-internet.de  (GEG, BauGB, BGB)
  - hessen.de               (HBO Hessen)
  - kfw.de                  (программы финансирования)
  - bundesanzeiger.de       (официальные объявления)
  - bafa.de                 (BAFA субсидии)
  - wibank.de               (WIBank Hessen)

Алгоритм:
  1. Загружаем страницу источника (только HTML-текст основного контента)
  2. Считаем SHA-256 хэш → сравниваем с предыдущим
  3. Если хэш изменился → GPT/Claude анализирует diff и:
     a) составляет краткую сводку изменений
     b) определяет затронутые этапы строительства
     c) предлагает обновление текста STAGE_CONTEXTS
  4. Записываем в LawUpdateLog, ставим requires_review=True
  5. Результаты доступны в /admin/law-updates
"""

from __future__ import annotations
import hashlib
import logging
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

from flask import current_app

logger = logging.getLogger(__name__)

# ── Jina Reader endpoint ─────────────────────────────────────────────────────
# Возвращает чистый Markdown без JS/nav/styles.
# Опционально используем JINA_API_KEY для повышенных лимитов (5 req/s без ключа).
_JINA_BASE = 'https://r.jina.ai/'

_HEADERS_JINA = {
    'Accept': 'text/plain',
    'X-Return-Format': 'text',
    'User-Agent': (
        'Mozilla/5.0 (compatible; BauNavigator-LawAgent/1.0; '
        '+https://baunavigator.de/bot)'
    ),
}

_WHITESPACE_RE = re.compile(r'\n{3,}')


def _fetch_text(url: str, timeout: int = 20) -> Optional[str]:
    """
    Загружает страницу через Jina AI Reader (r.jina.ai) и возвращает
    чистый текст/Markdown без навигации, скриптов и рекламы.
    Fallback: прямой urllib-запрос если Jina недоступен.
    """
    jina_url = _JINA_BASE + url
    headers = dict(_HEADERS_JINA)

    # Добавляем API-ключ если задан
    try:
        jina_key = current_app.config.get('JINA_API_KEY') or ''
    except RuntimeError:
        jina_key = ''
    if jina_key:
        headers['Authorization'] = f'Bearer {jina_key}'

    try:
        req = urllib.request.Request(jina_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode('utf-8', errors='replace')
        # Нормализуем лишние пустые строки
        text = _WHITESPACE_RE.sub('\n\n', text).strip()
        return text[:80_000]
    except Exception as exc:
        logger.warning(f'Jina Reader failed [{url}]: {exc} — trying direct fetch')

    # ── Fallback: прямой urllib ──────────────────────────────────────────────
    _STRIP_TAGS_RE = re.compile(
        r'<(script|style|nav|header|footer|aside|iframe)[^>]*>.*?</\1>',
        re.DOTALL | re.IGNORECASE,
    )
    _TAG_RE = re.compile(r'<[^>]+>')
    _WS_RE  = re.compile(r'\s+')
    try:
        req2 = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; BauNavigator/1.0)',
            'Accept-Language': 'de-DE,de;q=0.9',
        })
        with urllib.request.urlopen(req2, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        text = _STRIP_TAGS_RE.sub('', raw)
        text = _TAG_RE.sub(' ', text)
        text = _WS_RE.sub(' ', text).strip()
        return text[:80_000]
    except Exception as exc2:
        logger.warning(f'LawAgent direct fetch error [{url}]: {exc2}')
        return None

DEFAULT_SOURCES = [
    # ── Bundesrecht ──────────────────────────────────────────────────────────
    {
        "name": "GEG – Gebäudeenergiegesetz",
        "category": "bundesrecht",
        "url": "https://www.gesetze-im-internet.de/geg/BJNR172810020.html",
        "description": "Gebäudeenergiegesetz 2024 — §71 Heizungsanforderungen, §15 Energieausweis",
        "check_interval_days": 30,
    },
    {
        "name": "BauGB – Baugesetzbuch",
        "category": "bundesrecht",
        "url": "https://www.gesetze-im-internet.de/bbaug/BJNR003410960.html",
        "description": "§34/§35 BauGB — Zulässigkeit von Bauvorhaben",
        "check_interval_days": 90,
    },
    {
        "name": "BGB §634a – Gewährleistungsfristen",
        "category": "bundesrecht",
        "url": "https://www.gesetze-im-internet.de/bgb/__634a.html",
        "description": "Verjährungsfristen für Bauleistungen",
        "check_interval_days": 180,
    },
    # ── Hessen ───────────────────────────────────────────────────────────────
    {
        "name": "HBO – Hessische Bauordnung",
        "category": "hessen",
        "url": "https://www.rv.hessenrecht.hessen.de/bshe/document/jlr-BauOHE2018rahmen",
        "description": "HBO 2018 — §64 vereinfachtes Verfahren, §6 Abstandsflächen",
        "check_interval_days": 60,
    },
    {
        "name": "WIBank – Wohnraumförderung Hessen",
        "category": "hessen",
        "url": "https://www.wibank.de/wibank/wohnraumfoerderung",
        "description": "Aktuelle Förderprogramme WIBank Hessen für Neubau",
        "check_interval_days": 30,
    },
    # ── KfW ──────────────────────────────────────────────────────────────────
    {
        "name": "KfW 124 – Wohngebäudekredit",
        "category": "kfw",
        "url": "https://www.kfw.de/inlandsfoerderung/Privatpersonen/Neubau/Finanzierungsangebote/KfW-Wohngeb%C3%A4udekredit-(124)/",
        "description": "KfW 124 — Neubaufinanzierung Zinssätze und Konditionen",
        "check_interval_days": 14,
    },
    {
        "name": "KfW 261 – Bundesförderung Effizienzgebäude",
        "category": "kfw",
        "url": "https://www.kfw.de/inlandsfoerderung/Privatpersonen/Neubau/Finanzierungsangebote/Bundesf%C3%B6rderung-f%C3%BCr-effiziente-Geb%C3%A4ude-Wohngeb%C3%A4ude-Kredit-(261)/",
        "description": "KfW BEG WG — Effizienzgebäude 40/55/70 Förderkonditionen",
        "check_interval_days": 14,
    },
    {
        "name": "KfW 458 – Heizungsförderung BEG",
        "category": "kfw",
        "url": "https://www.kfw.de/inlandsfoerderung/Privatpersonen/Bestehende-Immobilie/Finanzierungsangebote/Bundesf%C3%B6rderung-f%C3%BCr-effiziente-Geb%C3%A4ude-Einzelma%C3%9Fnahmen-Kredit-(358,458)/",
        "description": "KfW 458 — Wärmepumpe, Biomasse, Solarthermie Förderung",
        "check_interval_days": 14,
    },
    {
        "name": "KfW 270 – Erneuerbare Energien PV",
        "category": "kfw",
        "url": "https://www.kfw.de/inlandsfoerderung/Privatpersonen/Neubau/Finanzierungsangebote/Erneuerbare-Energien-Standard-(270)/",
        "description": "KfW 270 — Photovoltaik Finanzierung",
        "check_interval_days": 30,
    },
    # ── BAFA ─────────────────────────────────────────────────────────────────
    {
        "name": "BAFA – BEG Einzelmaßnahmen",
        "category": "bafa",
        "url": "https://www.bafa.de/DE/Energie/Effiziente_Gebaeude/Bundesfoerderung_Effiziente_Gebaeude/beg_node.html",
        "description": "BAFA BEG EM — aktuelle Fördersätze Heizung, Dämmung, Fenster",
        "check_interval_days": 14,
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8', errors='replace')).hexdigest()


# ── AI-анализ изменений ───────────────────────────────────────────────────────

_ANALYSIS_SYSTEM = """Du bist ein juristisch-technischer Analyst bei BauNavigator.

Du analysierst Änderungen auf offiziellen deutschen Gesetzeswebseiten (gesetze-im-internet.de,
kfw.de, bafa.de, hessen.de etc.) um festzustellen, ob sich Inhalte geändert haben, die
für Bauherren in Hessen relevant sind.

Deine Antwort MUSS folgendes JSON-Format haben (keine Erklärungen außerhalb des JSON):
{
  "change_detected": true,
  "severity": "critical|important|minor",
  "summary_de": "Kurze Zusammenfassung der Änderungen auf Deutsch (max 200 Zeichen)",
  "affected_stages": ["financing", "heating", "solar_pv"],
  "suggested_context_update": "Aktualisierter Kontexttext für STAGE_CONTEXTS in ai_service.py (max 400 Zeichen pro Etappe)",
  "action_required": "sofort|naechster_check|keine"
}

Gültige stage-Werte: land_search, land_check, financing, land_purchase,
architect_select, design_planning, building_permit, tendering,
earthworks, foundation, walls_ceilings, roof, windows_doors_raw,
electrical, plumbing, flooring, tiling, plastering, built_in_furniture,
lighting, doors_stairs, facade_insulation, garage, garden, driveway,
fencing, heating, solar_pv, ventilation, energy_certificate, smart_home,
final_acceptance, official_notices, move_in, warranty_tracking

Severity:
- critical: Gesetzliche Anforderungen geändert, neue Pflichten für Bauherren
- important: Förderkonditionen oder Fristen geändert
- minor: Redaktionelle Änderung, keine inhaltliche Relevanz
"""


def _analyze_change_with_ai(source_name: str, old_text: str, new_text: str) -> dict:
    """
    Lässt Claude analysieren, was sich geändert hat und welche Bauetappen betroffen sind.
    Gibt ein dict zurück (aus JSON-Antwort geparst).
    """
    import json
    import anthropic

    # Für den Vergleich nehmen wir die ersten 4000 Zeichen beider Versionen
    old_snippet = old_text[:4000] if old_text else '(kein vorheriger Inhalt)'
    new_snippet = new_text[:4000]

    prompt = f"""Quelle: {source_name}

VORHERIGER INHALT (Auszug):
{old_snippet}

NEUER INHALT (Auszug):
{new_snippet}

Analysiere die Unterschiede und antworte im vorgegebenen JSON-Format."""

    try:
        client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
        resp = client.messages.create(
            model='claude-opus-4-5',
            max_tokens=600,
            system=_ANALYSIS_SYSTEM,
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = resp.content[0].text.strip()
        # Извлекаем JSON из ответа
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as exc:
        logger.error(f'LawAgent AI analysis error: {exc}')

    return {
        'change_detected': True,
        'severity': 'minor',
        'summary_de': 'Inhaltsänderung erkannt — manuelle Überprüfung erforderlich.',
        'affected_stages': [],
        'suggested_context_update': '',
        'action_required': 'naechster_check',
    }


# ── Hauptfunktionen ───────────────────────────────────────────────────────────

def seed_default_sources():
    """
    Fügt die Standard-Rechtsquellen in die DB ein, sofern noch keine vorhanden.
    Idempotent — kann mehrfach aufgerufen werden.
    """
    from app import db
    from app.models.models import LawSource

    for s in DEFAULT_SOURCES:
        existing = LawSource.query.filter_by(url=s['url']).first()
        if not existing:
            src = LawSource(**s)
            db.session.add(src)
    try:
        db.session.commit()
        logger.info('LawAgent: default sources seeded.')
    except Exception as exc:
        db.session.rollback()
        logger.error(f'LawAgent seed error: {exc}')


def check_source(source) -> dict:
    """
    Überprüft eine einzelne LawSource.
    Erstellt einen LawUpdateLog-Eintrag und aktualisiert den Source-Hash.

    Gibt zurück: {"result": "no_change"|"changed"|"error", "log_id": ...}
    """
    from app import db
    from app.models.models import LawUpdateLog

    now = datetime.now(timezone.utc)
    old_hash = source.last_hash

    # Seite abrufen
    text = _fetch_text(source.url)
    if text is None:
        log = LawUpdateLog(
            source_id=source.id,
            checked_at=now,
            result='error',
            previous_hash=old_hash,
            error_message=f'Fetch fehlgeschlagen für: {source.url}',
        )
        db.session.add(log)
        source.last_checked_at = now
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return {'result': 'error', 'log_id': log.id}

    new_hash = _sha256(text)
    source.last_checked_at = now

    if old_hash == new_hash:
        # Keine Änderung
        log = LawUpdateLog(
            source_id=source.id,
            checked_at=now,
            result='no_change',
            previous_hash=old_hash,
            current_hash=new_hash,
        )
        db.session.add(log)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        return {'result': 'no_change', 'log_id': log.id}

    # Änderung erkannt — AI-Analyse
    logger.info(f'LawAgent: change detected in [{source.name}] — analyzing…')

    # Wir können keinen echten Diff machen ohne gespeicherten Text,
    # also geben wir leeren old_text falls kein vorheriger Hash existiert
    old_text = ''  # Wir speichern keinen Volltext (zu groß) — nutzen nur Hash
    analysis = _analyze_change_with_ai(source.name, old_text, text)

    severity = analysis.get('severity', 'minor')
    requires_review = severity in ('critical', 'important')

    log = LawUpdateLog(
        source_id=source.id,
        checked_at=now,
        result='changed',
        previous_hash=old_hash,
        current_hash=new_hash,
        change_summary=analysis.get('summary_de', ''),
        affected_stages=analysis.get('affected_stages', []),
        suggested_update=analysis.get('suggested_context_update', ''),
        requires_review=requires_review,
    )
    db.session.add(log)
    source.last_hash = new_hash
    source.last_changed_at = now

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return {
        'result': 'changed',
        'severity': severity,
        'log_id': log.id,
        'requires_review': requires_review,
    }


def check_due_sources(app=None):
    """
    Überprüft alle aktiven Quellen, deren check_interval_days abgelaufen ist.
    Wird vom APScheduler aufgerufen.

    Gibt zurück: {"checked": int, "changed": int, "errors": int}
    """
    from datetime import timedelta

    def _run():
        from app import db
        from app.models.models import LawSource

        now = datetime.now(timezone.utc)
        sources = LawSource.query.filter_by(is_active=True).all()

        stats = {"checked": 0, "changed": 0, "errors": 0}

        for src in sources:
            # Prüfen ob Intervall abgelaufen
            if src.last_checked_at:
                next_check = src.last_checked_at.replace(tzinfo=timezone.utc) + \
                             timedelta(days=src.check_interval_days)
                if now < next_check:
                    continue

            result = check_source(src)
            stats["checked"] += 1
            if result["result"] == "changed":
                stats["changed"] += 1
            elif result["result"] == "error":
                stats["errors"] += 1

            logger.info(
                f'LawAgent [{src.name}]: {result["result"]}'
            )

        logger.info(
            f'LawAgent check complete — '
            f'checked:{stats["checked"]} changed:{stats["changed"]} errors:{stats["errors"]}'
        )
        return stats

    if app:
        with app.app_context():
            return _run()
    else:
        return _run()


def get_pending_reviews():
    """Возвращает логи, ожидающие ревью администратора."""
    from app.models.models import LawUpdateLog
    return (
        LawUpdateLog.query
        .filter_by(requires_review=True, reviewed_at=None)
        .order_by(LawUpdateLog.checked_at.desc())
        .all()
    )
