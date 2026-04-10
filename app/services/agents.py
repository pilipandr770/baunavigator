"""
BauNavigator Multi-Agent System
================================
Три специализированных агента, работающих в пространстве проекта:

  OnboardingAgent  — опрашивает нового пользователя, составляет профиль проекта
                     и определяет с какого этапа начинать
  DocumentAgent    — проверяет наличие обязательных документов по текущему этапу,
                     составляет чеклист недостающих документов
  FinanceAgent     — отслеживает критические дедлайны финансирования (KfW, WIBank)
                     и создаёт предупреждения в Postausgang

Все агенты используют Claude через существующий ask_ai() из ai_service.py.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from flask import current_app

from app.models.enums import (
    StageKey, StageStatus, ActionType, ActionMode,
    STAGE_LABELS, STAGE_PHASES, STAGE_REQUIRED_DOCS,
)


# ─── Вспомогательные ─────────────────────────────────────────────────────────

def _claude(system: str, messages: list, max_tokens: int = 1500) -> str:
    """Вызов Claude с произвольным system prompt и историей messages."""
    import anthropic
    client = anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])
    resp = client.messages.create(
        model='claude-opus-4-5',
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return resp.content[0].text.strip()


# ═══════════════════════════════════════════════════════════════════════════════
# ONBOARDING AGENT
# ═══════════════════════════════════════════════════════════════════════════════

_ONBOARDING_SYSTEM = """Du bist der BauNavigator Onboarding-Assistent.

DEINE AUFGABE:
Du führst ein strukturiertes Interview mit einem neuen Nutzer, um:
1. Den Projekttyp zu bestimmen (Neubau EFH/MFH, Umbau, Anbau, Kauf)
2. Den aktuellen Stand zu ermitteln (was ist bereits vorhanden?)
3. Vorhandene Dokumente aufzulisten
4. Den Einstiegspunkt in den 35-Stufen-Prozess zu bestimmen

INTERVIEW-ABLAUF (max. 6-8 Fragen, eine nach der anderen):
1. Projekttyp: "Was planen Sie — Neubau, Umbau, Anbau oder Kauf?"
2. Grundstück: "Haben Sie bereits ein Grundstück? (ja, suche noch, nein)"
3. Falls Grundstück vorhanden: "Liegt eine Baugenehmigung vor?"
4. Falls Genehmigung vorhanden: "In welchem Baustadium befinden Sie sich?"
5. Dokumente: "Welche Unterlagen haben Sie bereits? (z.B. Kaufvertrag, Baupläne, KfW-Antrag...)"
6. PLZ: "In welcher Postleitzahl befindet sich das Grundstück / Vorhaben?"
7. Budget: "Was ist Ihr ungefähres Gesamtbudget?"

WICHTIGE REGELN:
- Stelle immer NUR EINE Frage pro Nachricht
- Sei freundlich und ermutigend
- Halte Antworten kurz (2-3 Sätze + Frage)
- Antworte auf Russisch wenn der Nutzer Russisch schreibt
- Wenn du genug Information hast (nach mind. 4 Antworten), schließe mit einem
  JSON-Profil in folgendem Format ab — eingebettet zwischen den Tags <PROFILE> und </PROFILE>:

<PROFILE>
{
  "title_suggestion": "Neubau EFH Frankfurt",
  "project_type": "neubau_efh",
  "current_stage": "architect_select",
  "completed_stages": ["land_search", "land_check", "financing", "land_purchase"],
  "address_plz": "60311",
  "address_city": "Frankfurt am Main",
  "budget_total": 500000,
  "wohnflaeche_m2": 150,
  "grundstueck_m2": 600,
  "documents_present": ["Grundstückskaufvertrag", "Bodengutachten"],
  "summary": "Sie haben ein Grundstück in Frankfurt (60311), Budget 500.000 €. Die Finanzierung steht. Als nächsten Schritt suchen Sie einen Architekten.",
  "finance_warnings": []
}
</PROFILE>

