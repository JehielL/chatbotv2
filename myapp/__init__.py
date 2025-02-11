from flask import Flask
from .config import Config
from .extensions import session_ext, cors, init_db
from .routes import init_routes

def create_app():
    app = Flask(__name__, static_folder='images', static_url_path='/images')
    app.config.from_object(Config)

    # Inicializa las extensiones
    session_ext.init_app(app)
    cors.init_app(app, supports_credentials=True, resources={r"/*": {"origins": "http://localhost:4200"}})
    init_db(app)

    # Registra los blueprints de rutas
    init_routes(app)

    return app
