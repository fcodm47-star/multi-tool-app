from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
from flask_login import LoginManager, current_user, login_required
from flask_bcrypt import Bcrypt
from config import Config
from database import db, init_db
from models import User, Announcement, AttackLog
import os
import sys
import platform
from functools import wraps

# Initialize extensions
socketio = SocketIO()
bcrypt = Bcrypt()
login_manager = LoginManager()

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    
    # Login manager settings
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Create tables
    with app.app_context():
        db.create_all()
        
        # Create admin if not exists
        admin = User.query.filter_by(username=app.config['ADMIN_USERNAME']).first()
        if not admin:
            admin = User(
                username=app.config['ADMIN_USERNAME'],
                email=app.config['ADMIN_EMAIL'],
                password=bcrypt.generate_password_hash(app.config['ADMIN_PASSWORD']).decode('utf-8'),
                is_admin=True,
                is_approved=True
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created")
    
    # Register blueprints
    from auth_routes import auth_bp
    from admin_routes import admin_bp
    from ngl_routes import ngl_bp
    from bomber_routes import bomber_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp)
    app.register_blueprint(ngl_bp)
    app.register_blueprint(bomber_bp)
    
    # Main routes
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/dashboard')
    @login_required
    def dashboard():
        return render_template('dashboard.html')
    
    @app.route('/admin/api/stats')
    @login_required
    @admin_required
    def admin_stats():
        total_users = User.query.count()
        total_attacks = AttackLog.query.count()
        total_messages = db.session.query(db.func.sum(AttackLog.messages_sent)).scalar() or 0
        
        return jsonify({
            'total_users': total_users,
            'total_attacks': total_attacks,
            'total_messages': total_messages
        })

    @app.route('/api/recent-activity')
    @login_required
    def recent_activity():
        attacks = AttackLog.query.filter_by(user_id=current_user.id)\
            .order_by(AttackLog.created_at.desc()).limit(10).all()
        
        result = []
        for attack in attacks:
            result.append({
                'id': attack.id,
                'type': attack.attack_type,
                'target': attack.target,
                'messages': attack.messages_sent,
                'status': attack.status,
                'date': attack.created_at.strftime('%Y-%m-%d %H:%M')
            })
        
        return jsonify(result)
    
    @app.context_processor
    def inject_announcements():
        if login_manager._login_disabled:
            return {'announcements': []}
        
        from sqlalchemy import desc
        announcements = Announcement.query.filter_by(is_active=True)\
            .order_by(desc(Announcement.priority), desc(Announcement.created_at))\
            .limit(3).all()
        return {'announcements': announcements}
    
    @app.context_processor
    def inject_system_info():
        return {
            'sys': sys,
            'platform': platform,
            'db': db
        }
    
    return app

# Import controller after app creation to avoid circular imports
from bomber_controller import BombController

# Initialize controller with socketio
controller = BombController(socketio)

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)