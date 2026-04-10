from flask import Blueprint, render_template

legal_bp = Blueprint('legal', __name__)


@legal_bp.route('/impressum')
def impressum():
    return render_template('legal/impressum.html')


@legal_bp.route('/agb')
def agb():
    return render_template('legal/agb.html')


@legal_bp.route('/datenschutz')
def datenschutz():
    return render_template('legal/datenschutz.html')
