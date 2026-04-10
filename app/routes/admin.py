"""
Platform Admin Panel — /admin/*

Simple secret-key auth: admin logs in with ADMIN_PASSWORD from env.
Session key: session['is_admin'] = True.
"""
from functools import wraps
import os

from flask import (
    Blueprint, render_template, redirect, url_for, flash,
    request, session, jsonify, current_app,
)
from sqlalchemy import func
from app import db
from app.models.models import (
    Provider, User, Lead, ProviderReview, Project,
    Subscription,
)
from app.models.enums import (
    VerifiedStatus, ProviderPlan, SubscriptionPlan,
    LeadStatus, PROVIDER_CATEGORY_LABELS,
)

admin_bp = Blueprint('admin', __name__)


# ── Auth ─────────────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


# ── Login / Logout ────────────────────────────────────────────────────────────

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('is_admin'):
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        admin_pw = os.getenv('ADMIN_PASSWORD', '')
        if admin_pw and password == admin_pw:
            session['is_admin'] = True
            session.permanent = True
            return redirect(url_for('admin.dashboard'))
        flash('Falsches Passwort.', 'danger')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin.login'))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route('/')
@admin_required
def dashboard():
    stats = {
        'users_total': User.query.count(),
        'users_confirmed': User.query.filter_by(email_confirmed=True).count(),
        'projects_total': Project.query.count(),
        'providers_total': Provider.query.count(),
        'providers_pending': Provider.query.filter_by(
            verified_status=VerifiedStatus.PENDING).count(),
        'providers_verified': Provider.query.filter_by(
            verified_status=VerifiedStatus.VERIFIED).count(),
        'leads_total': Lead.query.count(),
        'leads_new': Lead.query.filter_by(status=LeadStatus.SENT).count(),
        'pro_users': User.query.filter(
            User.subscription_tier != SubscriptionPlan.FREE).count(),
    }
    recent_providers = (
        Provider.query
        .filter_by(verified_status=VerifiedStatus.PENDING)
        .order_by(Provider.registered_at.desc())
        .limit(5).all()
    )
    recent_users = (
        User.query
        .order_by(User.created_at.desc())
        .limit(5).all()
    )
    return render_template('admin/dashboard.html',
                           stats=stats,
                           recent_providers=recent_providers,
                           recent_users=recent_users)


# ── Providers ─────────────────────────────────────────────────────────────────

@admin_bp.route('/providers')
@admin_required
def providers():
    status_filter = request.args.get('status', '').strip()
    q = Provider.query.order_by(Provider.registered_at.desc())
    if status_filter:
        try:
            q = q.filter_by(verified_status=VerifiedStatus(status_filter))
        except ValueError:
            pass
    all_providers = q.all()
    return render_template('admin/providers.html',
                           providers=all_providers,
                           verified_status=VerifiedStatus,
                           category_labels=PROVIDER_CATEGORY_LABELS,
                           selected_status=status_filter)


@admin_bp.route('/providers/<provider_id>/activate', methods=['POST'])
@admin_required
def activate_provider(provider_id):
    p = Provider.query.get_or_404(provider_id)
    p.verified_status = VerifiedStatus.VERIFIED
    p.portal_active = True
    p.is_active = True
    db.session.commit()

    # Email notification
    _notify_provider(p, activated=True)
    flash(f'✅ {p.company_name} wurde aktiviert und verifiziert.', 'success')
    return redirect(url_for('admin.providers'))


@admin_bp.route('/providers/<provider_id>/reject', methods=['POST'])
@admin_required
def reject_provider(provider_id):
    p = Provider.query.get_or_404(provider_id)
    reason = request.form.get('reason', '').strip()
    p.verified_status = VerifiedStatus.REJECTED
    p.portal_active = False
    p.suspended_reason = reason or None
    db.session.commit()

    _notify_provider(p, activated=False, reason=reason)
    flash(f'❌ {p.company_name} wurde abgelehnt.', 'info')
    return redirect(url_for('admin.providers'))


@admin_bp.route('/providers/<provider_id>/suspend', methods=['POST'])
@admin_required
def suspend_provider(provider_id):
    from app.models.models import now_utc
    p = Provider.query.get_or_404(provider_id)
    reason = request.form.get('reason', '').strip()
    p.verified_status = VerifiedStatus.SUSPENDED
    p.portal_active = False
    p.is_active = False
    p.suspended_at = now_utc()
    p.suspended_reason = reason or None
    db.session.commit()
    flash(f'⏸ {p.company_name} wurde gesperrt.', 'warning')
    return redirect(url_for('admin.providers'))


