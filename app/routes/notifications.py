"""
Notifications routes — BauNavigator
"""
from flask import Blueprint, jsonify, render_template, request
from flask_login import login_required, current_user

from app import db
from app.models.models import Notification
from app.services.notification_service import (
    get_notifications, get_unread_count, NOTIFICATION_ICONS
)

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/')
@login_required
def index():
    notifications = get_notifications(current_user.id, limit=50)
    # Mark all as read when page opened
    unread_ids = [n.id for n in notifications if not n.is_read]
    if unread_ids:
        Notification.query.filter(
            Notification.id.in_(unread_ids)
        ).update({'is_read': True}, synchronize_session=False)
        db.session.commit()
    return render_template(
        'notifications/index.html',
        notifications=notifications,
        icons=NOTIFICATION_ICONS,
    )


@notifications_bp.route('/read/<nid>', methods=['POST'])
@login_required
def mark_read(nid):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify({'ok': True})


@notifications_bp.route('/read-all', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True}, synchronize_session=False)
    db.session.commit()
    return jsonify({'ok': True})


@notifications_bp.route('/api/unread-count')
@login_required
def api_unread_count():
    return jsonify({'count': get_unread_count(current_user.id)})


@notifications_bp.route('/api/recent')
@login_required
def api_recent():
    """Returns last 8 notifications as JSON for the dropdown bell."""
    items = get_notifications(current_user.id, limit=8)
    return jsonify([
        {
            'id': n.id,
            'type': n.type.value,
            'icon': NOTIFICATION_ICONS.get(n.type.value, 'ℹ️'),
            'title': n.title,
            'message': n.message or '',
            'link': n.link or '',
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%d.%m.%Y %H:%M'),
        }
        for n in items
    ])
