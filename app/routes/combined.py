from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from sqlalchemy import cast, Text
from flask_login import login_required, current_user
from app import db
from app.models.models import (
    Project, ProjectStage, MessageOutbox, Provider,
    Gemeinde, BebauungsplanZone, ProviderService, ProviderReview, Lead
)
from app.models.enums import (
    StageKey, OutboxStatus, VerifiedStatus, STAGE_LABELS,
    ProviderCategory, PROVIDER_CATEGORY_LABELS, ActionMode, ActionType, LeadStatus,
)
from app.services.ai_service import (
    ask_ai, generate_bauamt_letter, analyze_zone,
    calculate_kfw, find_providers_for_stage, generate_checklist
)

# ─── AI Blueprint ──────────────────────────────────────────────────────────────
ai_bp = Blueprint('ai', __name__)


# ─── Landing Sales Chatbot (public, no auth) ───────────────────────────────────

_LANDING_CHAT_SYSTEM = """Du bist „Bau-Max", der KI-Verkaufsassistent von BauNavigator.

DEINE AUFGABE: Du hilfst Besuchern der Landingpage zu verstehen, ob und wie BauNavigator
ihnen beim Hausbau helfen kann. Du qualifizierst Leads, erkennst Bedürfnisse und bringst
sie zur Registrierung.

FÄHIGKEITEN DER PLATTFORM (die du erklären kannst):
- 35 geführte Bauphasen von der Grundstückssuche bis zur Schlüsselübergabe
- KI-Assistent nach Hessischer Bauordnung (HBO) – beantwortet Rechtsfragen, generiert Dokumente
- Interaktive Karte mit 22+ verifizierten Fachleuten (Architekten, Statiker, Notare, Bauunternehmen)
- Finanzierungsplan mit KfW-Programmen (124, 261, 300) und Tilgungsplan
- Automatische Deadline-Erinnerungen für kritische Baufristen
- Direkte Anfragen an Fachleute über die Plattform
- Bewertungen echter Bauherren für alle Anbieter
- Pläne: FREE (kostenlos), PRO (19 €/Monat), EXPERT (49 €/Monat)
- Nur für Bauherren und Fachleute in Hessen

GESPRÄCHSSTRATEGIE:
1. Begrüße herzlich, stell eine offene Frage zum Bauvorhaben
2. Erkenne die Bauphase (plant/sucht Grundstück/hat Genehmigung/baut gerade)
3. Zeige konkret, wie BauNavigator genau THIS helfen kann
4. Nenne 1-2 spezifische Features die für ihren Fall relevant sind
5. Lade zur kostenlosen Registrierung ein: "Starten Sie kostenlos unter baunavigator.de/register"

STIL: Freundlich, kompetent, auf Augenhöhe. Keine Werbesprache. Kurze Antworten (max 4 Sätze).
Antworte auf Deutsch. Falls auf Englisch/Russisch gefragt wird, antworte in der gleichen Sprache.

VERBOTEN: Preise erfinden, Funktionen versprechen die nicht existieren, endlose Texte schreiben.
"""


@ai_bp.route('/landing-chat', methods=['POST'])
def landing_chat():
    """Public sales chatbot for the landing page. Rate-limited by IP."""
    import time
    from flask import session

    data = request.get_json(silent=True) or {}
    user_message = (data.get('message') or '').strip()
    if not user_message:
        return jsonify({'error': 'empty'}), 400
    if len(user_message) > 400:
        return jsonify({'error': 'too_long'}), 400

    # Simple rate limit: max 20 messages per session
    count = session.get('lnd_chat_count', 0)
    if count >= 20:
        return jsonify({'answer': 'Sie haben das Limit für diese Sitzung erreicht. Registrieren Sie sich kostenlos für unbegrenzten Zugang!'})
    session['lnd_chat_count'] = count + 1

    result = ask_ai(
        user_message=user_message,
        project=None,
        stage_key=None,
        action_type=ActionType.GENERAL_CONSULT,
        mode=ActionMode.AUTONOMOUS,
        user_id=None,
        system_override=_LANDING_CHAT_SYSTEM,
    )
    return jsonify({'answer': result.get('response', 'Entschuldigung, kurzer Fehler. Bitte versuchen Sie es nochmal.')})


