import uuid
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager
from app.models.enums import (
    SubscriptionPlan, SubscriptionStatus, ProjectType,
    StageKey, StageStatus, ActionMode, ActionType,
    OutboxStatus, RecipientType, DocType, ZoneType,
    ProviderCategory, LicenseType, VerifiedStatus,
    ProviderPlan, LeadStatus, FinancingStatus
)


def now_utc():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────
# USERS DOMAIN
# ─────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(50))
    full_name = db.Column(db.String(255))
    password_hash = db.Column(db.String(255))
    preferred_lang = db.Column(db.String(2), default='de')
    subscription_tier = db.Column(
        db.Enum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    email_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))

    # Relations
    subscription = db.relationship('Subscription', back_populates='user', uselist=False)
    projects = db.relationship('Project', back_populates='user', lazy='dynamic')
    ai_actions = db.relationship('AIActionLog', back_populates='user', lazy='dynamic')
    reviews = db.relationship('ProviderReview', back_populates='user', lazy='dynamic')
    leads = db.relationship('Lead', back_populates='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can_use_ai_drafts(self):
        return self.subscription_tier in (SubscriptionPlan.PRO, SubscriptionPlan.EXPERT)

    def can_use_advanced_finance(self):
        return self.subscription_tier == SubscriptionPlan.EXPERT

    def __repr__(self):
        return f'<User {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


class Subscription(db.Model):
    __tablename__ = 'subscriptions'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, unique=True)
    plan = db.Column(db.Enum(SubscriptionPlan), nullable=False, default=SubscriptionPlan.FREE)
    status = db.Column(db.Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    stripe_sub_id = db.Column(db.String(255), unique=True)
    stripe_customer_id = db.Column(db.String(255))
    current_period_end = db.Column(db.Date)
    cancelled_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    user = db.relationship('User', back_populates='subscription')


# ─────────────────────────────────────────────────────
# GEO DOMAIN
# ─────────────────────────────────────────────────────

class Gemeinde(db.Model):
    __tablename__ = 'gemeinden'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    name = db.Column(db.String(255), nullable=False, index=True)
    land = db.Column(db.String(2), nullable=False, default='HE')
    landkreis = db.Column(db.String(255))
    ags_code = db.Column(db.String(8), unique=True, index=True)  # Amtlicher Gemeindeschlüssel
    # boundary = db.Column(Geometry('MULTIPOLYGON', srid=4326))  # PostGIS — раскомментировать после установки
    lat = db.Column(db.Numeric(10, 7))   # центр общины
    lng = db.Column(db.Numeric(10, 7))
    bauamt_name = db.Column(db.String(255))
    bauamt_email = db.Column(db.String(255))
    bauamt_phone = db.Column(db.String(100))
    bauamt_address = db.Column(db.String(500))
    bauamt_url = db.Column(db.String(500))
    bauordnung_url = db.Column(db.String(500))
    bauleitplan_portal_url = db.Column(db.String(500))
    data_updated_at = db.Column(db.Date)

    zones = db.relationship('BebauungsplanZone', back_populates='gemeinde', lazy='dynamic')
    projects = db.relationship('Project', back_populates='gemeinde', lazy='dynamic')

    def __repr__(self):
        return f'<Gemeinde {self.name}>'


class BebauungsplanZone(db.Model):
    __tablename__ = 'bebauungsplan_zones'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    gemeinde_id = db.Column(db.String(36), db.ForeignKey('gemeinden.id'), nullable=False, index=True)
    plan_name = db.Column(db.String(255))
    plan_number = db.Column(db.String(100))
    zone_type = db.Column(db.Enum(ZoneType), nullable=False)
    # geometry = db.Column(Geometry('MULTIPOLYGON', srid=4326))  # PostGIS
    grz_max = db.Column(db.Numeric(4, 2))       # Grundflächenzahl max
    gfz_max = db.Column(db.Numeric(4, 2))       # Geschossflächenzahl max
    max_geschosse = db.Column(db.SmallInteger)
    max_hoehe_m = db.Column(db.Numeric(5, 2))
    bauweise = db.Column(db.String(50))          # o = offen, g = geschlossen
    sonderregeln = db.Column(db.JSON)            # jsonb für Sonderregelungen
    source_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    gemeinde = db.relationship('Gemeinde', back_populates='zones')
    projects = db.relationship('Project', back_populates='zone', lazy='dynamic')

    def zone_label(self):
        labels = {
            ZoneType.WA: 'Allgemeines Wohngebiet (WA)',
            ZoneType.WR: 'Reines Wohngebiet (WR)',
            ZoneType.MI: 'Mischgebiet (MI)',
            ZoneType.GE: 'Gewerbegebiet (GE)',
            ZoneType.GI: 'Kerngebiet (GI)',
            ZoneType.PARAGRAPH_34: 'Innenbereich §34 BauGB',
            ZoneType.PARAGRAPH_35: 'Außenbereich §35 BauGB',
        }
        return labels.get(self.zone_type, self.zone_type.value)


# ─────────────────────────────────────────────────────
# PROJECT DOMAIN
# ─────────────────────────────────────────────────────

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    gemeinde_id = db.Column(db.String(36), db.ForeignKey('gemeinden.id'), index=True)
    zone_id = db.Column(db.String(36), db.ForeignKey('bebauungsplan_zones.id'))
    title = db.Column(db.String(255), nullable=False)
    project_type = db.Column(db.Enum(ProjectType), default=ProjectType.NEUBAU_EFH)
    address = db.Column(db.String(500))
    address_plz = db.Column(db.String(10))
    address_city = db.Column(db.String(255))
    # location = db.Column(Geometry('POINT', srid=4326))  # PostGIS
    lat = db.Column(db.Numeric(10, 7))
    lng = db.Column(db.Numeric(10, 7))
    current_stage = db.Column(db.Enum(StageKey), default=StageKey.LAND_SEARCH)
    budget_total = db.Column(db.Numeric(12, 2))
    wohnflaeche_m2 = db.Column(db.Numeric(8, 2))
    grundstueck_m2 = db.Column(db.Numeric(10, 2))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    # Relations
    user = db.relationship('User', back_populates='projects')
    gemeinde = db.relationship('Gemeinde', back_populates='projects')
    zone = db.relationship('BebauungsplanZone', back_populates='projects')
    stages = db.relationship('ProjectStage', back_populates='project',
                              order_by='ProjectStage.created_at', lazy='dynamic')
    documents = db.relationship('Document', back_populates='project', lazy='dynamic')
    financing = db.relationship('FinancingPlan', back_populates='project', uselist=False)
    ai_actions = db.relationship('AIActionLog', back_populates='project', lazy='dynamic')
    outbox_messages = db.relationship('MessageOutbox', back_populates='project', lazy='dynamic')
    leads = db.relationship('Lead', back_populates='project', lazy='dynamic')
    reviews = db.relationship('ProviderReview', back_populates='project', lazy='dynamic')

    def get_stage(self, stage_key):
        return self.stages.filter_by(stage_key=stage_key).first()

    def get_active_stages(self):
        return self.stages.filter_by(status=StageStatus.ACTIVE).all()

    def completion_percent(self):
        from app.models.enums import STAGE_PHASES
        total = sum(len(p['stages']) for p in STAGE_PHASES.values())
        done = self.stages.filter_by(status=StageStatus.DONE).count()
        return int((done / total) * 100) if total > 0 else 0

    def __repr__(self):
        return f'<Project {self.title}>'


class ProjectStage(db.Model):
    __tablename__ = 'project_stages'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'), nullable=False, index=True)
    stage_key = db.Column(db.Enum(StageKey), nullable=False)
    status = db.Column(db.Enum(StageStatus), default=StageStatus.PENDING, nullable=False)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    deadline_at = db.Column(db.Date)
    notes = db.Column(db.Text)
    checklist = db.Column(db.JSON)   # [{item, done, required}]
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    project = db.relationship('Project', back_populates='stages')
    documents = db.relationship('Document', back_populates='stage', lazy='dynamic')
    outbox_messages = db.relationship('MessageOutbox', back_populates='stage', lazy='dynamic')

    def activate(self):
        self.status = StageStatus.ACTIVE
        self.started_at = now_utc()

    def complete(self):
        self.status = StageStatus.DONE
        self.completed_at = now_utc()


class Document(db.Model):
    __tablename__ = 'documents'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'), nullable=False, index=True)
    stage_id = db.Column(db.String(36), db.ForeignKey('project_stages.id'), index=True)
    doc_type = db.Column(db.Enum(DocType), nullable=False, default=DocType.SONSTIGES)
    filename = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(500))
    storage_path = db.Column(db.String(1000))
    mime_type = db.Column(db.String(100))
    size_bytes = db.Column(db.BigInteger)
    generated_by_ai = db.Column(db.Boolean, default=False, nullable=False)
    ai_draft_content = db.Column(db.Text)   # для текстовых черновиков от ИИ
    description = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    project = db.relationship('Project', back_populates='documents')
    stage = db.relationship('ProjectStage', back_populates='documents')


