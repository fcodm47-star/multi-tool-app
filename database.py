from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime

db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    db.init_app(app)
    migrate.init_app(app, db)
    
    with app.app_context():
        db.create_all()
        
        # Create admin user if not exists
        from models import User
        from flask_bcrypt import Bcrypt
        bcrypt = Bcrypt(app)
        
        admin = User.query.filter_by(username=app.config['ADMIN_USERNAME']).first()
        if not admin:
            admin = User(
                username=app.config['ADMIN_USERNAME'],
                email=app.config['ADMIN_EMAIL'],
                password=bcrypt.generate_password_hash(app.config['ADMIN_PASSWORD']).decode('utf-8'),
                is_admin=True,
                is_approved=True,
                created_at=datetime.utcnow()
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created")