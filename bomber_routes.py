from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from database import db
from models import AttackLog
from datetime import datetime
import re

# Import the controller getter function instead of the controller directly
from controller_instance import get_controller

bomber_bp = Blueprint('bomber', __name__, url_prefix='/bomber')

@bomber_bp.route('/')
@login_required
def index():
    return render_template('sms_bomber.html')

@bomber_bp.route('/api/start', methods=['POST'])
@login_required
def start_attack():
    data = request.json
    phone = data.get('phone', '')
    batches = int(data.get('batches', 1))
    
    # Check daily limit
    today = datetime.utcnow().date()
    attacks_today = AttackLog.query.filter(
        AttackLog.user_id == current_user.id,
        AttackLog.attack_type == 'sms',
        db.func.date(AttackLog.created_at) == today
    ).count()
    
    if attacks_today >= 5:
        return jsonify({'success': False, 'error': 'Daily limit reached (5 attacks)'})
    
    # Validate phone
    clean_phone = phone.replace(' ', '').replace('-', '').replace('+', '')
    if clean_phone.startswith('0'):
        clean_phone = clean_phone[1:]
    elif clean_phone.startswith('63'):
        clean_phone = clean_phone[2:]
    
    if not re.match(r'^9\d{9}$', clean_phone):
        return jsonify({'success': False, 'error': 'Invalid Philippine number format'})
    
    if batches < 1 or batches > 100:
        return jsonify({'success': False, 'error': 'Batches must be 1-100'})
    
    # Create attack log
    attack_log = AttackLog(
        user_id=current_user.id,
        attack_type='sms',
        target=phone,
        created_at=datetime.utcnow()
    )
    db.session.add(attack_log)
    db.session.commit()
    
    # Get controller and use it
    controller = get_controller()
    if controller is None:
        return jsonify({'success': False, 'error': 'Controller not initialized'}), 500
        
    success, message = controller.start_attack(phone, batches)
    
    return jsonify({'success': success, 'message': message})

@bomber_bp.route('/api/status')
@login_required
def get_status():
    controller = get_controller()
    if controller is None:
        return jsonify({'error': 'Controller not initialized'}), 500
        
    status = controller.get_status()
    
    # Get today's attack count
    today = datetime.utcnow().date()
    attacks_today = AttackLog.query.filter(
        AttackLog.user_id == current_user.id,
        AttackLog.attack_type == 'sms',
        db.func.date(AttackLog.created_at) == today
    ).count()
    
    status['user'] = {
        'attacks_today': attacks_today
    }
    
    return jsonify(status)

@bomber_bp.route('/api/stop', methods=['POST'])
@login_required
def stop_attack():
    controller = get_controller()
    if controller is None:
        return jsonify({'success': False, 'error': 'Controller not initialized'}), 500
        
    controller.is_running = False
    return jsonify({'success': True})

@bomber_bp.route('/api/history')
@login_required
def get_history():
    attacks = AttackLog.query.filter_by(
        user_id=current_user.id,
        attack_type='sms'
    ).order_by(AttackLog.created_at.desc()).limit(20).all()
    
    result = []
    for attack in attacks:
        result.append({
            'id': attack.id,
            'target': attack.target,
            'messages': attack.messages_sent,
            'status': attack.status,
            'date': attack.created_at.strftime('%Y-%m-%d %H:%M')
        })
    
    return jsonify(result)