# ─────────────────────────────────────────────────────
# AI DOMAIN
# ─────────────────────────────────────────────────────

class AIActionLog(db.Model):
    __tablename__ = 'ai_actions_log'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'), index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    action_type = db.Column(db.Enum(ActionType), nullable=False)
    mode = db.Column(db.Enum(ActionMode), nullable=False)
    stage_key = db.Column(db.Enum(StageKey))
    input_context = db.Column(db.JSON)
    output_summary = db.Column(db.Text)
    full_response = db.Column(db.Text)
    tokens_used = db.Column(db.Integer)
    model_version = db.Column(db.String(100))
    duration_ms = db.Column(db.Integer)
    error = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    project = db.relationship('Project', back_populates='ai_actions')
    user = db.relationship('User', back_populates='ai_actions')


class MessageOutbox(db.Model):
    __tablename__ = 'messages_outbox'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'), nullable=False, index=True)
    stage_id = db.Column(db.String(36), db.ForeignKey('project_stages.id'), index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    recipient_type = db.Column(db.Enum(RecipientType), nullable=False)
    recipient_name = db.Column(db.String(255))
    recipient_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(500), nullable=False)
    body_draft = db.Column(db.Text, nullable=False)
    attached_doc_ids = db.Column(db.JSON)   # list of doc UUIDs
    status = db.Column(db.Enum(OutboxStatus), default=OutboxStatus.DRAFT, nullable=False)
    approved_at = db.Column(db.DateTime(timezone=True))
    sent_at = db.Column(db.DateTime(timezone=True))
    error_log = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    project = db.relationship('Project', back_populates='outbox_messages')
    stage = db.relationship('ProjectStage', back_populates='outbox_messages')


