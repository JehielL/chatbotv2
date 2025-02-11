# Importación de módulos y librerías necesarios para la aplicación

import re  # Para trabajar con expresiones regulares y extraer patrones de texto
import os  # Para interactuar con el sistema operativo, manejar rutas y variables de entorno
import uuid  # Para generar identificadores únicos (UUID) para usuarios y sesiones
import logging  # Para registrar mensajes de log (información, errores, etc.)
import joblib  # Para guardar y cargar modelos de machine learning (serialización de objetos)
from datetime import datetime  # Para trabajar con fechas y horas (timestamps)
from flask import Flask, request, jsonify, session  # Componentes básicos de Flask para crear la API
from openai import OpenAI  # Cliente para interactuar con la API de OpenAI
from dotenv import load_dotenv  # Para cargar variables de entorno desde un archivo .env
import pymongo  # Para conectarse y trabajar con MongoDB
import geoip2.database  # Para obtener información geográfica a partir de direcciones IP usando la base de datos GeoLite2
import atexit  # Para registrar funciones que se ejecutan cuando el programa finaliza
from sklearn.ensemble import RandomForestClassifier  # Modelo de clasificación Random Forest
from sklearn.preprocessing import LabelEncoder  # Para codificar variables categóricas en números
from sklearn.model_selection import train_test_split  # Para dividir datos en conjuntos de entrenamiento y prueba (aunque no se usa en este código)
import pandas as pd  # Para trabajar con datos en formato DataFrame
from functools import wraps  # Para crear decoradores y preservar metadatos de las funciones

# Configuración del logging para registrar eventos a nivel INFO
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  # Se crea un objeto logger para este módulo

# Cargar variables de entorno definidas en el archivo .env
load_dotenv()

# -------------------- Configuración Inicial de Flask --------------------

# Se crea una instancia de la aplicación Flask, indicando dónde se encuentran los archivos estáticos
app = Flask(__name__, static_folder='images', static_url_path='/images')

# Configuración de la clave secreta de la aplicación (usada para firmar cookies y sesiones)
app.secret_key = os.getenv('SECRET_KEY')

# Configuración de las cookies de sesión
app.config['SESSION_COOKIE_SECURE'] = False  # Para desarrollo: permite enviar la cookie sin HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Política SameSite para las cookies

# -------------------- Configuración de Flask-Session --------------------

from flask_session import Session  # Importar la extensión para gestionar sesiones en Flask

# Configurar el almacenamiento de sesiones en el sistema de archivos
app.config['SESSION_TYPE'] = 'filesystem'           # Guardar sesiones en archivos
app.config['SESSION_PERMANENT'] = True               # Las sesiones serán permanentes (persistentes)
app.config['SESSION_USE_SIGNER'] = True              # Firmar la cookie para mayor seguridad
app.config['SESSION_FILE_DIR'] = './flask_sessions'    # Directorio donde se almacenarán los archivos de sesión
app.config['SESSION_COOKIE_HTTPONLY'] = False        # Permitir el acceso a la cookie desde JavaScript (menos seguro, pero útil en frontend)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'         # Permitir sesiones cross-origin
app.config['SESSION_COOKIE_SECURE'] = True           # Requiere HTTPS para enviar la cookie (ideal para producción)
Session(app)  # Inicializa la extensión Flask-Session con la configuración anterior

# -------------------- Configuración de CORS --------------------

from flask_cors import CORS  # Importa la extensión para permitir solicitudes de otros orígenes (CORS)

# Configura CORS para permitir solicitudes desde 'http://localhost:4200' (ajusta según tu frontend)
CORS(app, supports_credentials=True, resources={
    r"/*": {
        "origins": ["http://localhost:4200"],  # Origen permitido
        "methods": ["GET", "POST", "OPTIONS"],   # Métodos HTTP permitidos
        "allow_headers": ["Content-Type", "Authorization", "x-api-key", "x-contexto"],  # Headers permitidos
        "supports_credentials": True             # Permitir el envío de credenciales (cookies, etc.)
    }
})