@ai_bp.route('/provider-chat/<provider_id>', methods=['POST'])
def provider_chat(provider_id):
    """Public AI chatbot endpoint for provider mini-sites. No login required."""
    from app.models.enums import PROVIDER_CATEGORY_LABELS
    provider = Provider.query.get_or_404(provider_id)
    if not provider.chatbot_enabled:
        return jsonify({'error': 'Chatbot deaktiviert.'}), 403

    data = request.get_json() or {}
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({'error': 'Keine Nachricht.'}), 400
    if len(user_message) > 500:
        return jsonify({'error': 'Nachricht zu lang.'}), 400

    # Build system prompt
    svc = provider.services.first()
    category_label = PROVIDER_CATEGORY_LABELS.get(svc.category, svc.category.value) if svc else 'Fachbetrieb'
    plz_str = ', '.join(svc.service_area_plz) if svc and svc.service_area_plz else 'Hessen'

    system = (
        f"Du bist der freundliche KI-Assistent von {provider.company_name} ({category_label}). "
        f"Das Unternehmen arbeitet in folgenden Postleitzahlgebieten: {plz_str}. "
        f"Beschreibung: {provider.description or 'Fachbetrieb im Baubereich'}. "
        "Beantworte Anfragen von Bauherren auf Deutsch, präzise und hilfreich. "
        "Weise bei Preisanfragen darauf hin, dass ein individuelles Angebot notwendig ist. "
        "Verweis für Terminanfragen auf das Kontaktformular auf dieser Seite. "
    )
    if provider.chatbot_prompt:
        system += f"\nWeitere Anweisungen: {provider.chatbot_prompt}"

    from app.services.ai_service import ask_ai
    result = ask_ai(
        user_message=user_message,
        project=None,
        stage_key=None,
        action_type=ActionType.GENERAL_CONSULT,
        mode=ActionMode.AUTONOMOUS,
        user_id=None,
        system_override=system,
    )
    return jsonify({'answer': result.get('response', 'Fehler beim Abruf.')})


@ai_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """Общий чат с ИИ-ассистентом."""
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    project_id = data.get('project_id')
    stage_key_str = data.get('stage_key')

    if not message:
        return jsonify({'error': 'Сообщение пустое'}), 400

    project = None
    if project_id:
        project = Project.query.filter_by(
            id=project_id, user_id=current_user.id
        ).first()

    stage_key = None
    if stage_key_str:
        try:
            stage_key = StageKey(stage_key_str)
        except ValueError:
            pass

    result = ask_ai(
        user_message=message,
        project=project,
        stage_key=stage_key,
        action_type=ActionType.GENERAL_CONSULT,
        mode=ActionMode.CONFIRMATION_REQUIRED,
        user_id=current_user.id,
    )
    return jsonify(result)


@ai_bp.route('/zone-analysis/<project_id>', methods=['POST'])
@login_required
def zone_analysis(project_id):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    result = analyze_zone(project)
    return jsonify(result)


@ai_bp.route('/kfw-calc/<project_id>', methods=['POST'])
@login_required
def kfw_calc(project_id):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    result = calculate_kfw(project)
    return jsonify(result)


@ai_bp.route('/checklist/<project_id>/<stage_key>', methods=['POST'])
@login_required
def checklist(project_id, stage_key):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    try:
        sk = StageKey(stage_key)
    except ValueError:
        return jsonify({'error': 'Ungültiger Schritt'}), 400
    result = generate_checklist(project, sk)
    if result.get('checklist_saved'):
        result['reload'] = True  # Signal JS to reload the page to show saved checklist
    return jsonify(result)


@ai_bp.route('/draft-letter/<project_id>/<stage_key>', methods=['POST'])
@login_required
def draft_letter(project_id, stage_key):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    try:
        sk = StageKey(stage_key)
    except ValueError:
        return jsonify({'error': 'Ungültiger Schritt'}), 400

    stage = project.stages.filter_by(stage_key=sk).first()
    subject = request.get_json().get('subject', f'Anfrage zu {STAGE_LABELS.get(sk)}')
    result = generate_bauamt_letter(project, stage, subject, user=current_user)
    return jsonify(result)


