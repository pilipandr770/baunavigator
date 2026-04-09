from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.models import (
    Project, ProjectStage, MessageOutbox, Provider,
    Gemeinde, BebauungsplanZone, ProviderService, ProviderReview
)
from app.models.enums import (
    StageKey, OutboxStatus, VerifiedStatus, STAGE_LABELS,
    ProviderCategory, PROVIDER_CATEGORY_LABELS, ActionMode, ActionType
)
from app.services.ai_service import (
    ask_ai, generate_bauamt_letter, analyze_zone,
    calculate_kfw, find_providers_for_stage, generate_checklist
)

# ─── AI Blueprint ──────────────────────────────────────────────────────────────
ai_bp = Blueprint('ai', __name__)


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
    result = generate_bauamt_letter(project, stage, subject)
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
    """Реальная отправка через Flask-Mail."""
    from flask_mail import Message as MailMessage
    from app import mail
    from app.models.models import now_utc
    try:
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
        'bauamt_email': g.bauamt_email,
        'bauamt_url': g.bauamt_url,
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
            ProviderService.service_area_plz.contains(plz)
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
    return render_template('providers/detail.html',
                           provider=provider,
                           reviews=reviews,
                           category_labels=PROVIDER_CATEGORY_LABELS)


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


@providers_bp.route('/register', methods=['GET', 'POST'])
def register_provider():
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        vat_id = request.form.get('vat_id', '').strip()

        if not company_name or not contact_email:
            flash('Name und E-Mail sind Pflichtfelder.', 'danger')
            return render_template('providers/register.html',
                                   categories=ProviderCategory,
                                   category_labels=PROVIDER_CATEGORY_LABELS)

        provider = Provider(
            company_name=company_name,
            contact_email=contact_email,
            vat_id=vat_id or None,
            legal_form=request.form.get('legal_form', '').strip() or None,
            contact_phone=request.form.get('contact_phone', '').strip() or None,
            website=request.form.get('website', '').strip() or None,
            description=request.form.get('description', '').strip() or None,
        )
        db.session.add(provider)
        db.session.commit()

        flash('Ihre Registrierung wurde eingereicht. Wir prüfen Ihre Angaben.', 'success')
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
