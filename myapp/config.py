import os
from dotenv import load_dotenv

load_dotenv()  # Carga las variables de entorno del archivo .env

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_FILE_DIR = '.flask_session/'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'None'
    SESSION_COOKIE_SECURE = True

    MONGODB_URI = os.getenv('MONGODB_URI')
    DB_NAME = 'api-bd-1'

    # Variable de entorno para la API de OpenAI (usa el mismo nombre en todas partes)
    OPEN_API_KEY = os.getenv('OPEN_API_KEY')
    OPEN_API_MODEL = os.getenv('OPEN_API_MODEL', 'gpt-3.5-turbo')

    CONTEXTS_DIR = os.getenv('CONTEXTS_DIR', 'context')
