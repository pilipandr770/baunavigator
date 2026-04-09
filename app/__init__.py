from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
mail = Mail()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)

    # ── Config ────────────────────────────────────────
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-change-me')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', '').replace(
        'postgres://', 'postgresql://'  # Render.com fix
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db_schema = os.getenv('DB_SCHEMA', 'public')
    app.config['DB_SCHEMA'] = db_schema
    engine_options = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    if db_schema != 'public':
        # Set search_path to ONLY our schema so alembic/SQLAlchemy never sees
        # other projects' tables in the shared public schema
        engine_options['connect_args'] = {'options': f'-csearch_path={db_schema}'}
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options

    # Mail
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@baunavigator.de')

    # App settings
    app.config['APP_NAME'] = os.getenv('APP_NAME', 'BauNavigator')
    app.config['ANTHROPIC_API_KEY'] = os.getenv('ANTHROPIC_API_KEY')
    app.config['STRIPE_SECRET_KEY'] = os.getenv('STRIPE_SECRET_KEY')
    app.config['STRIPE_WEBHOOK_SECRET'] = os.getenv('STRIPE_WEBHOOK_SECRET')

    # ── Extensions ────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Auto-create the PostgreSQL schema if it doesn't exist yet
    db_schema = os.getenv('DB_SCHEMA', 'public')
    if db_schema != 'public':
        with app.app_context():
            from sqlalchemy import text
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{db_schema}"'))
                    conn.commit()
            except Exception:
                pass  # DB not reachable yet (e.g. no env at build time)
    mail.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Bitte melden Sie sich an.'
    login_manager.login_message_category = 'info'

    # ── Blueprints ────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.project import project_bp
    from app.routes.map import map_bp
    from app.routes.providers import providers_bp
    from app.routes.ai import ai_bp
    from app.routes.outbox import outbox_bp
    from app.routes.webhooks import webhooks_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(project_bp, url_prefix='/project')
    app.register_blueprint(map_bp, url_prefix='/map')
    app.register_blueprint(providers_bp, url_prefix='/providers')
    app.register_blueprint(ai_bp, url_prefix='/ai')
    app.register_blueprint(outbox_bp, url_prefix='/outbox')
    app.register_blueprint(webhooks_bp, url_prefix='/webhooks')

    # ── Shell context ─────────────────────────────────
    @app.shell_context_processor
    def make_shell_context():
        from app import models  # noqa
        return {'db': db, 'models': models}

    # ── Template globals ──────────────────────────────
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        from app.models.enums import StageKey, ActionMode, OutboxStatus

        pending_count = 0
        if current_user.is_authenticated:
            from app.models.models import MessageOutbox, Project
            pending_count = (
                MessageOutbox.query
                .join(Project)
                .filter(
                    Project.user_id == current_user.id,
                    MessageOutbox.status.in_([
                        OutboxStatus.DRAFT,
                        OutboxStatus.AWAITING_APPROVAL,
                    ])
                )
                .count()
            )

        return {
            'app_name': app.config['APP_NAME'],
            'StageKey': StageKey,
            'ActionMode': ActionMode,
            'nav_pending_outbox': pending_count,
        }

    from app.models.enums import StageKey, ActionMode

    return app