# -------------------- Configuración de OpenAI --------------------

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')  # Se obtiene la API key de OpenAI desde las variables de entorno
client = OpenAI(api_key=OPENAI_API_KEY)  # Se inicializa el cliente de OpenAI con la API key

# -------------------- Conexión a MongoDB --------------------

mongo_client = pymongo.MongoClient(os.getenv('MONGODB_URI'))  # Se conecta a MongoDB utilizando la URI definida en las variables de entorno
db = mongo_client['api-bd-1']  # Se selecciona la base de datos 'api-bd-1'
chats_collection = db['chats']  # Colección para almacenar los chats o conversaciones
usuarios_collection = db['usuarios']  # Colección para almacenar los datos de los usuarios
interactions_collection = db['interactions']  # Colección para registrar el número de interacciones por usuario

# -------------------- Definición de Expresiones Regulares --------------------

regex_patterns = {
    'nombre': re.compile(r'(?i)(?:mi nombre es|soy|me llamo|mi nombre)\s+([A-ZÁÉÍÓÚÜÑa-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑa-záéíóúüñ]+)*)'),
    # Patrón para extraer el nombre (frases como "mi nombre es", "soy", etc.)
    'telefono': re.compile(r'(\+?\d{1,4}[-.\s]?\(?\d{1,}\)?[-.\s]?\d{1,}[-.\s]?\d{1,}[-.\s]?\d{1,})'),
    # Patrón para extraer números de teléfono en diversos formatos
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    # Patrón para detectar direcciones de correo electrónico
    'empresa': re.compile(r'(?i)(?:trabajo en|empresa es|soy de)\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ0-9\s&.,-]{3,})'),
    # Patrón para extraer el nombre de la empresa (frases como "trabajo en", "empresa es", etc.)
    'motivo_visita': re.compile(r'(?i)(?:visitar|visita|reunirme con| conocer| me interesa | quiero saber | conocer )\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ0-9\s&.,-]{3,})')
    # Patrón para extraer el motivo de la visita o interés
}

# -------------------- Configuración de GeoIP --------------------

# Inicializa el lector de GeoIP utilizando la base de datos GeoLite2 (ajusta la ruta según corresponda)
geoip_reader = geoip2.database.Reader('C:/Users/Alex/Desktop/ASISTENTE-VIRTUALV1/para Docker/app/GeoLite2-Country_20240917/GeoLite2-Country.mmdb')

# -------------------- Decorador para Requerir API Key --------------------

def require_api_key(f):
    @wraps(f)  # Preserva la firma y documentación de la función original
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('x-api-key')  # Se extrae la API key del header 'x-api-key'
        if api_key and api_key == os.getenv('API_KEY'):  # Se compara con la API key definida en las variables de entorno
            return f(*args, **kwargs)  # Si es válida, se ejecuta la función decorada
        else:
            return jsonify({"message": "Unauthorized"}), 401  # Si no es válida, se devuelve un error 401 (no autorizado)
    return decorated_function  # Retorna la función decorada

# -------------------- Funciones Auxiliares --------------------

def ensure_user_id():
    """
    Asegura que la sesión tenga un 'user_id' único.
    """
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())  # Genera un UUID único para el usuario
        session.modified = True  # Marca la sesión como modificada para asegurar su guardado
    logger.info(f"✅ Usuario activo: {session['user_id']}")  # Registra en el log el 'user_id' asignado

def detectar_datos_usuario(mensaje):
    """
    Extrae datos del mensaje del usuario utilizando los patrones definidos en 'regex_patterns'.
    Devuelve un diccionario con la información detectada.
    """
    datos = {}  # Diccionario para almacenar los datos extraídos
    logger.info(f"📩 Mensaje recibido: {mensaje}")  # Registra el mensaje recibido
    for campo, patron in regex_patterns.items():
        matches = patron.findall(mensaje)  # Busca todas las coincidencias para el patrón actual en el mensaje
        logger.info(f"🔎 Buscando {campo} en mensaje: {matches}")  # Registra las coincidencias encontradas para el campo
        if matches:  # Si se encontraron coincidencias
            if campo in ['nombre', 'empresa', 'motivo_visita']:
                datos[campo] = matches[-1].strip()  # Para estos campos, toma la última coincidencia y elimina espacios extra
            else:
                # Para campos como 'telefono' o 'email', elimina espacios internos y guarda como lista
                datos[campo] = [match.replace(" ", "") for match in matches]
    logger.info(f"📌 Datos detectados en el mensaje: {datos}")  # Registra el diccionario con los datos extraídos
    return datos  # Retorna el diccionario con la información detectada