# ─────────────────────────────────────────────────────
# PROVIDER DOMAIN
# ─────────────────────────────────────────────────────

class Provider(db.Model):
    __tablename__ = 'providers'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    company_name = db.Column(db.String(255), nullable=False)
    legal_form = db.Column(db.String(100))   # GmbH, GbR, Einzelunternehmen…
    vat_id = db.Column(db.String(50), unique=True)
    handelsreg_nr = db.Column(db.String(100))
    contact_email = db.Column(db.String(255), nullable=False)
    contact_phone = db.Column(db.String(100))
    website = db.Column(db.String(500))
    description = db.Column(db.Text)
    logo_path = db.Column(db.String(500))
    verified_status = db.Column(
        db.Enum(VerifiedStatus), default=VerifiedStatus.PENDING, nullable=False
    )
    vat_verified = db.Column(db.Boolean, default=False)
    vat_verified_at = db.Column(db.DateTime(timezone=True))
    rating_avg = db.Column(db.Numeric(3, 2), default=0)
    review_count = db.Column(db.Integer, default=0)
    subscription_plan = db.Column(db.Enum(ProviderPlan), default=ProviderPlan.BASIC)
    stripe_customer_id = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)
    registered_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)
    suspended_at = db.Column(db.DateTime(timezone=True))
    suspended_reason = db.Column(db.Text)
    # Provider portal fields
    password_hash = db.Column(db.String(255))
    portal_active = db.Column(db.Boolean, default=False, nullable=False)
    tagline = db.Column(db.String(255))
    hero_image_path = db.Column(db.String(500))
    chatbot_enabled = db.Column(db.Boolean, default=True)
    chatbot_greeting = db.Column(db.String(500))
    chatbot_prompt = db.Column(db.Text)
    available_slots = db.Column(db.JSON)  # list of {date, time, duration_min, note}

    # Relations
    licenses = db.relationship('ProviderLicense', back_populates='provider',
                                lazy='dynamic', cascade='all, delete-orphan')
    services = db.relationship('ProviderService', back_populates='provider',
                                lazy='dynamic', cascade='all, delete-orphan')
    reviews = db.relationship('ProviderReview', back_populates='provider', lazy='dynamic')
    leads = db.relationship('Lead', back_populates='provider', lazy='dynamic')

    def is_verified(self):
        return self.verified_status == VerifiedStatus.VERIFIED

    def has_valid_licenses(self):
        from datetime import date
        today = date.today()
        expired = self.licenses.filter(
            ProviderLicense.valid_until < today
        ).count()
        return expired == 0

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Provider {self.company_name}>'


