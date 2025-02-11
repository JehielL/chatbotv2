from .chat import chat_bp
from .usuarios import usuarios_bp  # Descomenta si usas endpoints de usuarios

def init_routes(app):
    # Se registran los blueprints con los prefijos correspondientes
    app.register_blueprint(chat_bp, url_prefix='/chat')
    app.register_blueprint(usuarios_bp, url_prefix='/usuarios')