# Primera definición de actualizar_interacciones (se sobrescribe con la segunda)
def actualizar_interacciones(user_id):
    interactions_collection.update_one(
        {'user_id': user_id},  # Busca el documento por 'user_id'
        {'$inc': {'count': 1}},  # Incrementa en 1 el campo 'count'
        upsert=True  # Crea el documento si no existe
    )
    return interactions_collection.find_one({'user_id': user_id})['count']  # Retorna el contador actualizado

# Función para cargar el contenido de un archivo de contexto
def load_context_content(context_filename):
    if not context_filename:
        raise ValueError("El header 'x-contexto' es obligatorio.")  # Lanza un error si no se proporciona el nombre del contexto
    safe_filename = os.path.basename(context_filename)  # Asegura que solo se use el nombre base del archivo
    context_dir = os.getenv("CONTEXTS_DIR", "contextos")  # Directorio donde se encuentran los contextos (por defecto "contextos")
    context_filepath = os.path.join(context_dir, safe_filename + '.txt')  # Construye la ruta completa al archivo de contexto
    if os.path.exists(context_filepath):
        with open(context_filepath, 'r', encoding='utf-8') as f:  # Abre el archivo en modo lectura con codificación UTF-8
            content = f.read()  # Lee el contenido completo del archivo
            logger.info(f"Contexto cargado: {context_filename}")  # Registra que el contexto se cargó correctamente
            return content  # Retorna el contenido leído
    else:
        logger.error(f"Archivo de contexto no encontrado: {context_filename}")  # Registra un error si el archivo no existe
        raise FileNotFoundError(f"Archivo de contexto no encontrado: {context_filename}")  # Lanza una excepción

# Segunda definición de actualizar_interacciones (sobrescribe la anterior)
def actualizar_interacciones(user_id):
    result = interactions_collection.update_one(
        {'user_id': user_id},  # Busca el documento por 'user_id'
        {'$inc': {'count': 1}},  # Incrementa el campo 'count' en 1
        upsert=True  # Si no existe, crea un nuevo documento
    )
    doc = interactions_collection.find_one({'user_id': user_id})  # Obtiene el documento actualizado
    logger.info(f"Interacciones actualizadas para {user_id}: {doc['count']}")  # Registra el nuevo valor de 'count'
    return doc['count']  # Retorna el contador actualizado

def entrenar_modelo():
    """
    Entrena un modelo de machine learning (RandomForestClassifier) utilizando los datos de la colección 'usuarios'.
    Codifica variables categóricas con LabelEncoder y guarda el modelo junto con los encoders.
    Retorna el modelo entrenado y el encoder para 'empresa'. Si hay pocos datos, retorna (None, None).
    """
    try:
        # Obtiene todos los documentos de usuarios (sin el campo '_id')
        usuarios = list(usuarios_collection.find({}, {'_id': 0}))
        if len(usuarios) < 20:
            return None, None  # Si hay menos de 20 usuarios, no se entrena el modelo
        df = pd.DataFrame(usuarios)  # Convierte la lista de usuarios en un DataFrame de pandas
        df = df.where(pd.notnull(df), None)  # Reemplaza valores NaN por None
        
        # Codificación: utiliza LabelEncoder para convertir variables categóricas en números
        encoders = {
            'nombre': LabelEncoder().fit(df['nombre'].fillna('')),
            'email': LabelEncoder().fit(df['email'].fillna('')),
            'empresa': LabelEncoder().fit(df['empresa'].fillna('Desconocida')),
            'telefono': LabelEncoder().fit(df['telefono'].fillna('')),
            'motivo visita': LabelEncoder().fit(df['motivo visita'].fillna(''))
        }

        # Se preparan las características (X) a partir de 'nombre' y 'email'
        X = pd.DataFrame({
            'nombre': encoders['nombre'].transform(df['nombre']),
            'email': encoders['email'].transform(df['email'])
        })
        
        # La variable objetivo (y) se obtiene a partir de la columna 'empresa'
        y = encoders['empresa'].transform(df['empresa'])

        # Se crea y entrena un clasificador RandomForest con 100 árboles
        modelo = RandomForestClassifier(n_estimators=100)
        modelo.fit(X, y)

        # Guarda el modelo entrenado y cada uno de los encoders en archivos usando joblib
        joblib.dump(modelo, 'modelo_empresas.pkl')
        for campo, encoder in encoders.items():
            joblib.dump(encoder, f'encoder_{campo}.pkl')

        return modelo, encoders['empresa']  # Retorna el modelo y el encoder para 'empresa'
    
    except Exception as e:
        print(f"Error entrenando modelo: {str(e)}")  # Imprime el error si ocurre alguno durante el entrenamiento
        return None, None  # Retorna None en caso de fallo

