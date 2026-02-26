from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from database import db
from models import AttackLog
from ngl import NGLWrapper
import threading
import time
import random
import json
from datetime import datetime
import os

ngl_bp = Blueprint('ngl', __name__, url_prefix='/ngl')
n = NGLWrapper()

# Load quotes from random.json
def load_quotes():
    quotes = []
    try:
        json_path = os.path.join(os.path.dirname(__file__), 'random.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            for item in data:
                if isinstance(item, dict) and 'quote' in item:
                    quotes.append(item['quote'])
        print(f"✅ Loaded {len(quotes)} quotes for NGL spammer")
    except FileNotFoundError:
        print("⚠️ random.json not found, using fallback quotes")
        quotes = [
            "You have brains in your head. You have feet in your shoes. - Dr. Seuss",
            "Get busy living or get busy dying. - Stephen King",
            "The only limit to our realization of tomorrow is our doubts of today.",
            "Winter is Coming",
            "Do or do not. There is no try. - Yoda"
        ]
    except Exception as e:
        print(f"❌ Error loading quotes: {e}")
        quotes = ["Default quote 1", "Default quote 2", "Default quote 3"]
    return quotes

QUOTES = load_quotes()

# Progress tracking
progress = {
    'running': False,
    'current': 0,
    'total': 0,
    'username': '',
    'status': ''
}

@ngl_bp.route('/')
@login_required
def index():
    return render_template('ngl_spammer.html')

@ngl_bp.route('/api/start', methods=['POST'])
@login_required
def start_spam():
    global progress
    
    if progress['running']:
        return jsonify({'success': False, 'error': 'Spam already in progress'})
    
    data = request.json
    username = data.get('username', '').strip().replace('@', '')
    mode = data.get('mode', '1')
    count = int(data.get('count', 10))
    delay = float(data.get('delay', 0.5))
    custom_message = data.get('message', '')
    
    # Validate
    if not username:
        return jsonify({'success': False, 'error': 'Username required'})
    
    if count < 1 or count > 500:
        return jsonify({'success': False, 'error': 'Count must be 1-500'})
    
    if delay < 0.1 or delay > 5:
        return jsonify({'success': False, 'error': 'Delay must be 0.1-5 seconds'})
    
    if mode == '2' and not custom_message:
        return jsonify({'success': False, 'error': 'Custom message required'})
    
    if mode == '2' and len(custom_message) > 1000:
        return jsonify({'success': False, 'error': 'Message too long (max 1000 chars)'})
    
    # Create attack log
    attack_log = AttackLog(
        user_id=current_user.id,
        attack_type='ngl',
        target=username,
        created_at=datetime.utcnow()
    )
    db.session.add(attack_log)
    db.session.commit()
    
    progress = {
        'running': True,
        'current': 0,
        'total': count,
        'username': username,
        'status': 'Starting...',
        'log_id': attack_log.id
    }
    
    # Start thread
    thread = threading.Thread(target=run_spam, args=(username, mode, count, delay, custom_message, attack_log.id))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Spam started'})

def run_spam(username, mode, count, delay, custom_message, log_id):
    global progress
    
    n.set_username(username)
    successful = 0
    
    for i in range(count):
        if not progress['running']:
            progress['status'] = 'Stopped by user'
            break
        
        try:
            if mode == '1':
                # Random quote
                if QUOTES:
                    quote = random.choice(QUOTES)
                    if len(quote) > 300:
                        quote = quote[:297] + '...'
                    message = quote
                else:
                    message = f"Message {i+1} from NGL Spammer"
            else:
                message = custom_message
            
            success = n.send_question(message)
            
            if success:
                successful += 1
                progress['status'] = f"✓ Sent {i+1}/{count}"
            else:
                progress['status'] = f"✗ Failed {i+1}/{count}"
            
            progress['current'] = i + 1
            
        except Exception as e:
            progress['status'] = f"Error: {str(e)[:50]}"
        
        time.sleep(delay)
    
    # Update attack log
    attack_log = AttackLog.query.get(log_id)
    if attack_log:
        attack_log.messages_sent = successful
        attack_log.completed_at = datetime.utcnow()
        attack_log.status = 'completed' if successful > 0 else 'failed'
        db.session.commit()
    
    # Update user stats
    current_user.total_attacks += 1
    current_user.total_messages += successful
    db.session.commit()
    
    progress['running'] = False
    progress['status'] = f"Completed: {successful}/{count} sent"

@ngl_bp.route('/api/progress')
@login_required
def get_progress():
    return jsonify(progress)

@ngl_bp.route('/api/stop', methods=['POST'])
@login_required
def stop_spam():
    global progress
    progress['running'] = False
    return jsonify({'success': True})

@ngl_bp.route('/api/quotes/count')
@login_required
def quotes_count():
    return jsonify({'count': len(QUOTES)})

@ngl_bp.route('/api/quotes/random')
@login_required
def random_quote():
    if QUOTES:
        quote = random.choice(QUOTES)
        return jsonify({'quote': quote[:200] + '...' if len(quote) > 200 else quote})
    return jsonify({'quote': 'No quotes loaded'})

@ngl_bp.route('/api/history')
@login_required
def get_history():
    attacks = AttackLog.query.filter_by(
        user_id=current_user.id,
        attack_type='ngl'
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