@ai_bp.route('/providers/<project_id>/<stage_key>', methods=['POST'])
@login_required
def providers_for_stage(project_id, stage_key):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    try:
        sk = StageKey(stage_key)
    except ValueError:
        return jsonify({'error': 'Ungültiger Schritt'}), 400
    result = find_providers_for_stage(project, sk)
    return jsonify(result)


@ai_bp.route('/generate-document/<project_id>/<stage_key>', methods=['POST'])
@login_required
def generate_document(project_id, stage_key):
    """
    AI generates a text document draft for the given stage.
    Saved as Document with generated_by_ai=True and returned to JS.
    """
    from app.models.models import Document, now_utc
    from app.models.enums import DocType
    import uuid as _uuid

    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    try:
        sk = StageKey(stage_key)
    except ValueError:
        return jsonify({'error': 'Ungültiger Schritt'}), 400

    stage = project.stages.filter_by(stage_key=sk).first_or_404()
    data = request.get_json() or {}
    doc_type_str = data.get('doc_type', 'SONSTIGES')
    try:
        doc_type = DocType(doc_type_str)
    except ValueError:
        doc_type = DocType.SONSTIGES

    # Build a tailored AI prompt per doc type
    doc_type_prompts = {
        DocType.GENEHMIGUNG: (
            "Erstellen Sie einen vollständigen Bauantrag-Entwurf nach HBO Hessen. "
            "Nutzen Sie die Projektdaten. Gliedern Sie klar: Antragsteller, Grundstück, "
            "Vorhaben, Begründung, Anlagen-Liste. Formeller Stil."
        ),
        DocType.BRIEF: (
            "Erstellen Sie eine Checkliste aller Unterlagen, die für die Baugenehmigung "
            "nach HBO Hessen §§ 64–66 benötigt werden, bezogen auf dieses Projekt."
        ),
        DocType.VERTRAG: (
            "Erstellen Sie einen strukturierten Werkvertragsentwurf gemäß BGB §§ 631 ff. "
            "und VOB/B für diesen Bauschritt. Weisen Sie explizit darauf hin, dass dieser "
            "Entwurf vor Unterzeichnung von einem Rechtsanwalt geprüft werden sollte."
        ),
        DocType.STATIK: (
            "Erstellen Sie eine strukturierte Vorlage für ein Baugutachten zu diesem Schritt. "
            "Gliedern Sie: Aufgabenstellung, Befund, Bewertung, Empfehlungen."
        ),
    }
    prompt_extra = doc_type_prompts.get(doc_type, (
        f"Erstellen Sie ein professionelles Dokument vom Typ '{doc_type.value}' "
        f"für den Bauschritt '{STAGE_LABELS.get(sk, sk.value)}' des Projekts. "
        "Gliedern Sie den Text klar und verwenden Sie korrekten formellen deutschen Stil."
    ))

    project_info = (
        f"Projekt: {project.title}\n"
        f"Adresse: {project.address or ''}, {project.address_plz or ''} {project.address_city or ''}\n"
        f"Typ: {project.project_type.value}\n"
        f"Bauschritt: {STAGE_LABELS.get(sk, sk.value)}\n"
    )

    full_prompt = f"{project_info}\n{prompt_extra}"

    from app.services.ai_service import ask_ai
    ai_result = ask_ai(
        user_message=full_prompt,
        project=project,
        stage_key=sk,
        action_type=ActionType.DOCUMENT_GENERATE,
        mode=ActionMode.AUTONOMOUS,
        user_id=current_user.id,
    )

    content = ai_result.get('answer', ai_result.get('result', ''))
    if not content:
        return jsonify({'error': 'KI konnte kein Dokument erstellen.'}), 500

    # Save as Document record
    doc = Document(
        id=str(_uuid.uuid4()),
        project_id=project.id,
        stage_id=stage.id,
        doc_type=doc_type,
        filename=f"ki-entwurf-{sk.value}-{doc_type.value}.txt",
        original_filename=f"KI-Entwurf {STAGE_LABELS.get(sk, sk.value)}.txt",
        generated_by_ai=True,
        ai_draft_content=content,
        description=f"KI-generierter Entwurf — {doc_type.value}",
        uploaded_at=now_utc(),
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({
        'answer': content,
        'doc_id': doc.id,
        'saved': True,
    })


# ─── Outbox Blueprint ──────────────────────────────────────────────────────────
outbox_bp = Blueprint('outbox', __name__)


@outbox_bp.route('/')
@login_required
def index():
    # Все сообщения пользователя (через его проекты)
    messages = (
        MessageOutbox.query
        .join(Project)
        .filter(Project.user_id == current_user.id)
        .order_by(MessageOutbox.created_at.desc())
        .all()
    )
    return render_template('project/outbox.html', messages=messages)


@outbox_bp.route('/<message_id>/approve', methods=['POST'])
@login_required
def approve(message_id):
    msg = (
        MessageOutbox.query
        .join(Project)
        .filter(
            MessageOutbox.id == message_id,
            Project.user_id == current_user.id,
        )
        .first_or_404()
    )
    from app.models.models import now_utc
    msg.status = OutboxStatus.APPROVED
    msg.approved_at = now_utc()
    db.session.commit()

    # Отправка через Mail
    _send_outbox_message(msg)
    flash(f'Nachricht an {msg.recipient_email} wurde gesendet.', 'success')
    return redirect(url_for('outbox.index'))


@outbox_bp.route('/<message_id>/edit', methods=['POST'])
@login_required
def edit(message_id):
    msg = (
        MessageOutbox.query
        .join(Project)
        .filter(
            MessageOutbox.id == message_id,
            Project.user_id == current_user.id,
        )
        .first_or_404()
    )
    msg.subject = request.form.get('subject', msg.subject)
    msg.body_draft = request.form.get('body_draft', msg.body_draft)
    db.session.commit()
    flash('Nachricht gespeichert.', 'success')
    return redirect(url_for('outbox.index'))


@outbox_bp.route('/<message_id>/delete', methods=['POST'])
@login_required
def delete(message_id):
    msg = (
        MessageOutbox.query
        .join(Project)
        .filter(
            MessageOutbox.id == message_id,
            Project.user_id == current_user.id,
        )
        .first_or_404()
    )
    db.session.delete(msg)
    db.session.commit()
    flash('Nachricht gelöscht.', 'info')
    return redirect(url_for('outbox.index'))


def _send_outbox_message(msg: MessageOutbox):
    """
    Send an outbox message.
    If the project has a connected Gmail mailbox, use it (sends from project email).
    Otherwise fall back to Flask-Mail (system sender).
    """
    from app.models.models import now_utc
    try:
        project = msg.project
        if project and project.mailbox and project.mailbox.is_active:
            # Send via project Gmail
            from app.services.gmail_service import send_via_mailbox
            result = send_via_mailbox(
                mailbox=project.mailbox,
                to_email=msg.recipient_email,
                subject=msg.subject,
                body=msg.body_draft,
            )
            if result['success']:
                msg.status = OutboxStatus.SENT
                msg.sent_at = now_utc()
            else:
                msg.status = OutboxStatus.FAILED
                msg.error_log = result.get('error', 'Gmail-Fehler')
        else:
            # Fall back to Flask-Mail (system sender)
            from flask_mail import Message as MailMessage
            from app import mail
            email_msg = MailMessage(
                subject=msg.subject,
                recipients=[msg.recipient_email],
                body=msg.body_draft,
            )
            mail.send(email_msg)
            msg.status = OutboxStatus.SENT
            msg.sent_at = now_utc()

        db.session.commit()
    except Exception as e:
        msg.status = OutboxStatus.FAILED
        msg.error_log = str(e)
        db.session.commit()


# ─── Map Blueprint ─────────────────────────────────────────────────────────────
map_bp = Blueprint('map', __name__)


@map_bp.route('/')
@login_required
def index():
    gemeinden = Gemeinde.query.filter_by(land='HE').order_by(Gemeinde.name).all()
    return render_template('map/index.html', gemeinden=gemeinden)


@map_bp.route('/api/gemeinden')
@login_required
def api_gemeinden():
    gemeinden = Gemeinde.query.filter_by(land='HE').all()
    return jsonify([{
        'id': g.id,
        'name': g.name,
        'landkreis': g.landkreis,
        'ags': g.ags_code,
        'bauamt_name': g.bauamt_name,
        'bauamt_email': g.bauamt_email,
        'bauamt_phone': g.bauamt_phone,
        'bauamt_address': g.bauamt_address,
        'bauamt_url': g.bauamt_url,
        'bauleitplan_portal_url': g.bauleitplan_portal_url,
        'bauordnung_url': g.bauordnung_url,
        'lat': float(g.lat) if g.lat else None,
        'lng': float(g.lng) if g.lng else None,
    } for g in gemeinden])


@map_bp.route('/api/gemeinde/<gemeinde_id>/zones')
@login_required
def api_zones(gemeinde_id):
    zones = BebauungsplanZone.query.filter_by(gemeinde_id=gemeinde_id).all()
    return jsonify([{
        'id': z.id,
        'plan_name': z.plan_name,
        'zone_type': z.zone_type.value,
        'zone_label': z.zone_label(),
        'grz_max': float(z.grz_max) if z.grz_max else None,
        'gfz_max': float(z.gfz_max) if z.gfz_max else None,
        'max_geschosse': z.max_geschosse,
        'max_hoehe_m': float(z.max_hoehe_m) if z.max_hoehe_m else None,
    } for z in zones])


@map_bp.route('/api/providers')
@login_required
def api_providers():
    """Return verified providers that have geo coordinates (via their PLZ→Gemeinde lookup)."""
    category = request.args.get('category', '').strip()
    # Return providers with rating + category; lat/lng come from their primary PLZ Gemeinde lookup
    q = Provider.query.filter_by(verified_status=VerifiedStatus.VERIFIED, is_active=True)
    if category:
        try:
            cat = ProviderCategory(category)
            q = q.join(ProviderService).filter(ProviderService.category == cat).distinct()
        except ValueError:
            pass
    providers = q.limit(100).all()

    # Build PLZ → lat/lng cache from Gemeinde table
    from app.models.models import Gemeinde as _G
    gemeinden = _G.query.filter(_G.lat.isnot(None)).all()
    plz_to_coords: dict = {}
    for g in gemeinden:
        if g.ags_code:
            # use first 5 chars of ags_code as approximate PLZ bucket
            plz_to_coords[g.ags_code[:5]] = (float(g.lat), float(g.lng))

    result = []
    for p in providers:
        lat, lng = None, None
        # Try to get coords from first service area PLZ
        first_svc = p.services.first()
        if first_svc and first_svc.service_area_plz:
            plz_list = first_svc.service_area_plz
            if isinstance(plz_list, list) and plz_list:
                coords = plz_to_coords.get(plz_list[0])
                if coords:
                    lat, lng = coords

        # Jitter slightly so pins don't stack exactly
        import random
        if lat:
            lat += random.uniform(-0.05, 0.05)
            lng += random.uniform(-0.05, 0.05)

        categories = [s.category.value for s in p.services.all()]
        result.append({
            'id': p.id,
            'name': p.company_name,
            'categories': categories,
            'phone': p.contact_phone or '',
            'website': p.website or '',
            'rating': float(p.rating_avg) if p.rating_avg else 0,
            'reviews': p.review_count or 0,
            'lat': lat,
            'lng': lng,
            'url': f'/providers/{p.id}',
        })
    return jsonify(result)


# ─── Providers Blueprint ───────────────────────────────────────────────────────
providers_bp = Blueprint('providers', __name__)


@providers_bp.route('/')
@login_required
def index():
    category = request.args.get('category', '').strip()
    plz = request.args.get('plz', '').strip()

    query = Provider.query.filter_by(
        verified_status=VerifiedStatus.VERIFIED,
        is_active=True
    )

    if category:
        query = query.join(ProviderService).filter(
            ProviderService.category == ProviderCategory(category)
        ).distinct()

    if plz:
        if not category:
            query = query.join(ProviderService)
        query = query.filter(
            cast(ProviderService.service_area_plz, Text).contains(plz)
        ).distinct()

    providers = query.order_by(Provider.rating_avg.desc()).limit(50).all()

    return render_template('providers/index.html',
                           providers=providers,
                           categories=ProviderCategory,
                           category_labels=PROVIDER_CATEGORY_LABELS,
                           selected_category=category,
                           selected_plz=plz)


@providers_bp.route('/<provider_id>')
@login_required
def detail(provider_id):
    provider = Provider.query.filter_by(
        id=provider_id,
        verified_status=VerifiedStatus.VERIFIED
    ).first_or_404()
    reviews = provider.reviews.filter_by(is_published=True).order_by(
        ProviderReview.created_at.desc()
    ).limit(10).all()
    stage_labels_list = list(STAGE_LABELS.items())
    return render_template('providers/detail.html',
                           provider=provider,
                           reviews=reviews,
                           category_labels=PROVIDER_CATEGORY_LABELS,
                           stage_labels_list=stage_labels_list)


@providers_bp.route('/<provider_id>/review', methods=['POST'])
@login_required
def submit_review(provider_id):
    provider = Provider.query.filter_by(
        id=provider_id,
        verified_status=VerifiedStatus.VERIFIED
    ).first_or_404()

    try:
        rating = int(request.form.get('rating', 0))
    except ValueError:
        rating = 0

    if rating < 1 or rating > 5:
        flash('Bitte wählen Sie eine Bewertung zwischen 1 und 5 Sternen.', 'danger')
        return redirect(url_for('providers.detail', provider_id=provider_id))

    # Prevent duplicate review from same user
    existing = ProviderReview.query.filter_by(
        provider_id=provider_id,
        user_id=current_user.id,
    ).first()
    if existing:
        flash('Sie haben diesen Anbieter bereits bewertet.', 'warning')
        return redirect(url_for('providers.detail', provider_id=provider_id))

    title = request.form.get('title', '').strip()[:255] or None
    text = request.form.get('text', '').strip() or None

    review = ProviderReview(
        provider_id=provider_id,
        user_id=current_user.id,
        rating=rating,
        title=title,
        text=text,
    )
    db.session.add(review)

    # Recalculate provider rating_avg and review_count
    all_ratings = [r.rating for r in provider.reviews.all()] + [rating]
    provider.rating_avg = round(sum(all_ratings) / len(all_ratings), 2)
    provider.review_count = len(all_ratings)

    db.session.commit()
    flash('Vielen Dank für Ihre Bewertung!', 'success')
    return redirect(url_for('providers.detail', provider_id=provider_id))


@providers_bp.route('/<provider_id>/contact', methods=['POST'])
@login_required
def contact_provider(provider_id):
    """Create a Lead when a logged-in user sends a contact request from the provider detail page."""
    provider = Provider.query.filter_by(id=provider_id, is_active=True).first_or_404()

    note = request.form.get('note', '').strip()[:1000] or None
    stage_key_str = request.form.get('stage_key', '').strip()
    stage_key = None
    if stage_key_str:
        try:
            stage_key = StageKey(stage_key_str)
        except ValueError:
            pass

    # Prevent duplicate open leads
    existing = Lead.query.filter_by(
        user_id=current_user.id,
        provider_id=provider_id,
        status=LeadStatus.SENT,
    ).first()
    if existing:
        flash('Sie haben bereits eine offene Anfrage an diesen Anbieter.', 'info')
        return redirect(url_for('providers.detail', provider_id=provider_id))

    lead = Lead(
        user_id=current_user.id,
        provider_id=provider_id,
        stage_key=stage_key,
        status=LeadStatus.SENT,
        note=note,
    )
    db.session.add(lead)
    db.session.commit()

    # Notify provider by email
    try:
        from flask_mail import Message as MailMessage
        from app import mail
        mail.send(MailMessage(
            subject=f'Neue Anfrage auf BauNavigator von {current_user.full_name or current_user.email}',
            recipients=[provider.contact_email],
            body=(
                f"Sie haben eine neue Kontaktanfrage erhalten.\n\n"
                f"Von: {current_user.full_name or ''} ({current_user.email})\n"
                f"Bauschritt: {stage_key.value if stage_key else '—'}\n"
                f"Nachricht: {note or '—'}\n\n"
                f"Antworten Sie direkt auf diese E-Mail oder verwalten Sie die Anfrage in Ihrem Anbieter-Portal:\n"
                f"https://baunavigator.de/provider-admin/"
            ),
        ))
    except Exception:
        pass  # Email delivery is best-effort

    flash('Ihre Anfrage wurde gesendet. Der Anbieter meldet sich bei Ihnen.', 'success')
    return redirect(url_for('providers.detail', provider_id=provider_id))


@providers_bp.route('/register', methods=['GET', 'POST'])
def register_provider():
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        vat_id = request.form.get('vat_id', '').strip()
        category_str = request.form.get('category', '').strip()
        plz = request.form.get('plz', '').strip()
        city = request.form.get('city', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        if not company_name or not contact_email:
            flash('Name und E-Mail sind Pflichtfelder.', 'danger')
            return render_template('providers/register.html',
                                   categories=ProviderCategory,
                                   category_labels=PROVIDER_CATEGORY_LABELS)

        if len(password) < 8:
            flash('Das Passwort muss mindestens 8 Zeichen haben.', 'danger')
            return render_template('providers/register.html',
                                   categories=ProviderCategory,
                                   category_labels=PROVIDER_CATEGORY_LABELS)

        if password != password_confirm:
            flash('Die Passwörter stimmen nicht überein.', 'danger')
            return render_template('providers/register.html',
                                   categories=ProviderCategory,
                                   category_labels=PROVIDER_CATEGORY_LABELS)

        # Check duplicate email
        if Provider.query.filter_by(contact_email=contact_email).first():
            flash('Diese E-Mail ist bereits registriert.', 'danger')
            return render_template('providers/register.html',
                                   categories=ProviderCategory,
                                   category_labels=PROVIDER_CATEGORY_LABELS)

        provider = Provider(
            company_name=company_name,
            contact_email=contact_email,
            vat_id=vat_id or None,
            handelsreg_nr=request.form.get('handelsreg_nr', '').strip() or None,
            legal_form=request.form.get('legal_form', '').strip() or None,
            contact_phone=request.form.get('contact_phone', '').strip() or None,
            website=request.form.get('website', '').strip() or None,
            description=request.form.get('description', '').strip() or None,
        )
        provider.set_password(password)
        db.session.add(provider)
        db.session.flush()  # get provider.id

        # Save category as ProviderService
        if category_str:
            try:
                cat = ProviderCategory(category_str)
                svc = ProviderService(
                    provider_id=provider.id,
                    category=cat,
                    service_area_plz=[plz] if plz else None,
                    description=city or None,
                )
                db.session.add(svc)
            except ValueError:
                pass

        db.session.commit()
        flash('Ihre Registrierung wurde eingereicht. Wir prüfen Ihre Angaben und melden uns.', 'success')
        return redirect(url_for('providers.index'))

    return render_template('providers/register.html',
                           categories=ProviderCategory,
                           category_labels=PROVIDER_CATEGORY_LABELS)


# ─── Webhooks Blueprint ────────────────────────────────────────────────────────
webhooks_bp = Blueprint('webhooks', __name__)
from app import csrf  # noqa


@webhooks_bp.route('/stripe', methods=['POST'])
@csrf.exempt
def stripe_webhook():
    """Stripe webhook для обновления подписок."""
    import stripe
    import os
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception:
        return jsonify({'error': 'Invalid signature'}), 400

    from app.models.models import User, Subscription
    from app.models.enums import SubscriptionPlan, SubscriptionStatus

    if event['type'] == 'customer.subscription.updated':
        sub_data = event['data']['object']
        sub = Subscription.query.filter_by(
            stripe_sub_id=sub_data['id']
        ).first()
        if sub:
            sub.status = SubscriptionStatus.ACTIVE if sub_data['status'] == 'active' \
                else SubscriptionStatus.PAST_DUE
            db.session.commit()

    elif event['type'] == 'customer.subscription.deleted':
        sub_data = event['data']['object']
        sub = Subscription.query.filter_by(stripe_sub_id=sub_data['id']).first()
        if sub:
            sub.status = SubscriptionStatus.CANCELLED
            sub.plan = SubscriptionPlan.FREE
            if sub.user:
                sub.user.subscription_tier = SubscriptionPlan.FREE
            db.session.commit()

    return jsonify({'received': True})
