from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
import os
import uuid
from werkzeug.utils import secure_filename
from app import db
from app.models.models import (
    Project, ProjectStage, Gemeinde, FinancingPlan, Document
)
from app.models.enums import (
    StageKey, StageStatus, ProjectType, DocType,
    STAGE_LABELS, STAGE_PHASES, FinancingStatus,
    PROJECT_TYPE_LABELS, DOC_TYPE_LABELS,
    STAGE_PROVIDER_CATEGORIES, PROVIDER_CATEGORY_LABELS
)
from app.services.agents import (
    onboarding_chat, check_documents_for_stage,
    check_finance_alerts, create_finance_outbox_messages,
    build_stage_sequence,
)
from app.models.models import now_utc

project_bp = Blueprint('project', __name__)

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'docx', 'xlsx', 'doc', 'xls'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _upload_folder():
    from flask import current_app
    folder = os.path.join(current_app.instance_path, 'uploads')
    os.makedirs(folder, exist_ok=True)
    return folder



@project_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    gemeinden = Gemeinde.query.filter_by(land='HE').order_by(Gemeinde.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        project_type = request.form.get('project_type', ProjectType.NEUBAU_EFH.value)
        address = request.form.get('address', '').strip()
        address_plz = request.form.get('address_plz', '').strip()
        address_city = request.form.get('address_city', '').strip()
        gemeinde_id = request.form.get('gemeinde_id') or None
        budget_total = request.form.get('budget_total') or None
        wohnflaeche_m2 = request.form.get('wohnflaeche_m2') or None
        grundstueck_m2 = request.form.get('grundstueck_m2') or None

        if not title:
            flash('Projektname ist Pflichtfeld.', 'danger')
            return render_template('project/new.html', gemeinden=gemeinden,
                                   project_types=ProjectType,
                                   project_type_labels=PROJECT_TYPE_LABELS)

        project = Project(
            user_id=current_user.id,
            title=title,
            project_type=ProjectType(project_type),
            address=address,
            address_plz=address_plz,
            address_city=address_city,
            gemeinde_id=gemeinde_id,
            budget_total=float(budget_total) if budget_total else None,
            wohnflaeche_m2=float(wohnflaeche_m2) if wohnflaeche_m2 else None,
            grundstueck_m2=float(grundstueck_m2) if grundstueck_m2 else None,
            current_stage=StageKey.LAND_SEARCH,
        )
        db.session.add(project)
        db.session.flush()

        # Создаём все этапы как PENDING
        for phase_key, phase in STAGE_PHASES.items():
            for i, stage_key in enumerate(phase['stages']):
                stage = ProjectStage(
                    project_id=project.id,
                    stage_key=stage_key,
                    status=StageStatus.ACTIVE if stage_key == StageKey.LAND_SEARCH
                    else StageStatus.PENDING,
                )
                db.session.add(stage)

        # Создаём пустой план финансирования
        fin = FinancingPlan(
            project_id=project.id,
            status=FinancingStatus.DRAFT,
        )
        db.session.add(fin)
        db.session.commit()

        flash(f'Projekt "{title}" wurde erstellt.', 'success')
        return redirect(url_for('project.detail', project_id=project.id))

    return render_template('project/new.html',
                           gemeinden=gemeinden,
                           project_types=ProjectType,
                           project_type_labels=PROJECT_TYPE_LABELS)


# ─── AI-geführtes Onboarding ──────────────────────────────────────────────────

@project_bp.route('/onboard', methods=['GET'])
@login_required
def onboard():
    """Zeigt die KI-Interview-Seite für neue Projekte."""
    import json as _json
    gemeinden = Gemeinde.query.filter_by(land='HE').order_by(Gemeinde.name).all()
    stage_labels_json = _json.dumps({k.value: v for k, v in STAGE_LABELS.items()})
    return render_template('project/onboarding.html',
                           gemeinden=gemeinden,
                           project_types=ProjectType,
                           project_type_labels=PROJECT_TYPE_LABELS,
                           stage_labels_json=stage_labels_json)


@project_bp.route('/onboard/chat', methods=['POST'])
@login_required
def onboard_chat():
    """AJAX-Endpunkt: verarbeitet einen Chat-Schritt des Onboarding-Agenten."""
    data = request.get_json(silent=True) or {}
    messages = data.get('messages', [])
    if not messages:
        return jsonify({'error': 'Keine Nachrichten'}), 400
    if len(messages) > 30:
        return jsonify({'error': 'Zu viele Nachrichten'}), 400

    # Validate message structure
    for m in messages:
        if not isinstance(m, dict):
            return jsonify({'error': 'Ungültige Nachricht'}), 400
        if m.get('role') not in ('user', 'assistant'):
            return jsonify({'error': 'Ungültige Rolle'}), 400
        content = m.get('content', '')
        if not isinstance(content, str) or len(content) > 2000:
            return jsonify({'error': 'Nachricht zu lang'}), 400

    result = onboarding_chat(messages)
    return jsonify(result)


@project_bp.route('/onboard/confirm', methods=['POST'])
@login_required
def onboard_confirm():
    """Erstellt Projekt aus dem vom KI-Agenten erstellten Profil."""
    import json as _json
    data = request.get_json(silent=True) or {}
    profile = data.get('profile', {})

    if not profile:
        return jsonify({'error': 'Kein Profil'}), 400

    # Title aus Formular oder Vorschlag
    title = (data.get('title') or profile.get('title_suggestion') or '').strip()
    if not title:
        title = 'Mein Bauprojekt'

    seq = build_stage_sequence(profile)
    current_stage = seq['current_stage']
    completed_stages = seq['completed_stages']
    project_type = seq['project_type']

    gemeinde_id = data.get('gemeinde_id') or None
    address_plz = (data.get('address_plz') or profile.get('address_plz') or '').strip()
    address_city = (data.get('address_city') or profile.get('address_city') or '').strip()
    budget_total = data.get('budget_total') or profile.get('budget_total')
    wohnflaeche_m2 = data.get('wohnflaeche_m2') or profile.get('wohnflaeche_m2')
    grundstueck_m2 = data.get('grundstueck_m2') or profile.get('grundstueck_m2')

    project = Project(
        user_id=current_user.id,
        title=title,
        project_type=project_type,
        address_plz=address_plz,
        address_city=address_city,
        gemeinde_id=gemeinde_id,
        budget_total=float(budget_total) if budget_total else None,
        wohnflaeche_m2=float(wohnflaeche_m2) if wohnflaeche_m2 else None,
        grundstueck_m2=float(grundstueck_m2) if grundstueck_m2 else None,
        current_stage=current_stage,
    )
    db.session.add(project)
    db.session.flush()

    # Создаём этапы с правильными статусами
    for phase_key, phase in STAGE_PHASES.items():
        for stage_key in phase['stages']:
            if stage_key in completed_stages:
                status = StageStatus.DONE
            elif stage_key == current_stage:
                status = StageStatus.ACTIVE
            else:
                status = StageStatus.PENDING
            stage = ProjectStage(
                project_id=project.id,
                stage_key=stage_key,
                status=status,
            )
            db.session.add(stage)

    # Пустой план финансирования
    fin = FinancingPlan(
        project_id=project.id,
        status=FinancingStatus.DRAFT,
    )
    db.session.add(fin)
    db.session.commit()

    # Проверяем финансовые дедлайны и создаём уведомления
    try:
        create_finance_outbox_messages(project, current_user)
    except Exception:
        pass

    return jsonify({'redirect': url_for('project.detail', project_id=project.id)})


@project_bp.route('/<project_id>')
@login_required
def detail(project_id):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id, is_active=True
    ).first_or_404()

    # Группируем этапы по фазам
    phases_with_stages = []
    for phase_key, phase in STAGE_PHASES.items():
        stage_rows = []
        for sk in phase['stages']:
            stage = project.stages.filter_by(stage_key=sk).first()
            stage_rows.append({
                'key': sk,
                'label': STAGE_LABELS.get(sk, sk.value),
                'stage': stage,
            })
        phases_with_stages.append({
            'key': phase_key,
            'label': phase['label'],
            'label_ru': phase['label_ru'],
            'color': phase['color'],
            'stages': stage_rows,
        })

    pending_messages = project.outbox_messages.filter_by(
        status='draft'
    ).count()

    # Finance Agent — критические дедлайны
    try:
        finance_alerts = check_finance_alerts(project)
    except Exception:
        finance_alerts = []

    # Document Agent — состояние документов текущего этапа
    try:
        from app.services.agents import check_documents
        doc_status = check_documents(project)
    except Exception:
        doc_status = None

    return render_template('project/detail.html',
                           project=project,
                           phases=phases_with_stages,
                           stage_labels=STAGE_LABELS,
                           project_type_labels=PROJECT_TYPE_LABELS,
                           pending_messages=pending_messages,
                           finance_alerts=finance_alerts,
                           doc_status=doc_status)


