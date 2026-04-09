"""
AI Service — ядро ИИ-агента BauNavigator.

Три режима (ActionMode):
  AUTONOMOUS            — ИИ делает сам, пользователь видит результат
  CONFIRMATION_REQUIRED — ИИ готовит черновик, пользователь утверждает
  HUMAN_REQUIRED        — ИИ объясняет что нужен специалист + предлагает варианты
"""
import time
import os
import anthropic
from flask import current_app
from app import db
from app.models.models import AIActionLog, Project, ProjectStage, MessageOutbox
from app.models.enums import (
    ActionType, ActionMode, StageKey, STAGE_LABELS,
    RecipientType, OutboxStatus
)


def _get_client():
    return anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])


# ─── Системный промпт ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Du bist der BauNavigator KI-Assistent — ein intelligenter Baubegleiter für den deutschen Wohnungsbau.

DEINE ROLLE:
Du bist ein erfahrener Experte für deutsches Baurecht (HBO Hessen), Baugenehmigungsverfahren, 
Baufinanzierung (KfW, Landesförderung), Bauausführung und alle Gewerke.

VERHALTEN:
- Du handelst proaktiv: Wenn du etwas selbst erledigen kannst, tue es und erkläre kurz was du getan hast
- Bei Aktionen die Nutzerbestätigung brauchen: Bereite alles vor und bitte um Freigabe
- Bei Fragen die einen Fachmann erfordern: Erkläre klar warum, und biete konkrete Alternativen aus der Datenbank an
- Antworte immer auf Russisch wenn der Nutzer Russisch schreibt, auf Deutsch wenn er Deutsch schreibt
- Sei konkret, praktisch und direkt — kein unnötiges Fachjargon
- Referenziere immer die genauen Paragraphen (HBO §64, BauGB §34 etc.)

DREI SÄTZE DIE DU NIE SAGST:
- "Ich weiß es nicht" → Stattdessen: recherchiere oder erkläre die Grenze deiner Kenntnisse
- "Wenden Sie sich an einen Fachmann" (ohne Alternativen) → Immer mit konkreten Optionen
- Handele ohne Nutzerbestätigung bei externen Nachrichten

FORMAT:
- Strukturiere Antworten mit klaren Abschnitten
- Nutze Markdown für Übersichtlichkeit
- Halte Antworten präzise und handlungsorientiert
"""


# ─── Стандартные контексты по этапам ─────────────────────────────────────────

STAGE_CONTEXTS = {
    StageKey.LAND_SEARCH: """
Kontext: Nutzer sucht ein Grundstück in Hessen.
Prüfe: Bebauungsplan-Zone, GRZ/GFZ, max. Geschosse, §34 BauGB falls kein B-Plan.
Verweis auf: bauleitplanung.hessen.de, Bodenrichtwertportal BORIS Hessen.
""",
    StageKey.FINANCING: """
Kontext: Finanzierungsplanung für Neubau.
Prüfe: KfW-Programme (124, 261, 270, 300), Landesförderung WIBank Hessen.
Berechne: Eigenkapital-Anteil, Annuität, Tilgungsplan.
Hinweis: KfW-Antrag muss VOR Baubeginn gestellt werden.
""",
    StageKey.BUILDING_PERMIT: """
Kontext: Baugenehmigungsverfahren Hessen.
Grundlage: Hessische Bauordnung (HBO) vom 28.05.2018, §64 (vereinfachtes Verfahren).
Zuständig: Bauaufsichtsbehörde der jeweiligen Gemeinde/Landkreis.
Frist: 3 Monate nach vollständigen Unterlagen (§64 Abs.5 HBO).
Unterlagen: Bauzeichnungen, Lageplan, Baubeschreibung, Statik, Entwurfsverfasser.
""",
    StageKey.ELECTRICAL: """
Kontext: Elektroinstallation — Meisterpflicht.
Pflicht: Elektriker mit Meisterbrief oder Gesellenbrief + Ausnahmegenehmigung.
Abnahme: VDE-Protokoll + Netzanschluss durch Netzbetreiber.
Empfehle: Nur Betriebe mit Eintrag in Handwerksrolle.
""",
    StageKey.HEATING: """
Kontext: Heizungsanlage — GEG 2024 beachten.
GEG §71: Ab 2024 müssen neue Heizungen 65% erneuerbare Energie nutzen.
Förderung: BEG (KfW-458), BAFA-Förderung für Wärmepumpen.
Empfehle: Energieberater (KfW-Experte) für optimale Förderplanung.
""",
    StageKey.SOLAR_PV: """