MAPPING project_type-Werte: neubau_efh, neubau_mfh, umbau, anbau, kauf
MAPPING current_stage-Werte: land_search, land_check, financing, land_purchase,
  architect_select, design_planning, building_permit, tendering,
  earthworks, foundation, walls_ceilings, roof, windows_doors_raw,
  electrical, plumbing, flooring, tiling, plastering, built_in_furniture,
  lighting, doors_stairs, facade_insulation, garage, garden, driveway,
  fencing, heating, solar_pv, ventilation, energy_certificate, smart_home,
  final_acceptance, official_notices, move_in, warranty_tracking

finance_warnings: Array mit kritischen Warnungen, z.B.:
  ["KfW-Antrag muss VOR Baubeginn gestellt werden — haben Sie das getan?"]

ABSCHLUSS-NACHRICHT nach dem JSON:
Nach dem <PROFILE>...</PROFILE>-Tag schreibe einen kurzen freundlichen Abschluss,
der die nächsten Schritte zusammenfasst. Kein JSON mehr danach.
"""


def onboarding_chat(messages: list, user_lang: str = 'de') -> dict:
    """
    Verarbeitet einen Onboarding-Schritt.

    messages: Liste von {"role": "user"|"assistant", "content": "..."}
    Gibt zurück: {"reply": str, "profile": dict|None, "done": bool}
    """
    try:
        reply = _claude(_ONBOARDING_SYSTEM, messages, max_tokens=800)
    except Exception as e:
        current_app.logger.error(f'OnboardingAgent error: {e}')
        return {
            'reply': 'Entschuldigung, kurzer technischer Fehler. Bitte versuchen Sie es nochmal.',
            'profile': None,
            'done': False,
        }

    # Извлекаем JSON профиль, если он присутствует
    profile = None
    done = False
    match = re.search(r'<PROFILE>\s*(.*?)\s*</PROFILE>', reply, re.DOTALL)
    if match:
        try:
            profile = json.loads(match.group(1))
            done = True
            # Убираем тег из ответа для отображения
            reply = re.sub(r'<PROFILE>.*?</PROFILE>', '', reply, flags=re.DOTALL).strip()
        except json.JSONDecodeError:
            pass

    return {'reply': reply, 'profile': profile, 'done': done}


# ═══════════════════════════════════════════════════════════════════════════════
# DOCUMENT AGENT
# ═══════════════════════════════════════════════════════════════════════════════

def check_documents(project) -> dict:
    """
    Проверяет наличие документов для текущего этапа проекта.

    Возвращает:
    {
      "stage_key": str,
      "stage_label": str,
      "required": [{"name", "desc", "critical", "uploaded": bool}],
      "missing_critical": int,
      "missing_total": int,
      "percent_complete": int,
    }
    """
    from app.models.models import Document

    stage_key = project.current_stage
    required_list = STAGE_REQUIRED_DOCS.get(stage_key, [])
    if not required_list:
        return {
            'stage_key': stage_key.value,
            'stage_label': STAGE_LABELS.get(stage_key, stage_key.value),
            'required': [],
            'missing_critical': 0,
            'missing_total': 0,
            'percent_complete': 100,
        }

    # Получаем список загруженных документов
    uploaded_names = set()
    try:
        docs = Document.query.filter_by(project_id=project.id).all()
        for doc in docs:
            uploaded_names.add(doc.filename.lower())
            if doc.notes:
                uploaded_names.add(doc.notes.lower())
    except Exception:
        pass

    result_list = []
    missing_critical = 0
    missing_total = 0

    for req in required_list:
        # Простая эвристика: считаем документ загруженным если имя
        # частично совпадает с любым из загруженных файлов
        name_lower = req['name'].lower()
        keywords = [w for w in name_lower.replace('/', ' ').split() if len(w) > 4]
        uploaded = any(
            any(kw in uname for kw in keywords)
            for uname in uploaded_names
        )
        entry = {**req, 'uploaded': uploaded}
        result_list.append(entry)
        if not uploaded:
            missing_total += 1
            if req['critical']:
                missing_critical += 1

    total = len(required_list)
    uploaded_count = total - missing_total
    percent = int(uploaded_count / total * 100) if total else 100

    return {
        'stage_key': stage_key.value,
        'stage_label': STAGE_LABELS.get(stage_key, stage_key.value),
        'required': result_list,
        'missing_critical': missing_critical,
        'missing_total': missing_total,
        'percent_complete': percent,
    }


def check_documents_for_stage(project, stage_key: StageKey) -> dict:
    """Проверяет документы для указанного этапа (не только текущего)."""
    from app.models.models import Document

    required_list = STAGE_REQUIRED_DOCS.get(stage_key, [])
    if not required_list:
        return {
            'stage_key': stage_key.value,
            'stage_label': STAGE_LABELS.get(stage_key, stage_key.value),
            'required': [],
            'missing_critical': 0,
            'missing_total': 0,
            'percent_complete': 100,
        }

    uploaded_names = set()
    try:
        docs = Document.query.filter_by(project_id=project.id).all()
        for doc in docs:
            uploaded_names.add(doc.filename.lower())
            if doc.notes:
                uploaded_names.add(doc.notes.lower())
    except Exception:
        pass

    result_list = []
    missing_critical = 0
    missing_total = 0

    for req in required_list:
        name_lower = req['name'].lower()
        keywords = [w for w in name_lower.replace('/', ' ').split() if len(w) > 4]
        uploaded = any(
            any(kw in uname for kw in keywords)
            for uname in uploaded_names
        )
        entry = {**req, 'uploaded': uploaded}
        result_list.append(entry)
        if not uploaded:
            missing_total += 1
            if req['critical']:
                missing_critical += 1

    total = len(required_list)
    uploaded_count = total - missing_total
    percent = int(uploaded_count / total * 100) if total else 100

    return {
        'stage_key': stage_key.value,
        'stage_label': STAGE_LABELS.get(stage_key, stage_key.value),
        'required': result_list,
        'missing_critical': missing_critical,
        'missing_total': missing_total,
        'percent_complete': percent,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# FINANCE AGENT
# ═══════════════════════════════════════════════════════════════════════════════

# Критические финансовые дедлайны — KEY_STAGE: (описание, дней_предупреждения)
_FINANCE_DEADLINES = {
    StageKey.FINANCING: {
        'warning': 'KfW-Antrag (Programme 124/261/300) MUSS vor Baubeginn gestellt werden! '
                   'Nach Baustart ist keine Förderung mehr möglich.',
        'trigger_stage': StageKey.EARTHWORKS,
        'days_before': 60,
    },
    StageKey.BUILDING_PERMIT: {
        'warning': 'WIBank Hessen (Wohnraumförderung) — Antrag muss vor Baubeginn eingereicht werden.',
        'trigger_stage': StageKey.EARTHWORKS,
        'days_before': 30,
    },
    StageKey.HEATING: {
        'warning': 'BEG/BAFA-Förderantrag für Wärmepumpe/Heizung muss VOR dem Einbau gestellt werden.',
        'trigger_stage': StageKey.HEATING,
        'days_before': 14,
    },
    StageKey.SOLAR_PV: {
        'warning': 'KfW-270 Antrag für PV-Anlage muss VOR der Beauftragung des Installateurs gestellt werden.',
        'trigger_stage': StageKey.SOLAR_PV,
        'days_before': 7,
    },
}


def check_finance_alerts(project) -> list:
    """
    Проверяет критические дедлайны финансирования для проекта.

    Возвращает список dict: {level, message, action}
      level: 'critical' | 'warning' | 'info'
    """
    alerts = []

    # Определяем, на каких этапах уже находится проект
    current = project.current_stage
    stage_order = []
    for phase_data in STAGE_PHASES.values():
        stage_order.extend(phase_data['stages'])

    current_idx = stage_order.index(current) if current in stage_order else 0

    # Проверяем каждый дедлайн
    for deadline_stage, info in _FINANCE_DEADLINES.items():
        trigger_stage = info['trigger_stage']
        trigger_idx = stage_order.index(trigger_stage) if trigger_stage in stage_order else 99

        # Если мы УЖЕ на триггерном этапе или дальше
        if current_idx >= trigger_idx:
            dl_idx = stage_order.index(deadline_stage) if deadline_stage in stage_order else 0
            # Если дедлайн-этап уже пройден (done) — ок, предупреждения нет
            try:
                from app.models.models import ProjectStage
                dl_ps = ProjectStage.query.filter_by(
                    project_id=project.id,
                    stage_key=deadline_stage
                ).first()
                if dl_ps and dl_ps.status == StageStatus.DONE:
                    continue
            except Exception:
                pass

            level = 'critical' if current_idx >= trigger_idx else 'warning'
            alerts.append({
                'level': level,
                'message': info['warning'],
                'stage_key': deadline_stage.value,
                'stage_label': STAGE_LABELS.get(deadline_stage, deadline_stage.value),
                'action': f'Zum Etap "{STAGE_LABELS.get(deadline_stage, deadline_stage.value)}" navigieren',
            })

    return alerts


def create_finance_outbox_messages(project, user) -> int:
    """
    Создаёт предупреждения в Postausgang для критических финансовых дедлайнов.
    Возвращает количество созданных сообщений.
    """
    from app import db
    from app.models.models import MessageOutbox
    from app.models.enums import OutboxStatus, RecipientType

    alerts = check_finance_alerts(project)
    count = 0

    for alert in alerts:
        if alert['level'] != 'critical':
            continue

        # Проверяем, не создавали ли уже такое сообщение
        existing = MessageOutbox.query.filter_by(
            project_id=project.id,
            recipient_type=RecipientType.KFW,
            status=OutboxStatus.DRAFT,
        ).filter(
            MessageOutbox.subject.contains(alert['stage_label'])
        ).first()
        if existing:
            continue

        msg = MessageOutbox(
            project_id=project.id,
            user_id=user.id,
            recipient_type=RecipientType.KFW,
            subject=f'⚠️ Finanzierungs-Deadline: {alert["stage_label"]}',
            body=f"""WICHTIG: {alert["message"]}

