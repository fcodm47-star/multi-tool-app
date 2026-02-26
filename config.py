import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'multi_tool:'
    
    # Admin settings
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME') or 'admin'
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD') or 'admin123'
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL') or 'admin@example.com'
    
    # Announcement settings
    MAX_ANNOUNCEMENTS = 10
    ANNOUNCEMENT_CACHE_TIME = 300  # 5 minutes
    
    # Rate limiting
    RATE_LIMIT_ENABLED = True
    MAX_ATTACKS_PER_DAY = 5
    MAX_MESSAGES_PER_ATTACK = 500