class ProviderLicense(db.Model):
    __tablename__ = 'provider_licenses'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    provider_id = db.Column(db.String(36), db.ForeignKey('providers.id'), nullable=False, index=True)
    license_type = db.Column(db.Enum(LicenseType), nullable=False)
    issuing_body = db.Column(db.String(255))
    license_number = db.Column(db.String(255))
    valid_from = db.Column(db.Date)
    valid_until = db.Column(db.Date)
    doc_storage_path = db.Column(db.String(1000))
    verified_at = db.Column(db.DateTime(timezone=True))
    verified_by = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc)

    provider = db.relationship('Provider', back_populates='licenses')

    def is_expired(self):
        from datetime import date
        if self.valid_until is None:
            return False
        return self.valid_until < date.today()

    def days_until_expiry(self):
        from datetime import date
        if self.valid_until is None:
            return None
        return (self.valid_until - date.today()).days


class ProviderService(db.Model):
    __tablename__ = 'provider_services'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    provider_id = db.Column(db.String(36), db.ForeignKey('providers.id'), nullable=False, index=True)
    category = db.Column(db.Enum(ProviderCategory), nullable=False)
    subcategory = db.Column(db.String(255))
    relevant_stages = db.Column(db.JSON)   # list of StageKey values
    price_range_min = db.Column(db.Numeric(10, 2))
    price_range_max = db.Column(db.Numeric(10, 2))
    price_unit = db.Column(db.String(50))   # m², Stunde, Pauschal
    service_area_plz = db.Column(db.JSON)   # list of PLZ codes
    # service_area = db.Column(Geometry('MULTIPOLYGON', srid=4326))  # PostGIS
    description = db.Column(db.Text)

    provider = db.relationship('Provider', back_populates='services')


class ProviderReview(db.Model):
    __tablename__ = 'provider_reviews'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    provider_id = db.Column(db.String(36), db.ForeignKey('providers.id'), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'))
    rating = db.Column(db.SmallInteger, nullable=False)
    title = db.Column(db.String(255))
    text = db.Column(db.Text)
    ai_anomaly_score = db.Column(db.Numeric(4, 3))  # 0.0 = нормальный, 1.0 = подозрительный
    verified_deal = db.Column(db.Boolean, default=False, nullable=False)
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    provider = db.relationship('Provider', back_populates='reviews')
    user = db.relationship('User', back_populates='reviews')
    project = db.relationship('Project', back_populates='reviews')


class Lead(db.Model):
    __tablename__ = 'leads'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False, index=True)
    provider_id = db.Column(db.String(36), db.ForeignKey('providers.id'), nullable=False, index=True)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'), index=True)
    stage_key = db.Column(db.Enum(StageKey))
    status = db.Column(db.Enum(LeadStatus), default=LeadStatus.SENT, nullable=False)
    price_charged = db.Column(db.Numeric(8, 2))
    stripe_charge_id = db.Column(db.String(255))
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    user = db.relationship('User', back_populates='leads')
    provider = db.relationship('Provider', back_populates='leads')
    project = db.relationship('Project', back_populates='leads')


# ─────────────────────────────────────────────────────
# FINANCE DOMAIN
# ─────────────────────────────────────────────────────