def manejar_datos_usuario(user_id, nuevos_datos):
    """
    Acumula en la sesión los datos extraídos del mensaje del usuario. Cuando se tienen
    los campos requeridos ('nombre', 'email', 'motivo_visita'), guarda la información en MongoDB.
    """
    if 'datos_acumulados' not in session:
        session['datos_acumulados'] = {}  # Inicializa el diccionario en la sesión si no existe
        logger.info("📝 Inicializando datos acumulados en sesión")

    logger.info(f"🔍 Antes de actualizar, datos en sesión: {session['datos_acumulados']}")
    logger.info(f"🔄 Nuevos datos detectados: {nuevos_datos}")

    # Acumula los nuevos datos sin sobrescribir los existentes
    for campo, valor in nuevos_datos.items():
        if valor:
            if campo not in session['datos_acumulados']:
                session['datos_acumulados'][campo] = valor  # Si el campo no existe, lo agrega
                logger.info(f"✅ Campo actualizado en sesión: {campo} = {valor}")
            elif isinstance(session['datos_acumulados'][campo], list) and isinstance(valor, list):
                session['datos_acumulados'][campo].extend(valor)  # Si es una lista, extiende los valores
    session.modified = True  # Marca la sesión como modificada para asegurar que se guarden los cambios

    logger.info(f"🆕 Después de actualizar, datos en sesión: {session['datos_acumulados']}")

    # Verifica si se tienen todos los campos requeridos para guardar los datos
    campos_requeridos = ['nombre', 'email', 'motivo_visita']
    if all(campo in session['datos_acumulados'] for campo in campos_requeridos):
        try:
            # Prepara el documento final del usuario con los datos acumulados y la fecha de registro
            usuario_final = {
                'user_id': user_id,
                **session['datos_acumulados'],
                'fecha_registro': datetime.utcnow()
            }
            # Actualiza (o inserta) el documento en la colección 'usuarios'
            usuarios_collection.update_one(
                {'user_id': user_id},
                {'$set': usuario_final},
                upsert=True
            )
            logger.info(f"✅ Datos guardados en MongoDB: {usuario_final}")

            # Limpia los datos acumulados en la sesión tras guardarlos exitosamente
            session.pop('datos_acumulados')
            session.modified = True
            logger.info("🗑️ Datos de sesión limpiados después de guardar.")
        
        except Exception as e:
            logger.error(f"❌ Error al guardar en MongoDB: {str(e)}")

def cargar_modelo():
    """
    Carga el modelo de machine learning previamente guardado y sus encoders.
    Retorna el modelo y un diccionario con los encoders.
    """
    try:
        modelo = joblib.load('modelo_empresas.pkl')  # Carga el modelo desde el archivo
        encoders = {
            'nombre': joblib.load('encoder_nombre.pkl'),
            'email': joblib.load('encoder_email.pkl'),
            'empresa': joblib.load('encoder_empresa.pkl'),
            'telefono': joblib.load('encoder_telefono.pkl'),
        }
        return modelo, encoders  # Retorna el modelo y los encoders
    except Exception as e:
        print(f"Error cargando modelo: {str(e)}")
        return None, None

