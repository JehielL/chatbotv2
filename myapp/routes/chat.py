# myapp/routes/chat.py
from flask import Blueprint, request, jsonify, session, current_app
from datetime import datetime
import uuid
import os
from openai import OpenAI

from myapp.utils.regex_utils import detectar_datos_usuario
from myapp.utils.session_helpers import ensure_user_id
from myapp.utils.data_utils import manejar_datos_usuario

chat_bp = Blueprint('chat', __name__)

client = OpenAI(api_key=os.getenv('OPEN_API_KEY'))

def load_context_content(context_filename):
    safe_filename = os.path.basename(context_filename)
    context_dir = os.getenv("CONTEXTS_DIR", "context")
    context_filepath = os.path.join(context_dir, safe_filename + ".txt")
    if os.path.exists(context_filepath):
        with open(context_filepath, "r", encoding="utf-8") as f:
            content = f.read()
            current_app.logger.info(f"Contexto cargado desde: {context_filepath}")
            return content
    else:
        error_msg = f"Context file {context_filepath} not found"
        current_app.logger.error(error_msg)
        raise FileNotFoundError(error_msg)

@chat_bp.before_request
def set_session_permanent():
    session.permanent = True
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        current_app.logger.info(f"Nueva session_id: {session['session_id']}")
    else:
        current_app.logger.info(f"Session activa: {session['session_id']}")

@chat_bp.route('/', methods=['GET'])
def index():
    return jsonify({'message': 'Chat API funcionando OK'})

@chat_bp.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        context_filename = request.headers.get('x-contexto')
        
        if not user_message or not context_filename:
            current_app.logger.warning("Solicitud con datos incompletos.")
            return jsonify({"error": "Datos incompletos"}), 400
        
        ensure_user_id(session)
        user_id = session['user_id']
        current_app.logger.info(f"Procesando mensaje para user_id: {user_id}")
        
        # Actualizar interacciones en MongoDB
        interactions_collection = current_app.db.interactions
        interactions_collection.update_one(
            {"user_id": user_id},
            {'$inc': {'count': 1},
             '$push': {'messages': {'user_message': user_message, 'timestamp': datetime.now()}}},
            upsert=True
        )
        current_app.logger.info("Interacciones actualizadas en MongoDB.")
        
        # Extraer y guardar datos supervisados
        nuevos_datos = detectar_datos_usuario(user_message)
        current_app.logger.info(f"Datos extraídos: {nuevos_datos}")
        if nuevos_datos:
            from myapp.utils.data_utils import manejar_datos_usuario
            manejar_datos_usuario(user_id, nuevos_datos, session, current_app.db.usuarios, current_app.logger)
            current_app.logger.info("Datos supervisados guardados en MongoDB.")
        else:
            current_app.logger.info("No se detectaron nuevos datos supervisados.")
        
        # Cargar el contexto
        context_content = load_context_content(context_filename)
        
        # Preparar mensajes para OpenAI
        messages = [
            {"role": "system", "content": context_content},
            {"role": "user", "content": user_message}
        ]
        current_app.logger.info("Llamando a la API de OpenAI...")
        response = client.chat.completions.create(
            model=os.getenv('OPEN_API_MODEL', 'gpt-3.5-turbo'),
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        bot_response = response.choices[0].message.content
        current_app.logger.info(f"Respuesta de OpenAI: {bot_response}")
        
        # Guardar el chat en MongoDB
        chat_entry = {
            'user_id': user_id,
            'session_id': session['session_id'],
            'user_message': user_message,
            'response': bot_response,
            'timestamp': datetime.utcnow()
        }
        current_app.db.chats.insert_one(chat_entry)
        current_app.logger.info("Chat guardado en MongoDB.")
        
        # Integración con Pipedrive: Siempre crear un nuevo deal
        try:
            usuario = current_app.db.usuarios.find_one({"user_id": user_id}, {"_id": 0})
            current_app.logger.info(f"Datos del usuario para Pipedrive: {usuario}")
            if usuario:
                from myapp.services.pipedrive_service import create_person, create_deal
                # Preparar datos para crear la persona
                person_data = {
                    "name": usuario.get("nombre") or usuario.get("nombreCliente"),
                    "email": usuario.get("email") or usuario.get("correoElectronico"),
                    "phone": usuario.get("telefono")
                }
                current_app.logger.info(f"Creando persona en Pipedrive con datos: {person_data}")
                person_response = create_person(person_data)
                person_id = person_response.get("data", {}).get("id")
                if person_id:
                    # Usar el campo "motivovisita" para el título del nuevo deal
                    motivovisita = usuario.get("motivo_visita") or usuario.get("motivovisita")
                    deal_data = {
                        "title": motivovisita if motivovisita else "Nuevo Deal",
                        "pipeline_id": 6,  # Asumiendo que el pipeline es fijo (por ejemplo, el ID 6)
                        "person_id": person_id
                    }
                    deal_response = create_deal(deal_data)
                    current_app.logger.info(f"Nuevo deal creado en Pipedrive: {deal_response}")
                else:
                    current_app.logger.error("No se pudo crear la persona en Pipedrive.")
            else:
                current_app.logger.warning("No se encontraron datos del usuario para Pipedrive.")
        except Exception as pipedrive_error:
            current_app.logger.error(f"Error en la integración con Pipedrive: {pipedrive_error}")
            # Continuamos sin bloquear la respuesta al usuario
        
        return jsonify({'response': bot_response}), 200
    except Exception as e:
        current_app.logger.error(f"Error en el endpoint /chat: {e}")
        return jsonify({'error': str(e)}), 500
