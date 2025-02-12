from .chat import chat_bp
from .usuarios import usuarios_bp
from .pipedrive import pipedrive_bp  # Nuevo

def init_routes(app):
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(usuarios_bp, url_prefix='/usuarios')
    app.register_blueprint(pipedrive_bp, url_prefix='/pipedrive')
