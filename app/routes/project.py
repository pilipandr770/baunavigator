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
    PROJECT_TYPE_LABELS, DOC_TYPE_LABELS
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

    return render_template('project/detail.html',
                           project=project,
                           phases=phases_with_stages,
                           stage_labels=STAGE_LABELS,
                           project_type_labels=PROJECT_TYPE_LABELS,
                           pending_messages=pending_messages)


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

    return render_template('project/stage.html',
                           project=project,
                           stage=stage,
                           stage_label=STAGE_LABELS.get(sk, sk.value),
                           documents=documents,
                           outbox=outbox,
                           doc_types=DocType,
                           doc_type_labels=DOC_TYPE_LABELS)


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
    doc = Document.query.get_or_404(doc_id)
    # Security: verify document belongs to current user
    if doc.project.user_id != current_user.id:
        flash('Zugriff verweigert.', 'danger')
        return redirect(url_for('dashboard.index'))

    if not doc.storage_path or not os.path.exists(doc.storage_path):
        flash('Datei nicht gefunden.', 'danger')
        return redirect(url_for('dashboard.index'))

    return send_file(
        doc.storage_path,
        download_name=doc.original_filename or doc.filename,
        as_attachment=True,
        mimetype=doc.mime_type or 'application/octet-stream',
    )


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