Projekt: {project.title}
Aktueller Schritt: {STAGE_LABELS.get(project.current_stage, '')}

Bitte nehmen Sie sofort Maßnahmen, um Förderungen nicht zu verlieren.

Nächste Schritte:
1. Öffnen Sie in BauNavigator den Abschnitt "{alert["stage_label"]}"
2. Bereiten Sie den Antrag vor
3. Stellen Sie den Antrag BEVOR Sie mit dem nächsten Baustadium beginnen

Diese Erinnerung wurde automatisch vom BauNavigator Finance-Agenten erstellt.
""",
            status=OutboxStatus.AWAITING_APPROVAL,
        )
        db.session.add(msg)
        count += 1

    if count:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    return count


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE SEQUENCE BUILDER — используется при создании проекта из профиля
# ═══════════════════════════════════════════════════════════════════════════════

def build_stage_sequence(profile: dict) -> dict:
    """
    Принимает профиль от OnboardingAgent и возвращает:
    {
      "current_stage": StageKey,
      "completed_stages": [StageKey],
      "project_type": ProjectType,
    }
    """
    from app.models.enums import ProjectType

    current_str = profile.get('current_stage', 'land_search')
    completed_strs = profile.get('completed_stages', [])

    try:
        current_stage = StageKey(current_str)
    except ValueError:
        current_stage = StageKey.LAND_SEARCH

    completed = []
    for s in completed_strs:
        try:
            completed.append(StageKey(s))
        except ValueError:
            pass

    pt_str = profile.get('project_type', 'neubau_efh')
    try:
        project_type = ProjectType(pt_str)
    except ValueError:
        project_type = ProjectType.NEUBAU_EFH

    return {
        'current_stage': current_stage,
        'completed_stages': completed,
        'project_type': project_type,
    }
