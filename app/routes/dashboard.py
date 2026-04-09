from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import os
from app import db
from app.models.models import Project, ProjectStage, Gemeinde, FinancingPlan
from app.models.enums import (
    StageKey, StageStatus, ProjectType, STAGE_LABELS, STAGE_PHASES,
    PROJECT_TYPE_LABELS, SubscriptionPlan,
)

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    projects = (
        Project.query
        .filter_by(user_id=current_user.id, is_active=True)
        .order_by(Project.updated_at.desc())
        .all()
    )
    archived = (
        Project.query
        .filter_by(user_id=current_user.id, is_active=False)
        .order_by(Project.updated_at.desc())
        .all()
    )
    return render_template('dashboard/index.html',
                           projects=projects,
                           archived=archived,
                           stage_labels=STAGE_LABELS,
                           project_type_labels=PROJECT_TYPE_LABELS)


@dashboard_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            full_name = request.form.get('full_name', '').strip()
            if full_name:
                current_user.full_name = full_name
                db.session.commit()
                flash('Profil wurde aktualisiert.', 'success')
            else:
                flash('Name darf nicht leer sein.', 'danger')

        elif action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not check_password_hash(current_user.password_hash, current_pw):
                flash('Aktuelles Passwort ist falsch.', 'danger')
            elif len(new_pw) < 8:
                flash('Neues Passwort muss mindestens 8 Zeichen haben.', 'danger')
            elif new_pw != confirm_pw:
                flash('Passwörter stimmen nicht überein.', 'danger')
            else:
                current_user.password_hash = generate_password_hash(new_pw)
                db.session.commit()
                flash('Passwort wurde geändert.', 'success')

        return redirect(url_for('dashboard.profile'))

    return render_template('dashboard/profile.html')


@dashboard_bp.route('/upgrade')
@login_required
def upgrade():
    """Страница выбора тарифа с Stripe Checkout."""
    return render_template('dashboard/upgrade.html',
                           SubscriptionPlan=SubscriptionPlan)


@dashboard_bp.route('/upgrade/checkout', methods=['POST'])
@login_required
def create_checkout():
    """Создаёт Stripe Checkout Session и редиректит пользователя."""
    import stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

    plan = request.form.get('plan')
    price_map = {
        'pro': os.getenv('STRIPE_PRICE_PRO'),
        'expert': os.getenv('STRIPE_PRICE_EXPERT'),
    }
    price_id = price_map.get(plan)
    if not price_id or price_id.startswith('price_...'):
        flash('Zahlungssystem ist noch nicht konfiguriert. Bitte kontaktieren Sie uns.', 'warning')
        return redirect(url_for('dashboard.upgrade'))

    try:
        session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=url_for('dashboard.upgrade_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('dashboard.upgrade', _external=True),
            metadata={'user_id': current_user.id, 'plan': plan},
        )
        return redirect(session.url, code=303)
    except stripe.error.StripeError as e:
        flash(f'Zahlungsfehler: {e.user_message}', 'danger')
        return redirect(url_for('dashboard.upgrade'))


@dashboard_bp.route('/upgrade/success')
@login_required
def upgrade_success():
    """Erfolgsseite nach der Zahlung."""
    flash('Vielen Dank! Ihr Abonnement wurde erfolgreich aktiviert.', 'success')
    return redirect(url_for('dashboard.profile'))

