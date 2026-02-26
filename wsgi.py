# wsgi.py
from app import create_app, socketio
from bomber_controller import BombController

# Create the Flask app instance
app = create_app()

# Initialize controller with socketio
from app import socketio as app_socketio
controller = BombController(app_socketio)

# This is what gunicorn will look for
application = app

if __name__ == "__main__":
    socketio.run(app)
