from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models.models import User, Subscription
from app.models.enums import SubscriptionPlan, SubscriptionStatus

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()

        if not email or not password or not full_name:
            flash('Bitte alle Pflichtfelder ausfüllen.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('Passwort muss mindestens 8 Zeichen haben.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Diese E-Mail ist bereits registriert.', 'danger')
            return render_template('auth/register.html')

        user = User(email=email, full_name=full_name)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        # Создаём бесплатную подписку
        sub = Subscription(
            user_id=user.id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
        )
        db.session.add(sub)
        db.session.commit()

        login_user(user)
        flash(f'Willkommen, {full_name}! Ihr Konto wurde erstellt.', 'success')
        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('E-Mail oder Passwort falsch.', 'danger')
            return render_template('auth/login.html')

        if not user.is_active:
            flash('Ihr Konto ist deaktiviert.', 'danger')
            return render_template('auth/login.html')

        from app.models.models import now_utc
        user.last_login_at = now_utc()
        db.session.commit()

        login_user(user, remember=remember)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sie wurden abgemeldet.', 'info')
    return redirect(url_for('auth.login'))