# -------------------- Definición de Endpoints --------------------

# Función que se ejecuta antes de cada solicitud para asegurar que la sesión sea permanente
@app.before_request
def make_session_permanent():
    session.permanent = True  # Marca la sesión como permanente (persistente)
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())  # Genera un identificador único para la sesión si no existe
        logger.info(f"⚠️ Nueva sesión creada: {session['session_id']}")
    else:
        logger.info(f"✅ Usuario activo: {session['session_id']}")

# Endpoint raíz: devuelve un mensaje sencillo indicando que la API está operativa
@app.route('/')
def index():
    return jsonify({"message": "API operativa"})

# Endpoint para verificar el estado de la sesión actual, incluyendo 'session_id', 'user_id' y datos acumulados
@app.route('/verificar_sesion', methods=['GET'])
def verificar_sesion():
    return jsonify({
        "session_id": session.get('session_id', 'No hay sesión'),
        "user_id": session.get('user_id', 'No hay user_id'),
        "datos_acumulados": session.get('datos_acumulados', {})
    })

# Endpoint principal del chat:
# Recibe un mensaje del usuario, extrae datos, actualiza interacciones, llama a OpenAI para generar una respuesta,
# guarda la interacción en MongoDB y retorna la respuesta del bot.
@app.route('/chat', methods=['POST'])
@require_api_key
def chat():
    try:
        data = request.get_json()  # Extrae los datos JSON enviados en la solicitud
        user_message = data.get('message', '')  # Obtiene el mensaje del usuario (por defecto cadena vacía)
        context_filename = request.headers.get('x-contexto')  # Obtiene el nombre del contexto desde el header 'x-contexto'
        
        # Verifica que se haya enviado el mensaje y el nombre del contexto
        if not user_message or not context_filename:
            return jsonify({"error": "Datos incompletos"}), 400

        ensure_user_id()  # Asegura que la sesión tenga un 'user_id'
        user_id = session['user_id']  # Obtiene el 'user_id' de la sesión
        interaction_count = actualizar_interacciones(user_id)  # Actualiza y obtiene el contador de interacciones del usuario

        # Detecta y maneja datos del usuario presentes en el mensaje
        nuevos_datos = detectar_datos_usuario(user_message)
        if nuevos_datos:
            manejar_datos_usuario(user_id, nuevos_datos)

        # Carga el contenido del contexto desde el archivo especificado en el header
        context_content = load_context_content(context_filename)
        
        # Prepara los mensajes que se enviarán a la API de OpenAI:
        # El primer mensaje es del sistema con el contexto y el segundo es el mensaje del usuario.
        messages = [
            {"role": "system", "content": context_content},
            {"role": "user", "content": user_message}
        ]

        # Llama a la API de OpenAI para generar una respuesta utilizando el modelo "gpt-3.5-turbo"
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,      # Número máximo de tokens en la respuesta
            temperature=0.7      # Parámetro que controla la creatividad de la respuesta
        )
        
        # Extrae el contenido de la respuesta del bot
        bot_response = response.choices[0].message.content

        # Crea una entrada para el historial de chat que se guardará en MongoDB
        chat_entry = {
            'user_id': user_id,
            'session_id': session['session_id'],
            'message': user_message,
            'response': bot_response,
            'timestamp': datetime.utcnow()  # Marca de tiempo en formato UTC
        }
        chats_collection.insert_one(chat_entry)  # Inserta la entrada en la colección 'chats'
        logger.info(f"Chat guardado para {user_id}")  # Registra en el log que el chat fue guardado

        return jsonify({'response': bot_response})  # Retorna la respuesta del bot en formato JSON

    except Exception as e:
        logger.error(f"Error en el endpoint /chat: {str(e)}")  # Registra cualquier error ocurrido
        return jsonify({'error': str(e)}), 500  # Retorna un error 500 en caso de excepción

