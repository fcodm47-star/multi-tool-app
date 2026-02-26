from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from functools import wraps
from database import db
from models import User, AttackLog, Announcement, Setting
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Access denied', 'error')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    # Stats
    total_users = User.query.count()
    pending_users = User.query.filter_by(is_approved=False, is_admin=False).count()
    total_attacks = AttackLog.query.count()
    total_messages = db.session.query(db.func.sum(AttackLog.messages_sent)).scalar() or 0
    
    # Recent users
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # Recent attacks
    recent_attacks = AttackLog.query.order_by(AttackLog.created_at.desc()).limit(10).all()
    
    # Chart data for last 7 days
    dates = [(datetime.utcnow() - timedelta(days=i)).date() for i in range(6, -1, -1)]
    attack_counts = []
    user_counts = []
    
    for date in dates:
        attack_count = AttackLog.query.filter(
            db.func.date(AttackLog.created_at) == date
        ).count()
        attack_counts.append(attack_count)
        
        user_count = User.query.filter(
            db.func.date(User.created_at) == date
        ).count()
        user_counts.append(user_count)
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         pending_users=pending_users,
                         total_attacks=total_attacks,
                         total_messages=total_messages,
                         recent_users=recent_users,
                         recent_attacks=recent_attacks,
                         dates=[d.strftime('%Y-%m-%d') for d in dates],
                         attack_counts=attack_counts,
                         user_counts=user_counts)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    users_query = User.query.order_by(User.created_at.desc())
    pagination = users_query.paginate(page=page, per_page=per_page)
    users = pagination.items
    
    return render_template('admin/users.html',
                         users=users,
                         pagination=pagination)

@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_approved = True
    db.session.commit()
    
    flash(f'User {user.username} has been approved', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.is_admin:
        flash('Cannot delete admin user', 'error')
        return redirect(url_for('admin.users'))
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {user.username} has been deleted', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/announcements')
@login_required
@admin_required
def announcements():
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin/announcements.html', announcements=announcements)

@admin_bp.route('/announcements/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_announcement():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        priority = request.form.get('priority', 0, type=int)
        expires_days = request.form.get('expires_days', type=int)
        
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        announcement = Announcement(
            title=title,
            content=content,
            author_id=current_user.id,
            priority=priority,
            expires_at=expires_at,
            created_at=datetime.utcnow()
        )
        
        db.session.add(announcement)
        db.session.commit()
        
        flash('Announcement created successfully', 'success')
        return redirect(url_for('admin.announcements'))
    
    return render_template('admin/create_announcement.html')

@admin_bp.route('/announcements/<int:announcement_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    
    if request.method == 'POST':
        announcement.title = request.form.get('title')
        announcement.content = request.form.get('content')
        announcement.priority = request.form.get('priority', 0, type=int)
        announcement.is_active = 'is_active' in request.form
        
        expires_days = request.form.get('expires_days', type=int)
        if expires_days:
            announcement.expires_at = datetime.utcnow() + timedelta(days=expires_days)
        else:
            announcement.expires_at = None
        
        db.session.commit()
        
        flash('Announcement updated successfully', 'success')
        return redirect(url_for('admin.announcements'))
    
    return render_template('admin/edit_announcement.html', announcement=announcement)

@admin_bp.route('/announcements/<int:announcement_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement)
    db.session.commit()
    
    flash('Announcement deleted successfully', 'success')
    return redirect(url_for('admin.announcements'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    if request.method == 'POST':
        # Update settings
        settings_to_update = [
            ('max_attacks_per_day', request.form.get('max_attacks_per_day', 5, type=int)),
            ('max_messages_per_attack', request.form.get('max_messages_per_attack', 500, type=int)),
            ('rate_limit_enabled', 'rate_limit_enabled' in request.form),
            ('announcement_cache_time', request.form.get('announcement_cache_time', 300, type=int))
        ]
        
        for key, value in settings_to_update:
            setting = Setting.query.filter_by(key=key).first()
            if not setting:
                setting = Setting(key=key, value=str(value))
                db.session.add(setting)
            else:
                setting.value = str(value)
        
        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
    
    # Get current settings
    settings_dict = {}
    for setting in Setting.query.all():
        settings_dict[setting.key] = setting.value
    
    return render_template('admin/settings.html', settings=settings_dict)

@admin_bp.route('/api/announcements/active')
def get_active_announcements():
    announcements = Announcement.query.filter_by(is_active=True)\
        .order_by(Announcement.priority.desc(), Announcement.created_at.desc())\
        .limit(5).all()
    
    result = []
    for a in announcements:
        if not a.is_expired():
            result.append({
                'id': a.id,
                'title': a.title,
                'content': a.content,
                'priority': a.priority,
                'author': a.author.username,
                'created_at': a.created_at.strftime('%Y-%m-%d %H:%M')
            })
    
    return jsonify(result)
    
@admin_bp.route('/announcements/<int:announcement_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    announcement.is_active = not announcement.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': announcement.is_active})

@admin_bp.route('/api/user/<int:user_id>')
@login_required
@admin_required
def get_user_details(user_id):
    user = User.query.get_or_404(user_id)
    
    # Get recent attacks
    recent_attacks = AttackLog.query.filter_by(user_id=user.id)\
        .order_by(AttackLog.created_at.desc()).limit(5).all()
    
    attacks_data = []
    for attack in recent_attacks:
        attacks_data.append({
            'type': attack.attack_type,
            'target': attack.target,
            'messages': attack.messages_sent,
            'date': attack.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'is_admin': user.is_admin,
        'is_approved': user.is_approved,
        'created_at': user.created_at.strftime('%Y-%m-%d %H:%M'),
        'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
        'total_attacks': user.total_attacks,
        'total_messages': user.total_messages,
        'recent_attacks': attacks_data
    })          
    
@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@admin_required
def settings():
    if request.method == 'POST':
        # Update settings
        settings_to_update = [
            ('max_attacks_per_day', request.form.get('max_attacks_per_day', 5, type=int)),
            ('max_messages_per_attack', request.form.get('max_messages_per_attack', 500, type=int)),
            ('rate_limit_enabled', 'rate_limit_enabled' in request.form),
            ('announcement_cache_time', request.form.get('announcement_cache_time', 300, type=int))
        ]
        
        for key, value in settings_to_update:
            setting = Setting.query.filter_by(key=key).first()
            if not setting:
                setting = Setting(key=key, value=str(value))
                db.session.add(setting)
            else:
                setting.value = str(value)
        
        db.session.commit()
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
    
    # Get current settings
    settings_dict = {}
    for setting in Setting.query.all():
        settings_dict[setting.key] = setting.value
    
    # Get stats for display
    total_users = User.query.count()
    total_attacks = AttackLog.query.count()
    
    return render_template('admin/settings.html', 
                         settings=settings_dict,
                         stats={
                             'total_users': total_users,
                             'total_attacks': total_attacks
                         })
                         
@admin_bp.route('/api/clear-logs', methods=['POST'])
@login_required
@admin_required
def clear_logs():
    try:
        num_deleted = AttackLog.query.delete()
        db.session.commit()
        return jsonify({'success': True, 'deleted': num_deleted})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500                         