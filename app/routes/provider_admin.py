"""
Provider Admin Portal — /provider-admin/*

Providers log in with their contact_email + password (stored on Provider.password_hash).
Auth is tracked via session['provider_id'] (separate from Flask-Login user sessions).
"""
from functools import wraps

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, session, jsonify,
)
from werkzeug.utils import secure_filename
from app import db
from app.models.models import Provider, ProviderService, ProviderReview, Lead
from app.models.enums import (
    ProviderCategory, PROVIDER_CATEGORY_LABELS,
    LeadStatus, VerifiedStatus,
)

provider_admin_bp = Blueprint('provider_admin', __name__)


# ── Auth helper ──────────────────────────────────────────────────────────────

def get_current_provider():
    pid = session.get('provider_id')
    if pid:
        return Provider.query.get(pid)
    return None


def provider_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('provider_id'):
            flash('Bitte melden Sie sich als Anbieter an.', 'info')
            return redirect(url_for('provider_admin.login'))
        return f(*args, **kwargs)
    return decorated


# ── Login / Logout ───────────────────────────────────────────────────────────

@provider_admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('provider_id'):
        return redirect(url_for('provider_admin.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        provider = Provider.query.filter_by(contact_email=email).first()
        if provider and provider.password_hash and provider.check_password(password):
            if not provider.portal_active:
                flash(
                    'Ihr Konto ist noch nicht aktiviert. '
                    'Wir melden uns nach der Verifizierung.', 'warning'
                )
                return render_template('provider_admin/login.html')
            session['provider_id'] = provider.id
            flash(f'Willkommen, {provider.company_name}!', 'success')
            return redirect(url_for('provider_admin.dashboard'))

        flash('E-Mail oder Passwort ist falsch.', 'danger')

    return render_template('provider_admin/login.html')


@provider_admin_bp.route('/logout')
def logout():
    session.pop('provider_id', None)
    flash('Sie wurden abgemeldet.', 'info')
    return redirect(url_for('provider_admin.login'))


# ── Dashboard ────────────────────────────────────────────────────────────────

@provider_admin_bp.route('/')
@provider_required
def dashboard():
    p = get_current_provider()
    total_leads = p.leads.count()
    new_leads = p.leads.filter_by(status=LeadStatus.SENT).count()
    won_leads = p.leads.filter_by(status=LeadStatus.WON).count()
    review_count = p.reviews.filter_by(is_published=True).count()
    recent_leads = p.leads.order_by(Lead.created_at.desc()).limit(5).all()

    return render_template(
        'provider_admin/dashboard.html',
        provider=p,
        total_leads=total_leads,
        new_leads=new_leads,
        won_leads=won_leads,
        review_count=review_count,
        recent_leads=recent_leads,
        lead_status=LeadStatus,
    )


# ── Profile editor ───────────────────────────────────────────────────────────

@provider_admin_bp.route('/profile', methods=['GET', 'POST'])
@provider_required
def profile():
    p = get_current_provider()

    if request.method == 'POST':
        p.company_name = request.form.get('company_name', p.company_name).strip() or p.company_name
        p.contact_phone = request.form.get('contact_phone', '').strip() or None
        p.website = request.form.get('website', '').strip() or None
        p.description = request.form.get('description', '').strip() or None
        p.tagline = request.form.get('tagline', '').strip() or None
        p.legal_form = request.form.get('legal_form', '').strip() or None

        # Update primary service category / PLZ
        category_str = request.form.get('category', '').strip()
        plz_raw = request.form.get('plz', '').strip()
        plz_list = [x.strip() for x in plz_raw.split(',') if x.strip()] if plz_raw else []

        svc = p.services.first()
        if category_str:
            try:
                cat = ProviderCategory(category_str)
                if svc:
                    svc.category = cat
                    if plz_list:
                        svc.service_area_plz = plz_list
                else:
                    svc = ProviderService(
                        provider_id=p.id,
                        category=cat,
                        service_area_plz=plz_list or None,
                    )
                    db.session.add(svc)
            except ValueError:
                pass

        db.session.commit()
        flash('Profil gespeichert.', 'success')
        return redirect(url_for('provider_admin.profile'))

    svc = p.services.first()
    current_plz = ', '.join(svc.service_area_plz) if svc and svc.service_area_plz else ''
    return render_template(
        'provider_admin/profile.html',
        provider=p,
        service=svc,
        current_plz=current_plz,
        categories=ProviderCategory,
        category_labels=PROVIDER_CATEGORY_LABELS,
    )


# ── Leads CRM ────────────────────────────────────────────────────────────────

@provider_admin_bp.route('/leads')
@provider_required
def leads():
    p = get_current_provider()
    status_filter = request.args.get('status', '').strip()
    q = p.leads.order_by(Lead.created_at.desc())
    if status_filter:
        try:
            q = q.filter_by(status=LeadStatus(status_filter))
        except ValueError:
            pass
    all_leads = q.all()
    return render_template(
        'provider_admin/leads.html',
        provider=p,
        leads=all_leads,
        lead_status=LeadStatus,
        selected_status=status_filter,
    )


@provider_admin_bp.route('/leads/<lead_id>/status', methods=['POST'])
@provider_required
def update_lead_status(lead_id):
    p = get_current_provider()
    lead = Lead.query.filter_by(id=lead_id, provider_id=p.id).first_or_404()
    new_status_str = request.form.get('status', '').strip()
    try:
        lead.status = LeadStatus(new_status_str)
        db.session.commit()
        flash('Status aktualisiert.', 'success')
    except ValueError:
        flash('Ungültiger Status.', 'danger')
    return redirect(url_for('provider_admin.leads'))


# ── Availability Slots ───────────────────────────────────────────────────────

@provider_admin_bp.route('/slots', methods=['GET', 'POST'])
@provider_required
def slots():
    p = get_current_provider()

    if request.method == 'POST':
        action = request.form.get('action', '')
        current_slots = p.available_slots or []

        if action == 'add':
            date = request.form.get('date', '').strip()
            time = request.form.get('time', '').strip()
            duration = request.form.get('duration', '60').strip()
            note = request.form.get('note', '').strip()
            if date and time:
                current_slots.append({
                    'date': date,
                    'time': time,
                    'duration_min': int(duration) if duration.isdigit() else 60,
                    'note': note,
                })
                p.available_slots = current_slots
                db.session.commit()
                flash('Termin hinzugefügt.', 'success')

        elif action == 'delete':
            idx_str = request.form.get('index', '')
            if idx_str.isdigit():
                idx = int(idx_str)
                if 0 <= idx < len(current_slots):
                    current_slots.pop(idx)
                    p.available_slots = current_slots
                    db.session.commit()
                    flash('Termin gelöscht.', 'info')

        return redirect(url_for('provider_admin.slots'))

    return render_template('provider_admin/slots.html', provider=p)


# ── AI Chatbot Settings ──────────────────────────────────────────────────────

@provider_admin_bp.route('/chatbot', methods=['GET', 'POST'])
@provider_required
def chatbot():
    p = get_current_provider()

    if request.method == 'POST':
        p.chatbot_enabled = request.form.get('chatbot_enabled') == '1'
        p.chatbot_greeting = request.form.get('chatbot_greeting', '').strip()[:500] or None
        p.chatbot_prompt = request.form.get('chatbot_prompt', '').strip() or None
        db.session.commit()
        flash('Chatbot-Einstellungen gespeichert.', 'success')
        return redirect(url_for('provider_admin.chatbot'))

    return render_template('provider_admin/chatbot.html', provider=p)


# ── Reviews ──────────────────────────────────────────────────────────────────

@provider_admin_bp.route('/reviews')
@provider_required
def reviews():
    p = get_current_provider()
    all_reviews = p.reviews.order_by(ProviderReview.created_at.desc()).all()
    return render_template('provider_admin/reviews.html', provider=p, reviews=all_reviews)


# ── Password change ──────────────────────────────────────────────────────────

@provider_admin_bp.route('/change-password', methods=['GET', 'POST'])
@provider_required
def change_password():
    p = get_current_provider()

    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not p.check_password(current_pw):
            flash('Aktuelles Passwort ist falsch.', 'danger')
        elif len(new_pw) < 8:
            flash('Neues Passwort muss mindestens 8 Zeichen haben.', 'danger')
        elif new_pw != confirm_pw:
            flash('Passwörter stimmen nicht überein.', 'danger')
        else:
            p.set_password(new_pw)
            db.session.commit()
            flash('Passwort geändert.', 'success')
            return redirect(url_for('provider_admin.dashboard'))

    return render_template('provider_admin/change_password.html', provider=p)
