from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from database import db
from models import User, AttackLog
from datetime import datetime
import re

auth_bp = Blueprint('auth', __name__)
bcrypt = Bcrypt()

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        
        if not user or not bcrypt.check_password_hash(user.password, password):
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth.login'))
        
        if not user.is_approved and not user.is_admin:
            flash('Your account is pending approval', 'warning')
            return redirect(url_for('auth.login'))
        
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        login_user(user, remember=remember)
        
        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return redirect(url_for('auth.register'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('auth.register'))
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'error')
            return redirect(url_for('auth.register'))
        
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Invalid email format', 'error')
            return redirect(url_for('auth.register'))
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('auth.register'))
        
        # Create user
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            is_admin=False,
            is_approved=False,
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please wait for admin approval.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    attacks = AttackLog.query.filter_by(user_id=current_user.id)\
        .order_by(AttackLog.created_at.desc()).limit(10).all()
    return render_template('profile.html', attacks=attacks)

@auth_bp.route('/api/user/stats')
@login_required
def user_stats():
    total_attacks = AttackLog.query.filter_by(user_id=current_user.id).count()
    total_messages = db.session.query(db.func.sum(AttackLog.messages_sent))\
        .filter_by(user_id=current_user.id).scalar() or 0
    
    return jsonify({
        'username': current_user.username,
        'email': current_user.email,
        'member_since': current_user.created_at.strftime('%Y-%m-%d'),
        'total_attacks': total_attacks,
        'total_messages': total_messages,
        'is_admin': current_user.is_admin,
        'is_approved': current_user.is_approved
    })