class FinancingPlan(db.Model):
    __tablename__ = 'financing_plans'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'),
                            nullable=False, unique=True, index=True)
    eigenkapital = db.Column(db.Numeric(12, 2), default=0)
    kfw_program = db.Column(db.String(100))   # KFW-124, KFW-261, KFW-300…
    kfw_amount = db.Column(db.Numeric(12, 2), default=0)
    kfw_zinssatz = db.Column(db.Numeric(5, 3))
    kfw_laufzeit_years = db.Column(db.SmallInteger)
    kfw_application_date = db.Column(db.Date)
    kfw_status = db.Column(db.String(100))
    bank_name = db.Column(db.String(255))
    bank_loan_amount = db.Column(db.Numeric(12, 2), default=0)
    bank_zinssatz = db.Column(db.Numeric(5, 3))
    bank_sollzinsbindung_years = db.Column(db.SmallInteger)
    bank_tilgung_pct = db.Column(db.Numeric(5, 3))
    laufzeit_years = db.Column(db.SmallInteger)
    landesfoerderung_program = db.Column(db.String(255))
    landesfoerderung_amount = db.Column(db.Numeric(12, 2), default=0)
    monthly_rate = db.Column(db.Numeric(10, 2))
    total_cost = db.Column(db.Numeric(12, 2))
    status = db.Column(db.Enum(FinancingStatus), default=FinancingStatus.DRAFT)
    notes = db.Column(db.Text)
    updated_at = db.Column(db.DateTime(timezone=True), default=now_utc, onupdate=now_utc)

    project = db.relationship('Project', back_populates='financing')

    def total_financing(self):
        total = 0
        for field in [self.eigenkapital, self.kfw_amount,
                      self.bank_loan_amount, self.landesfoerderung_amount]:
            if field:
                total += float(field)
        return total

    def calculate_monthly_rate(self):
        """Упрощённый расчёт аннуитета для банковского кредита"""
        if not self.bank_loan_amount or not self.bank_zinssatz or not self.laufzeit_years:
            return None
        P = float(self.bank_loan_amount)
        r = float(self.bank_zinssatz) / 100 / 12
        n = int(self.laufzeit_years) * 12
        if r == 0:
            return P / n
        rate = P * r * (1 + r) ** n / ((1 + r) ** n - 1)
        return round(rate, 2)


# ─────────────────────────────────────────────────────
# MAILBOX DOMAIN
# ─────────────────────────────────────────────────────

class ProjectMailbox(db.Model):
    """Gmail mailbox connected to a project (IMAP + SMTP via App Password)."""
    __tablename__ = 'project_mailboxes'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    project_id = db.Column(db.String(36), db.ForeignKey('projects.id'),
                            nullable=False, unique=True, index=True)
    gmail_address = db.Column(db.String(255), nullable=False)
    # App password encrypted with Fernet (key derived from SECRET_KEY)
    app_password_enc = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_sync_at = db.Column(db.DateTime(timezone=True))
    email_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    project = db.relationship('Project', backref=db.backref('mailbox', uselist=False))


# ─────────────────────────────────────────────────────
# LAW UPDATE AGENT DOMAIN
# ─────────────────────────────────────────────────────

class LawSource(db.Model):
    """Tracked legal sources — German construction law / KfW programs / Hessen rules."""
    __tablename__ = 'law_sources'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    name = db.Column(db.String(255), nullable=False)         # e.g. "GEG 2024"
    category = db.Column(db.String(100), nullable=False)     # e.g. "bundesrecht", "kfw", "hessen"
    url = db.Column(db.String(1000), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_checked_at = db.Column(db.DateTime(timezone=True))
    last_changed_at = db.Column(db.DateTime(timezone=True))
    last_hash = db.Column(db.String(64))                     # SHA-256 of fetched content
    check_interval_days = db.Column(db.SmallInteger, default=30)
    created_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False)

    logs = db.relationship('LawUpdateLog', back_populates='source',
                           order_by='LawUpdateLog.checked_at.desc()', lazy='dynamic')


class LawUpdateLog(db.Model):
    """Log of each law-check run for a source."""
    __tablename__ = 'law_update_logs'

    id = db.Column(db.String(36), primary_key=True, default=new_uuid)
    source_id = db.Column(db.String(36), db.ForeignKey('law_sources.id'),
                          nullable=False, index=True)
    checked_at = db.Column(db.DateTime(timezone=True), default=now_utc, nullable=False, index=True)
    # 'no_change' | 'changed' | 'error'
    result = db.Column(db.String(20), nullable=False, default='no_change')
    previous_hash = db.Column(db.String(64))
    current_hash = db.Column(db.String(64))
    # AI-generated summary of what changed
    change_summary = db.Column(db.Text)
    # AI-generated suggestion for which STAGE_CONTEXTS need updating
    affected_stages = db.Column(db.JSON)        # list of stage_key strings
    suggested_update = db.Column(db.Text)       # AI-drafted update text for ai_service.py
    # Admin review
    requires_review = db.Column(db.Boolean, default=False, nullable=False)
    reviewed_at = db.Column(db.DateTime(timezone=True))
    reviewed_by = db.Column(db.String(100))     # admin email / "auto"
    review_note = db.Column(db.Text)
    applied = db.Column(db.Boolean, default=False, nullable=False)
    error_message = db.Column(db.Text)

    source = db.relationship('LawSource', back_populates='logs')