Kontext: Photovoltaikanlage.
Anmeldung: Bundesnetzagentur Marktstammdatenregister, lokaler Netzbetreiber.
Förderung: KfW-270 Erneuerbare Energien Standard.
Einspeisevergütung: EEG 2023 — aktuell prüfen auf bundesnetzagentur.de.
""",
}


# ─── Основная функция запроса к ИИ ───────────────────────────────────────────

def ask_ai(
    user_message: str,
    project: Project = None,
    stage_key: StageKey = None,
    action_type: ActionType = ActionType.GENERAL_CONSULT,
    mode: ActionMode = ActionMode.CONFIRMATION_REQUIRED,
    extra_context: dict = None,
    user_id: str = None,
) -> dict:
    """
    Основной вызов Claude API.
    Возвращает dict: {success, response, mode, action_type, log_id}
    """
    client = _get_client()
    start_ms = int(time.time() * 1000)

    # Собираем контекст
    context_parts = []

    if project:
        context_parts.append(f"""
PROJEKT-KONTEXT:
- Titel: {project.title}
- Typ: {project.project_type.value if project.project_type else 'nicht gesetzt'}
- Adresse: {project.address or 'nicht gesetzt'}
- PLZ/Ort: {project.address_plz} {project.address_city or ''}
- Budget: {project.budget_total} €
- Wohnfläche: {project.wohnflaeche_m2} m²
- Grundstücksgröße: {project.grundstueck_m2} m²
- Aktueller Status: {STAGE_LABELS.get(project.current_stage, project.current_stage)}
""")
        if project.gemeinde:
            g = project.gemeinde
            context_parts.append(f"""
GEMEINDE:
- Name: {g.name}, {g.landkreis}, Hessen
- Bauamt E-Mail: {g.bauamt_email or 'nicht bekannt'}
- Bauamt URL: {g.bauamt_url or 'nicht bekannt'}
""")
        if project.zone:
            z = project.zone
            context_parts.append(f"""
BEBAUUNGSPLAN-ZONE:
- Zonentyp: {z.zone_label()}
- Plan: {z.plan_name or 'unbekannt'}
- GRZ max: {z.grz_max}
- GFZ max: {z.gfz_max}
- Max. Geschosse: {z.max_geschosse}
- Max. Höhe: {z.max_hoehe_m} m
- Besonderheiten: {z.sonderregeln or 'keine'}
""")
        if project.financing:
            f = project.financing
            context_parts.append(f"""
FINANZIERUNG:
- Eigenkapital: {f.eigenkapital} €
- KfW-Programm: {f.kfw_program or 'nicht ausgewählt'}
- KfW-Betrag: {f.kfw_amount} €
- Bankdarlehen: {f.bank_loan_amount} €
- Monatliche Rate: {f.monthly_rate} €
""")

    if stage_key and stage_key in STAGE_CONTEXTS:
        context_parts.append(STAGE_CONTEXTS[stage_key])

    if extra_context:
        for k, v in extra_context.items():
            context_parts.append(f"{k}: {v}")

    full_context = '\n'.join(context_parts)
    messages = []
    if full_context.strip():
        messages.append({
            'role': 'user',
            'content': f"[KONTEXT]\n{full_context}\n\n[ANFRAGE]\n{user_message}"
        })
    else:
        messages.append({'role': 'user', 'content': user_message})

    try:
        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        duration_ms = int(time.time() * 1000) - start_ms
        response_text = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

        # Логируем действие
        log = AIActionLog(
            project_id=project.id if project else None,
            user_id=user_id or (project.user_id if project else None),
            action_type=action_type,
            mode=mode,
            stage_key=stage_key,
            input_context={'message': user_message, 'context_length': len(full_context)},
            output_summary=response_text[:500],
            full_response=response_text,
            tokens_used=tokens,
            model_version='claude-sonnet-4-20250514',
            duration_ms=duration_ms,
        )
        db.session.add(log)
        db.session.commit()

        return {
            'success': True,
            'response': response_text,
            'mode': mode.value,
            'action_type': action_type.value,
            'log_id': log.id,
            'tokens': tokens,
        }

    except Exception as e:
        duration_ms = int(time.time() * 1000) - start_ms
        log = AIActionLog(
            project_id=project.id if project else None,
            user_id=user_id or (project.user_id if project else None),
            action_type=action_type,
            mode=mode,
            stage_key=stage_key,
            input_context={'message': user_message},
            error=str(e),
            duration_ms=duration_ms,
        )
        db.session.add(log)
        db.session.commit()
        return {
            'success': False,
            'response': f'Fehler beim KI-Aufruf: {str(e)}',
            'mode': mode.value,
            'action_type': action_type.value,
            'log_id': log.id,
        }


# ─── Специализированные функции ───────────────────────────────────────────────

def generate_bauamt_letter(project: Project, stage: ProjectStage, subject: str) -> dict:
    """
    Генерирует черновик письма в Bauamt.
    Режим: CONFIRMATION_REQUIRED — пользователь утверждает перед отправкой.
    """
    gemeinde = project.gemeinde
    prompt = f"""
