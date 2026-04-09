from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app import db
from app.models.models import User, Subscription
from app.models.enums import SubscriptionPlan, SubscriptionStatus

auth_bp = Blueprint('auth', __name__)


def _make_token(email: str) -> str:
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(email, salt='email-confirm')


def _verify_token(token: str, max_age: int = 86400):
    """Returns email string or None. max_age in seconds (default 24h)."""
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = s.loads(token, salt='email-confirm', max_age=max_age)
        return email
    except (SignatureExpired, BadSignature):
        return None


def _send_confirmation_email(user: User):
    from flask_mail import Message as MailMessage
    from app import mail
    token = _make_token(user.email)
    confirm_url = url_for('auth.confirm_email', token=token, _external=True)
    try:
        msg = MailMessage(
            subject='BauNavigator — E-Mail-Adresse bestätigen',
            recipients=[user.email],
            html=f"""
<p>Hallo {user.full_name},</p>
<p>bitte bestätigen Sie Ihre E-Mail-Adresse, indem Sie auf den folgenden Link klicken:</p>
<p><a href="{confirm_url}" style="background:#2563eb;color:#fff;padding:10px 20px;
border-radius:6px;text-decoration:none;display:inline-block;">E-Mail bestätigen</a></p>
<p>Der Link ist 24 Stunden gültig.</p>
<p>Falls Sie kein Konto bei BauNavigator registriert haben, ignorieren Sie diese E-Mail.</p>
<p>Mit freundlichen Grüßen,<br>Das BauNavigator-Team</p>
""",
        )
        mail.send(msg)
        return True
    except Exception:
        return False


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

        sub = Subscription(
            user_id=user.id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
        )
        db.session.add(sub)
        db.session.commit()

        sent = _send_confirmation_email(user)
        login_user(user)

        if sent:
            flash(
                f'Willkommen, {full_name}! Bitte bestätigen Sie Ihre E-Mail-Adresse '
                f'— wir haben einen Link an {email} gesendet.',
                'success',
            )
        else:
            # Mail not configured (local dev) — confirm automatically
            user.email_confirmed = True
            db.session.commit()
            flash(f'Willkommen, {full_name}! Ihr Konto ist aktiv.', 'success')

        return redirect(url_for('dashboard.index'))

    return render_template('auth/register.html')


@auth_bp.route('/confirm/<token>')
def confirm_email(token):
    email = _verify_token(token)
    if not email:
        flash('Der Bestätigungslink ist ungültig oder abgelaufen.', 'danger')
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first_or_404()
    if user.email_confirmed:
        flash('Ihre E-Mail-Adresse ist bereits bestätigt.', 'info')
    else:
        user.email_confirmed = True
        db.session.commit()
        flash('E-Mail-Adresse erfolgreich bestätigt! Sie können sich jetzt anmelden.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-confirmation')
@login_required
def resend_confirmation():
    if current_user.email_confirmed:
        flash('Ihre E-Mail-Adresse ist bereits bestätigt.', 'info')
        return redirect(url_for('dashboard.index'))
    sent = _send_confirmation_email(current_user)
    if sent:
        flash(f'Bestätigungs-E-Mail wurde erneut an {current_user.email} gesendet.', 'success')
    else:
        flash('E-Mail konnte nicht gesendet werden. Bitte prüfen Sie die Mail-Konfiguration.', 'danger')
    return redirect(url_for('dashboard.index'))


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