@admin_bp.route('/providers/<provider_id>/set-password', methods=['POST'])
@admin_required
def set_provider_password(provider_id):
    p = Provider.query.get_or_404(provider_id)
    new_pw = request.form.get('password', '').strip()
    if len(new_pw) < 8:
        flash('Passwort muss mindestens 8 Zeichen haben.', 'danger')
        return redirect(url_for('admin.providers'))
    p.set_password(new_pw)
    db.session.commit()
    flash(f'🔑 Passwort für {p.company_name} gesetzt.', 'success')
    return redirect(url_for('admin.providers'))


@admin_bp.route('/providers/<provider_id>')
@admin_required
def provider_detail(provider_id):
    p = Provider.query.get_or_404(provider_id)
    leads = p.leads.order_by(Lead.created_at.desc()).limit(20).all()
    reviews = p.reviews.order_by(ProviderReview.created_at.desc()).all()
    return render_template('admin/provider_detail.html',
                           provider=p,
                           leads=leads,
                           reviews=reviews,
                           category_labels=PROVIDER_CATEGORY_LABELS,
                           verified_status=VerifiedStatus,
                           lead_status=LeadStatus)


# ── Users ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/users')
@admin_required
def users():
    plan_filter = request.args.get('plan', '').strip()
    q = User.query.order_by(User.created_at.desc())
    if plan_filter:
        try:
            q = q.filter(User.subscription_tier == SubscriptionPlan(plan_filter))
        except ValueError:
            pass
    all_users = q.all()
    plan_opts = [(p.value, p.value.upper()) for p in SubscriptionPlan]
    return render_template('admin/users.html',
                           users=all_users,
                           total=User.query.count(),
                           plan_opts=plan_opts,
                           subscription_plan=SubscriptionPlan,
                           selected_plan=plan_filter)


@admin_bp.route('/users/<user_id>/toggle-active', methods=['POST'])
@admin_required
def toggle_user_active(user_id):
    u = User.query.get_or_404(user_id)
    u.is_active = not u.is_active
    db.session.commit()
    state = 'aktiviert' if u.is_active else 'deaktiviert'
    flash(f'Nutzer {u.email} wurde {state}.', 'info')
    return redirect(url_for('admin.users'))


# ── Leads overview ────────────────────────────────────────────────────────────

@admin_bp.route('/leads')
@admin_required
def leads():
    all_leads = (
        Lead.query
        .order_by(Lead.created_at.desc())
        .limit(100).all()
    )
    return render_template('admin/leads.html',
                           leads=all_leads,
                           lead_status=LeadStatus)


# ── Helper ────────────────────────────────────────────────────────────────────

def _notify_provider(provider: Provider, activated: bool, reason: str = ''):
    try:
        from flask_mail import Message as MailMsg
        from app import mail
        if activated:
            subject = 'Ihr BauNavigator-Konto wurde aktiviert!'
            body = (
                f"Sehr geehrte Damen und Herren,\n\n"
                f"Ihr Anbieter-Konto für {provider.company_name} wurde erfolgreich geprüft "
                f"und freigeschaltet.\n\n"
                f"Sie können sich jetzt im Anbieter-Portal anmelden:\n"
                f"https://baunavigator.de/provider-admin/login\n\n"
                f"Mit freundlichen Grüßen,\nDas BauNavigator-Team"
            )
        else:
            subject = 'Ihre BauNavigator-Registrierung konnte nicht bestätigt werden'
            body = (
                f"Sehr geehrte Damen und Herren,\n\n"
                f"Leider konnten wir Ihre Registrierung für {provider.company_name} "
                f"nicht bestätigen.\n"
                f"{('Grund: ' + reason) if reason else ''}\n\n"
                f"Bitte nehmen Sie Kontakt mit uns auf, wenn Sie Fragen haben.\n\n"
                f"Mit freundlichen Grüßen,\nDas BauNavigator-Team"
            )
        mail.send(MailMsg(subject=subject, recipients=[provider.contact_email], body=body))
    except Exception:
        pass  # Email delivery is best-effort