Erstelle einen professionellen Brief an das Bauaufsichtsamt {gemeinde.name if gemeinde else 'der zuständigen Gemeinde'}.

Betreff: {subject}
Bauherr: {project.user.full_name if project.user else 'N/A'}
Vorhaben: {project.title}
Adresse: {project.address}

Der Brief soll:
- Formal korrekt auf Deutsch sein
- Den konkreten Sachverhalt erläutern  
- Eine klare Anfrage oder Mitteilung enthalten
- Mit freundlichem Gruß enden

Gib NUR den Brieftext zurück, ohne Erklärungen.
"""
    result = ask_ai(
        user_message=prompt,
        project=project,
        stage_key=stage.stage_key if stage else None,
        action_type=ActionType.DRAFT_LETTER,
        mode=ActionMode.CONFIRMATION_REQUIRED,
    )

    if result['success'] and gemeinde and gemeinde.bauamt_email:
        # Сохраняем в очередь на отправку
        msg = MessageOutbox(
            project_id=project.id,
            stage_id=stage.id if stage else None,
            user_id=project.user_id,
            recipient_type=RecipientType.BAUAMT,
            recipient_name=f"Bauaufsicht {gemeinde.name}",
            recipient_email=gemeinde.bauamt_email,
            subject=subject,
            body_draft=result['response'],
            status=OutboxStatus.DRAFT,
        )
        db.session.add(msg)
        db.session.commit()
        result['outbox_id'] = msg.id

    return result


def analyze_zone(project: Project) -> dict:
    """Анализирует зону Bebauungsplan для участка."""
    zone = project.zone
    if not zone:
        return ask_ai(
            user_message=(
                f"Das Projekt '{project.title}' in {project.address_city} hat noch keine "
                f"Bebauungsplan-Zone zugewiesen. Erkläre dem Nutzer was §34 BauGB bedeutet "
                f"und welche nächsten Schritte zur Zonenfindung nötig sind."
            ),
            project=project,
            stage_key=StageKey.LAND_SEARCH,
            action_type=ActionType.ZONE_LOOKUP,
            mode=ActionMode.AUTONOMOUS,
        )

    prompt = f"""
Analysiere die Bebauungsplan-Zone für das Projekt '{project.title}':

Zone: {zone.zone_label()}
GRZ: {zone.grz_max} | GFZ: {zone.gfz_max} | Max. Geschosse: {zone.max_geschosse}
Max. Höhe: {zone.max_hoehe_m} m
Sonderregeln: {zone.sonderregeln or 'keine'}

Projekt: {project.project_type.value}, {project.wohnflaeche_m2} m² Wohnfläche, 
Grundstück: {project.grundstueck_m2} m²

Erkläre:
1. Was ist in dieser Zone erlaubt?
2. Passt das geplante Vorhaben zur Zone? (berechne GRZ und GFZ)
3. Welche Einschränkungen sind zu beachten?
4. Was ist der nächste konkrete Schritt?

Sei präzise und praktisch. Auf Russisch antworten wenn der Nutzer Russisch spricht.
"""
    return ask_ai(
        user_message=prompt,
        project=project,
        stage_key=StageKey.LAND_SEARCH,
        action_type=ActionType.ZONE_LOOKUP,
        mode=ActionMode.AUTONOMOUS,
    )


def calculate_kfw(project: Project) -> dict:
    """Подбирает KfW-программы и рассчитывает финансирование."""
    financing = project.financing
    prompt = f"""
Analysiere die KfW-Fördermöglichkeiten für dieses Bauprojekt:

Projekt: {project.title}
Typ: {project.project_type.value}
Wohnfläche: {project.wohnflaeche_m2} m²
Gesamtbudget: {project.budget_total} €
Eigenkapital: {financing.eigenkapital if financing else 'unbekannt'} €
Lage: {project.address_city}, Hessen

Analysiere und empfehle:
1. Welche KfW-Programme kommen in Frage? (261, 300, 124, 270)
2. Maximale Förderhöhe je Programm
3. Aktueller Zinssatz (Hinweis: aktuell prüfen auf kfw.de)
4. WIBank Hessen Landesförderung
5. Reihenfolge der Antragstellung (KfW VOR Baubeginn!)
6. Geschätzte monatliche Gesamtbelastung