# Endpoint para reiniciar la conversación actual:
# Genera un nuevo 'conversation_id', actualiza el contexto y crea una nueva entrada en la colección 'chats'.
@app.route('/reset', methods=['POST'])
@require_api_key
def reset():
    try:
        context_filename = request.headers.get('x-contexto')  # Obtiene el nombre del contexto desde el header
        if not context_filename:
            return jsonify({"message": "Falta header 'x-contexto'"}), 400  # Retorna error si falta el header

        user_id = session.get('user_id', 'anonymous')  # Obtiene el 'user_id' de la sesión, usa 'anonymous' si no existe
        new_conversation_id = str(uuid.uuid4())  # Genera un nuevo identificador único para la conversación
        session['conversation_id'] = new_conversation_id  # Almacena el nuevo 'conversation_id' en la sesión

        context_content = load_context_content(context_filename)  # Carga el contenido del nuevo contexto

        # Actualiza (o inserta) en la colección 'chats' la nueva conversación con el contexto de sistema
        chats_collection.update_one(
            {'session_id': session['session_id'], 'conversation_id': new_conversation_id},
            {'$set': {
                'conversation_id': new_conversation_id,
                'user_id': user_id,
                'history': [{"role": "system", "content": context_content}],
                'context_content': context_content,
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )

        return jsonify({'success': True})  # Retorna un mensaje de éxito
    except Exception as e:
        return jsonify({'error': str(e)}), 500  # Retorna error 500 en caso de excepción

# Endpoint para obtener el historial de la conversación actual almacenada en la colección 'chats'
@app.route('/history', methods=['GET'])
@require_api_key
def get_history():
    try:
        session_id = session['session_id']  # Obtiene el 'session_id' de la sesión
        conversation_id = session.get('conversation_id')  # Obtiene el 'conversation_id' actual de la sesión
        
        # Busca la conversación en la colección 'chats' utilizando 'session_id' y 'conversation_id'
        conversation = chats_collection.find_one({
            'session_id': session_id,
            'conversation_id': conversation_id
        })
        
        # Retorna el historial de chat si existe, o una lista vacía si no se encontró
        return jsonify({'history': conversation['history'] if conversation else []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500  # Retorna error 500 en caso de excepción

# Endpoint para obtener la lista de usuarios registrados en la colección 'usuarios'
@app.route('/usuarios', methods=['GET'])
@require_api_key
def obtener_usuarios():
    try:
        # Recupera todos los documentos de la colección 'usuarios', excluyendo el campo '_id'
        usuarios = list(usuarios_collection.find({}, {"_id": 0}))
        return jsonify({'usuarios': usuarios})  # Retorna la lista de usuarios en formato JSON
    except Exception as e:
        return jsonify({'error': str(e)}), 500  # Retorna error 500 en caso de excepción

# Endpoint para entrenar el modelo de machine learning utilizando los datos de la colección 'usuarios'
@app.route('/entrenar-modelo', methods=['POST'])
@require_api_key
def entrenar_endpoint():
    try:
        modelo, encoder = entrenar_modelo()  # Llama a la función que entrena el modelo
        if modelo:
            return jsonify({"message": "Modelo actualizado exitosamente"})  # Retorna mensaje de éxito si se entrenó el modelo
        return jsonify({"message": "No hay suficientes datos para entrenar"}), 400  # Retorna error si faltan datos
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Retorna error 500 en caso de excepción

# -------------------- Función de Limpieza al Finalizar la Aplicación --------------------

@atexit.register
def cleanup():
    geoip_reader.close()  # Cierra el lector de GeoIP para liberar recursos cuando la aplicación finaliza

# -------------------- Bloque Principal para Iniciar la Aplicación --------------------

if __name__ == '__main__':
    # Se asegura de que exista el directorio 'encoders' para almacenar los encoders si es necesario
    if not os.path.exists('encoders'):
        os.makedirs('encoders')
    # Se inicia la aplicación Flask en modo debug, accesible desde cualquier interfaz en el puerto 5001
    app.run(debug=True, host='0.0.0.0', port=5001)