@project_bp.route('/<project_id>/print')
@login_required
def print_project(project_id):
    """Printable single-page project summary."""
    from datetime import date as _date
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    phases_with_stages = []
    for phase_key, phase in STAGE_PHASES.items():
        stage_rows = []
        for sk in phase['stages']:
            stage = project.stages.filter_by(stage_key=sk).first()
            stage_rows.append({
                'key': sk,
                'label': STAGE_LABELS.get(sk, sk.value),
                'stage': stage,
            })
        phases_with_stages.append({
            'key': phase_key,
            'label': phase['label'],
            'color': phase['color'],
            'stages': stage_rows,
        })

    return render_template('project/print_summary.html',
                           project=project,
                           phases=phases_with_stages,
                           stage_labels=STAGE_LABELS,
                           project_type_labels=PROJECT_TYPE_LABELS,
                           today=_date.today())


@project_bp.route('/<project_id>/stage/<stage_key>')
@login_required
def stage_detail(project_id, stage_key):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    try:
        sk = StageKey(stage_key)
    except ValueError:
        flash('Unbekannter Schritt.', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    stage = project.stages.filter_by(stage_key=sk).first_or_404()
    documents = stage.documents.all()
    outbox = stage.outbox_messages.all()

    from datetime import date as _date
    # Provider categories for this stage
    raw_cats = STAGE_PROVIDER_CATEGORIES.get(sk, [])
    provider_categories = [
        (cat.value, PROVIDER_CATEGORY_LABELS.get(cat, cat.value))
        for cat in raw_cats
    ]
    # Document checklist from DocumentAgent
    doc_check = check_documents_for_stage(project, sk)

    return render_template('project/stage.html',
                           project=project,
                           stage=stage,
                           stage_label=STAGE_LABELS.get(sk, sk.value),
                           documents=documents,
                           outbox=outbox,
                           doc_types=DocType,
                           doc_type_labels=DOC_TYPE_LABELS,
                           provider_categories=provider_categories,
                           doc_check=doc_check,
                           today=_date.today())


@project_bp.route('/<project_id>/stage/<stage_key>/complete', methods=['POST'])
@login_required
def complete_stage(project_id, stage_key):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    try:
        sk = StageKey(stage_key)
    except ValueError:
        return jsonify({'error': 'Invalid stage'}), 400

    stage = project.stages.filter_by(stage_key=sk).first_or_404()
    stage.complete()

    # Активируем следующий этап
    all_stages = [s for phase in STAGE_PHASES.values() for s in phase['stages']]
    current_idx = all_stages.index(sk) if sk in all_stages else -1
    if current_idx >= 0 and current_idx + 1 < len(all_stages):
        next_key = all_stages[current_idx + 1]
        next_stage = project.stages.filter_by(stage_key=next_key).first()
        if next_stage and next_stage.status == StageStatus.PENDING:
            next_stage.activate()
        project.current_stage = next_key

    db.session.commit()
    flash(f'Schritt "{STAGE_LABELS.get(sk)}" abgeschlossen.', 'success')
    return redirect(url_for('project.detail', project_id=project_id))


@project_bp.route('/<project_id>/financing')
@login_required
def financing(project_id):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    return render_template('project/financing.html', project=project)


@project_bp.route('/<project_id>/financing/save', methods=['POST'])
@login_required
def financing_save(project_id):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    fin = project.financing or FinancingPlan(project_id=project.id)

    def get_num(field):
        v = request.form.get(field, '').strip()
        return float(v) if v else None

    fin.eigenkapital = get_num('eigenkapital')
    fin.kfw_program = request.form.get('kfw_program', '').strip() or None
    fin.kfw_amount = get_num('kfw_amount')
    fin.kfw_zinssatz = get_num('kfw_zinssatz')
    fin.bank_name = request.form.get('bank_name', '').strip() or None
    fin.bank_loan_amount = get_num('bank_loan_amount')
    fin.bank_zinssatz = get_num('bank_zinssatz')
    fin.laufzeit_years = int(request.form.get('laufzeit_years', 0) or 0) or None
    fin.landesfoerderung_amount = get_num('landesfoerderung_amount')

    # Пересчитываем месячный платёж
    fin.monthly_rate = fin.calculate_monthly_rate()

    db.session.add(fin)
    db.session.commit()
    flash('Finanzierungsdaten gespeichert.', 'success')
    return redirect(url_for('project.financing', project_id=project_id))


@project_bp.route('/<project_id>/tilgungsplan')
@login_required
def tilgungsplan(project_id):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    fin = project.financing
    if not fin or not fin.bank_loan_amount or not fin.bank_zinssatz or not fin.laufzeit_years:
        flash('Bitte zuerst Bankdarlehen, Zinssatz und Laufzeit eintragen.', 'warning')
        return redirect(url_for('project.financing', project_id=project_id))

    P = float(fin.bank_loan_amount)
    annual_rate = float(fin.bank_zinssatz) / 100
    r = annual_rate / 12
    n = int(fin.laufzeit_years) * 12

    if r == 0:
        monthly_payment = P / n
    else:
        monthly_payment = P * r * (1 + r) ** n / ((1 + r) ** n - 1)

    rows = []
    balance = P
    total_interest = 0.0
    total_principal = 0.0

    for month in range(1, n + 1):
        interest = balance * r
        principal = monthly_payment - interest
        balance -= principal
        if balance < 0.005:
            balance = 0.0
        total_interest += interest
        total_principal += principal
        rows.append({
            'month': month,
            'year': (month - 1) // 12 + 1,
            'payment': monthly_payment,
            'interest': interest,
            'principal': principal,
            'balance': balance,
        })

    summary = {
        'loan': P,
        'monthly_rate': monthly_payment,
        'total_payment': monthly_payment * n,
        'total_interest': total_interest,
        'total_principal': total_principal,
        'laufzeit_years': int(fin.laufzeit_years),
        'zinssatz': float(fin.bank_zinssatz),
        'bank_name': fin.bank_name or '',
    }

    return render_template('project/tilgungsplan.html',
                           project=project, rows=rows, summary=summary)

@project_bp.route('/<project_id>/stage/<stage_key>/upload', methods=['POST'])
@login_required
def upload_document(project_id, stage_key):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    try:
        sk = StageKey(stage_key)
    except ValueError:
        flash('Ungültiger Schritt.', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    stage = project.stages.filter_by(stage_key=sk).first_or_404()

    file = request.files.get('file')
    if not file or file.filename == '':
        flash('Keine Datei ausgewählt.', 'danger')
        return redirect(url_for('project.stage_detail', project_id=project_id, stage_key=stage_key))

    if not _allowed_file(file.filename):
        flash('Dateityp nicht erlaubt. Erlaubt: PDF, JPG, PNG, DOCX, XLSX.', 'danger')
        return redirect(url_for('project.stage_detail', project_id=project_id, stage_key=stage_key))

    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit('.', 1)[1].lower()
    stored_filename = f"{uuid.uuid4()}.{ext}"
    upload_path = os.path.join(_upload_folder(), stored_filename)
    file.save(upload_path)

    doc_type_val = request.form.get('doc_type', DocType.SONSTIGES.value)
    try:
        doc_type = DocType(doc_type_val)
    except ValueError:
        doc_type = DocType.SONSTIGES

    description = request.form.get('description', '').strip() or None
    size = os.path.getsize(upload_path)
    mime = file.mimetype or 'application/octet-stream'

    doc = Document(
        project_id=project.id,
        stage_id=stage.id,
        doc_type=doc_type,
        filename=stored_filename,
        original_filename=original_filename,
        storage_path=upload_path,
        mime_type=mime,
        size_bytes=size,
        description=description,
        generated_by_ai=False,
    )
    db.session.add(doc)
    db.session.commit()
    flash(f'Dokument „{original_filename}" hochgeladen.', 'success')
    return redirect(url_for('project.stage_detail', project_id=project_id, stage_key=stage_key))


@project_bp.route('/document/<doc_id>/download')
@login_required
def download_document(doc_id):
    from io import BytesIO
    doc = Document.query.get_or_404(doc_id)
    if doc.project.user_id != current_user.id:
        flash('Zugriff verweigert.', 'danger')
        return redirect(url_for('dashboard.index'))

    # AI-generated text draft — serve as .txt
    if doc.generated_by_ai and doc.ai_draft_content:
        content_bytes = doc.ai_draft_content.encode('utf-8')
        return send_file(
            BytesIO(content_bytes),
            download_name=doc.original_filename or doc.filename,
            as_attachment=True,
            mimetype='text/plain; charset=utf-8',
        )

    if not doc.storage_path or not os.path.exists(doc.storage_path):
        flash('Datei nicht gefunden.', 'danger')
        return redirect(url_for('dashboard.index'))

    return send_file(
        doc.storage_path,
        download_name=doc.original_filename or doc.filename,
        as_attachment=True,
        mimetype=doc.mime_type or 'application/octet-stream',
    )


@project_bp.route('/document/<doc_id>/view')
@login_required
def view_ai_document(doc_id):
    """Inline viewer for AI-generated text documents."""
    doc = Document.query.get_or_404(doc_id)
    if doc.project.user_id != current_user.id:
        flash('Zugriff verweigert.', 'danger')
        return redirect(url_for('dashboard.index'))
    if not doc.generated_by_ai or not doc.ai_draft_content:
        flash('Kein KI-Entwurf vorhanden.', 'warning')
        return redirect(url_for('project.stage_detail',
                                project_id=doc.project_id,
                                stage_key=doc.stage.stage_key.value if doc.stage else ''))
    return render_template('project/view_ai_doc.html', doc=doc)


@project_bp.route('/<project_id>/stage/<stage_key>/checklist/<int:item_index>', methods=['POST'])
@login_required
def toggle_checklist(project_id, stage_key, item_index):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    try:
        sk = StageKey(stage_key)
    except ValueError:
        return jsonify({'error': 'Ungültiger Schritt'}), 400

    stage = project.stages.filter_by(stage_key=sk).first_or_404()

    checklist = stage.checklist or []
    if item_index < 0 or item_index >= len(checklist):
        return jsonify({'error': 'Ungültiger Index'}), 400

    data = request.get_json() or {}
    checklist[item_index]['done'] = bool(data.get('done', False))

    # Force SQLAlchemy to detect JSON mutation
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(stage, 'checklist')
    stage.checklist = checklist
    db.session.commit()
    return jsonify({'ok': True})


@project_bp.route('/<project_id>/archive', methods=['POST'])
@login_required
def archive(project_id):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    project.is_active = False
    db.session.commit()
    flash('Projekt wurde archiviert.', 'info')
    return redirect(url_for('dashboard.index'))


@project_bp.route('/<project_id>/stage/<stage_key>/notes', methods=['POST'])
@login_required
def save_notes(project_id, stage_key):
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id, is_active=True
    ).first_or_404()
    try:
        sk = StageKey(stage_key)
    except ValueError:
        flash('Ungültiger Schritt.', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    stage = project.stages.filter_by(stage_key=sk).first()
    if not stage:
        flash('Schritt nicht gefunden.', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    stage.notes = request.form.get('notes', '').strip() or None
    db.session.commit()
    flash('Notizen gespeichert.', 'success')
    return redirect(url_for('project.stage_detail', project_id=project_id, stage_key=stage_key))


@project_bp.route('/<project_id>/stage/<stage_key>/deadline', methods=['POST'])
@login_required
def save_deadline(project_id, stage_key):
    from datetime import date as _date
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id, is_active=True
    ).first_or_404()
    try:
        sk = StageKey(stage_key)
    except ValueError:
        flash('Ungültiger Schritt.', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    stage = project.stages.filter_by(stage_key=sk).first()
    if not stage:
        flash('Schritt nicht gefunden.', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    raw = request.form.get('deadline_at', '').strip()
    if raw:
        try:
            stage.deadline_at = _date.fromisoformat(raw)
            flash('Frist gespeichert.', 'success')
        except ValueError:
            flash('Ungültiges Datum.', 'danger')
    else:
        stage.deadline_at = None
        flash('Frist entfernt.', 'info')

    db.session.commit()
    return redirect(url_for('project.stage_detail', project_id=project_id, stage_key=stage_key))


# ─── Gmail Mailbox ─────────────────────────────────────────────────────────────

@project_bp.route('/<project_id>/mailbox/save', methods=['POST'])
@login_required
def mailbox_save(project_id):
    """Save or update Gmail credentials for a project."""
    from app.models.models import ProjectMailbox
    from app.services.gmail_service import encrypt_password, test_connection

    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    gmail = request.form.get('gmail_address', '').strip().lower()
    app_pwd = request.form.get('app_password', '').strip().replace(' ', '')

    if not gmail or '@' not in gmail:
        flash('Ungültige Gmail-Adresse.', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    if not app_pwd or len(app_pwd) != 16:
        flash('App-Passwort muss genau 16 Zeichen haben (Leerzeichen werden ignoriert).', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    # Test connection before saving
    result = test_connection(gmail, app_pwd)
    if not result['success']:
        flash(f'Verbindung fehlgeschlagen: {result["error"]}', 'danger')
        return redirect(url_for('project.detail', project_id=project_id))

    enc_pwd = encrypt_password(app_pwd)

    mailbox = project.mailbox
    if mailbox:
        mailbox.gmail_address = gmail
        mailbox.app_password_enc = enc_pwd
        mailbox.is_active = True
    else:
        mailbox = ProjectMailbox(
            project_id=project.id,
            gmail_address=gmail,
            app_password_enc=enc_pwd,
        )
        db.session.add(mailbox)

    db.session.commit()
    flash(f'Gmail {gmail} erfolgreich verbunden! ✓', 'success')
    return redirect(url_for('project.detail', project_id=project_id))


@project_bp.route('/<project_id>/mailbox/disconnect', methods=['POST'])
@login_required
def mailbox_disconnect(project_id):
    """Deactivate mailbox connection."""
    from app.models.models import ProjectMailbox
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    if project.mailbox:
        project.mailbox.is_active = False
        db.session.commit()
        flash('E-Mail-Verbindung getrennt.', 'info')
    return redirect(url_for('project.detail', project_id=project_id))


@project_bp.route('/<project_id>/mailbox/inbox')
@login_required
def mailbox_inbox(project_id):
    """AJAX: fetch inbox from Gmail."""
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    if not project.mailbox or not project.mailbox.is_active:
        return jsonify({'success': False, 'error': 'Kein Gmail-Konto verbunden.'})

    from app.services.gmail_service import fetch_inbox
    limit = min(int(request.args.get('limit', 30)), 50)
    result = fetch_inbox(project.mailbox, limit=limit)
    return jsonify(result)


@project_bp.route('/<project_id>/mailbox/attachments/<uid>')
@login_required
def mailbox_fetch_attachments(project_id, uid):
    """AJAX: list attachment filenames for an email."""
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    if not project.mailbox or not project.mailbox.is_active:
        return jsonify({'success': False, 'error': 'Nicht verbunden.'})

    from app.services.gmail_service import fetch_email_attachments
    result = fetch_email_attachments(project.mailbox, uid)
    # Return only metadata (no raw bytes)
    attachments_meta = [
        {'filename': a['filename'], 'content_type': a['content_type'], 'size': len(a['data'])}
        for a in result.get('attachments', [])
    ]
    return jsonify({'success': result['success'], 'attachments': attachments_meta,
                    'error': result.get('error')})


@project_bp.route('/<project_id>/mailbox/save-attachment', methods=['POST'])
@login_required
def mailbox_save_attachment(project_id):
    """
    Download attachment from an email and save it as a Document in the project.
    Body JSON: {uid, filename, stage_key (optional)}
    """
    import io
    from app.services.gmail_service import fetch_email_attachments

    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    if not project.mailbox or not project.mailbox.is_active:
        return jsonify({'success': False, 'error': 'Nicht verbunden.'})

    data = request.get_json() or {}
    uid = data.get('uid', '')
    target_filename = data.get('filename', '')
    stage_key_str = data.get('stage_key', '')

    if not uid or not target_filename:
        return jsonify({'success': False, 'error': 'uid und filename erforderlich.'})

    result = fetch_email_attachments(project.mailbox, uid)
    if not result['success']:
        return jsonify({'success': False, 'error': result['error']})

    # Find the matching attachment by filename
    attachment = next(
        (a for a in result['attachments'] if a['filename'] == target_filename),
        None
    )
    if not attachment:
        return jsonify({'success': False, 'error': 'Anhang nicht gefunden.'})

    # Determine stage
    stage_id = None
    if stage_key_str:
        try:
            sk = StageKey(stage_key_str)
            stage_obj = project.stages.filter_by(stage_key=sk).first()
            if stage_obj:
                stage_id = stage_obj.id
        except ValueError:
            pass

    # Save file to upload directory
    upload_dir = os.path.join('uploads', project.id)
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(target_filename)[1].lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(upload_dir, stored_name)

    with open(file_path, 'wb') as f:
        f.write(attachment['data'])

    doc = Document(
        project_id=project.id,
        stage_id=stage_id,
        doc_type=DocType.SONSTIGES,
        filename=stored_name,
        original_filename=target_filename,
        storage_path=file_path,
        mime_type=attachment['content_type'],
        size_bytes=len(attachment['data']),
        generated_by_ai=False,
        description='Via E-Mail importiert',
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({'success': True, 'doc_id': doc.id, 'filename': target_filename})


@project_bp.route('/<project_id>/mailbox/send', methods=['POST'])
@login_required
def mailbox_send(project_id):
    """Send an email via project Gmail mailbox."""
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    if not project.mailbox or not project.mailbox.is_active:
        return jsonify({'success': False, 'error': 'Kein Gmail-Konto verbunden.'})

    data = request.get_json() or {}
    to_email = data.get('to', '').strip()
    subject  = data.get('subject', '').strip()
    body     = data.get('body', '').strip()

    if not to_email or not subject or not body:
        return jsonify({'success': False, 'error': 'Empfänger, Betreff und Nachricht erforderlich.'})

    from app.services.gmail_service import send_via_mailbox
    result = send_via_mailbox(
        mailbox=project.mailbox,
        to_email=to_email,
        subject=subject,
        body=body,
        reply_to=project.mailbox.gmail_address,
    )
    return jsonify(result)


# ─────────────────────────────────────────────────────
# CAMERA ROUTES
# ─────────────────────────────────────────────────────

@project_bp.route('/<project_id>/cameras')
@login_required
def cameras(project_id):
    """Camera management + snapshot gallery for a project."""
    from app.models.models import CameraFeed, CameraSnapshot
    from app.models.enums import CameraFeedType, STAGE_LABELS

    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    feeds = CameraFeed.query.filter_by(project_id=project_id).order_by(
        CameraFeed.created_at.desc()
    ).all()

    # Last 20 snapshots across all cameras
    recent_snaps = (
        CameraSnapshot.query.filter_by(project_id=project_id)
        .order_by(CameraSnapshot.captured_at.desc())
        .limit(20)
        .all()
    )

    return render_template(
        'project/cameras.html',
        project=project,
        feeds=feeds,
        recent_snaps=recent_snaps,
        CameraFeedType=CameraFeedType,
        STAGE_LABELS=STAGE_LABELS,
        stage_labels=STAGE_LABELS,
    )


@project_bp.route('/<project_id>/cameras/add', methods=['POST'])
@login_required
def camera_add(project_id):
    """Add a new camera feed (RTSP or Telegram)."""
    from app.models.models import CameraFeed
    from app.models.enums import CameraFeedType

    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()

    feed_type_str = request.form.get('feed_type', 'rtsp')
    name          = request.form.get('name', '').strip()
    rtsp_url      = request.form.get('rtsp_url', '').strip()
    interval      = int(request.form.get('interval', 60))

    if not name:
        flash('Kameraname ist erforderlich.', 'error')
        return redirect(url_for('project.cameras', project_id=project_id))

    try:
        feed_type = CameraFeedType(feed_type_str)
    except ValueError:
        feed_type = CameraFeedType.RTSP

    cam = CameraFeed(
        project_id=project_id,
        name=name,
        feed_type=feed_type,
        rtsp_url=rtsp_url or None,
        is_active=True,
        check_interval_minutes=interval,
    )
    db.session.add(cam)
    db.session.commit()

    flash(f'Kamera "{name}" hinzugefügt.', 'success')
    return redirect(url_for('project.cameras', project_id=project_id))


@project_bp.route('/<project_id>/cameras/<camera_id>/delete', methods=['POST'])
@login_required
def camera_delete(project_id, camera_id):
    from app.models.models import CameraFeed
    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    cam = CameraFeed.query.filter_by(id=camera_id, project_id=project_id).first_or_404()
    db.session.delete(cam)
    db.session.commit()
    flash('Kamera entfernt.', 'info')
    return redirect(url_for('project.cameras', project_id=project_id))


@project_bp.route('/<project_id>/cameras/<camera_id>/snapshot', methods=['POST'])
@login_required
def camera_snapshot_now(project_id, camera_id):
    """Trigger an immediate RTSP snapshot."""
    from app.models.models import CameraFeed
    from app.services.camera_service import process_camera_snapshot

    project = Project.query.filter_by(
        id=project_id, user_id=current_user.id
    ).first_or_404()
    cam = CameraFeed.query.filter_by(id=camera_id, project_id=project_id).first_or_404()

    if not cam.rtsp_url:
        flash('Keine RTSP-URL konfiguriert.', 'error')
        return redirect(url_for('project.cameras', project_id=project_id))

    snap = process_camera_snapshot(cam, project)
    if snap:
        flash(f'Snapshot gespeichert. Fortschritt: {snap.ai_progress_pct or "?"}%', 'success')
    else:
        flash('Snapshot fehlgeschlagen. Kamera-Verbindung prüfen.', 'error')
    return redirect(url_for('project.cameras', project_id=project_id))