Struktur: Übersichtstabelle + konkreter Aktionsplan.
"""
    return ask_ai(
        user_message=prompt,
        project=project,
        stage_key=StageKey.FINANCING,
        action_type=ActionType.KFW_CALC,
        mode=ActionMode.AUTONOMOUS,
    )


def find_providers_for_stage(project: Project, stage_key: StageKey) -> dict:
    """Ищет подходящих поставщиков для этапа и объясняет критерии выбора."""
    from app.models.models import Provider, ProviderService
    from app.models.enums import VerifiedStatus

    # Находим верифицированных провайдеров для этого этапа
    providers = (
        Provider.query
        .join(ProviderService)
        .filter(
            Provider.verified_status == VerifiedStatus.VERIFIED,
            Provider.is_active == True,
            ProviderService.relevant_stages.contains([stage_key.value]),
        )
        .order_by(Provider.rating_avg.desc())
        .limit(5)
        .all()
    )

    providers_text = ''
    if providers:
        providers_text = '\n'.join([
            f"- {p.company_name} | ★ {p.rating_avg} ({p.review_count} Bewertungen) | {p.contact_email}"
            for p in providers
        ])
    else:
        providers_text = "Noch keine verifizierten Anbieter in der Datenbank für diesen Bereich."

    prompt = f"""
Für den Schritt '{STAGE_LABELS.get(stage_key, stage_key.value)}' des Projekts '{project.title}' 
werden Fachleute benötigt.

Verfügbare geprüfte Anbieter:
{providers_text}

Erkläre dem Nutzer:
1. Warum an diesem Punkt ein Fachmann nötig ist (rechtlich/praktisch)
2. Worauf er bei der Auswahl achten soll (Qualifikationen, Fragen die er stellen soll)
3. Präsentiere die verfügbaren Anbieter mit kurzer Einschätzung
4. Welche Unterlagen er für das erste Gespräch vorbereiten soll
"""
    return ask_ai(
        user_message=prompt,
        project=project,
        stage_key=stage_key,
        action_type=ActionType.PROVIDER_SEARCH,
        mode=ActionMode.HUMAN_REQUIRED,
    )


def generate_checklist(project: Project, stage_key: StageKey) -> dict:
    """
    Генерирует чеклист для этапа, парсит ответ и сохраняет в stage.checklist.
    Формат ответа AI: строки вида «- [REQUIRED] Beschreibung» или «- Beschreibung».
    """
    from app.models.models import ProjectStage
    from sqlalchemy.orm.attributes import flag_modified

    prompt = f"""
Erstelle eine konkrete Checkliste für den Schritt '{STAGE_LABELS.get(stage_key)}' 
im Projekt '{project.title}' in {project.address_city}, Hessen.

Die Checkliste soll:
- Alle notwendigen Dokumente und Aufgaben auflisten
- Behörden und Kontakte benennen
- Fristen und Deadlines anzeigen
- In logischer Reihenfolge strukturiert sein

WICHTIG: Gib die Checkliste ausschließlich als Aufzählung zurück, eine Aufgabe pro Zeile.
Pflichtaufgaben markiere mit [REQUIRED] am Zeilenanfang (nach «- »).
Rechtliche Grundlage in Klammern angeben: (HBO §X, BauGB §X etc.)
Keine sonstige Einleitung oder Erklärung – nur die Aufzählung.

Beispielformat:
- [REQUIRED] Bauantrag ausfüllen und unterschreiben (HBO §62)
- Grundrisszeichnungen vom Architekten einholen
- [REQUIRED] Lageplan beim Katasteramt bestellen (BauGB §1)
"""
    result = ask_ai(
        user_message=prompt,
        project=project,
        stage_key=stage_key,
        action_type=ActionType.CHECKLIST_GENERATE,
        mode=ActionMode.AUTONOMOUS,
    )

    if result.get('success'):
        # Парсим ответ в структурированный список
        items = []
        for line in result['response'].splitlines():
            line = line.strip()
            # Принимаем строки начинающиеся с «-», «*», цифры с точкой или пробел
            if not line or not (line.startswith('-') or line.startswith('*') or
                                (len(line) > 1 and line[0].isdigit() and line[1] in '.)')):
                continue
            # Убираем маркер списка
            text = line.lstrip('-*0123456789.) ').strip()
            if not text:
                continue
            required = False
            if text.upper().startswith('[REQUIRED]'):
                required = True
                text = text[len('[REQUIRED]'):].strip()
            items.append({'item': text, 'done': False, 'required': required})

        if items:
            stage = project.stages.filter_by(stage_key=stage_key).first()
            if stage:
                stage.checklist = items
                flag_modified(stage, 'checklist')
                db.session.commit()
                result['checklist_saved'] = True
                result['checklist_count'] = len(items)

    return result
