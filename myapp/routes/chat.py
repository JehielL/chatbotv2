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
    context_filepath = f"/chatbotv2025/myapp/context/{safe_filename}.txt"
    if os.path.exists(context_filepath):
        with open(context_filepath, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise FileNotFoundError(f"❌ ERROR: Archivo de contexto no encontrado: {context_filepath}")

@chat_bp.before_request
def set_session_permanent():
    session.permanent = True
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        current_app.logger.info(f"Nueva session_id creada: {session['session_id']}")
    else:
        current_app.logger.info(f"Sesión existente: {session['session_id']}")

def get_chat_history(user_id, session_id):
    """ Recupera el historial de chat desde MongoDB """
    chats_collection = current_app.db.chats
    conversation = chats_collection.find_one({"user_id": user_id, "session_id": session_id})
    
    if conversation:
        return conversation.get("history", [])
    return []
from myapp.services.pipedrive_service import create_person, create_deal

def enviar_a_pipedrive(user_id):
    """ Envía los datos del usuario a Pipedrive si tiene la información necesaria """
    try:
        current_app.logger.info(f"📤 Intentando enviar datos del usuario {user_id} a Pipedrive...")

        usuario = current_app.db.usuarios.find_one({"user_id": user_id}, {"_id": 0})
        if not usuario:
            current_app.logger.warning(f"⚠️ No se encontraron datos en MongoDB para el usuario {user_id}")
            return

        # ✅ Verificar que el usuario tiene la información completa
        nombre = usuario.get("nombre")
        email = usuario.get("email")
        telefono = usuario.get("telefono")
        motivo_visita = usuario.get("motivo_visita")

        if not (nombre and email and motivo_visita):
            current_app.logger.warning(f"⚠️ Faltan datos para enviar a Pipedrive (nombre, email o motivo_visita).")
            return

        # ✅ Verificar si ya tiene un deal_id
        deal_id = usuario.get("deal_id")

        if not deal_id:
            # Si no tiene deal_id, crear una persona en Pipedrive
            from myapp.services.pipedrive_service import create_person, create_deal  # ⚠️ Importar dentro de la función

            person_data = {
                "name": nombre,
                "email": email,
                "phone": telefono
            }
            current_app.logger.info(f"🛠️ Creando persona en Pipedrive con datos: {person_data}")
            person_response = create_person(person_data)
            person_id = person_response.get("data", {}).get("id")

            if person_id:
                # Crear un nuevo negocio (deal) asociado a la persona
                deal_data = {
                    "title": motivo_visita if motivo_visita else "Nuevo Deal",
                    "pipeline_id": 6,  # ID del pipeline en Pipedrive
                    "person_id": person_id
                }
                deal_response = create_deal(deal_data)
                new_deal_id = deal_response.get("data", {}).get("id")

                if new_deal_id:
                    # Guardar el deal_id en MongoDB
                    current_app.db.usuarios.update_one(
                        {"user_id": user_id},
                        {"$set": {"deal_id": new_deal_id}}
                    )
                    current_app.logger.info(f"✅ Nuevo negocio creado en Pipedrive: {new_deal_id}")
                else:
                    current_app.logger.error("❌ No se pudo obtener el deal_id al crear el nuevo negocio.")
            else:
                current_app.logger.error("❌ No se pudo crear la persona en Pipedrive.")

    except Exception as e:
        current_app.logger.error(f"❌ Error enviando datos a Pipedrive: {e}")

@chat_bp.route('/chat', methods=['POST'])
def chat():
    try:
        if not request.is_json:
            return jsonify({"error": "El request debe ser JSON"}), 400

        data = request.get_json() or {}
        user_message = data.get('message', '')
        context_filename = request.headers.get('x-contexto')

        if not user_message:
            return jsonify({"error": "El campo 'message' es obligatorio"}), 400
        if not context_filename:
            return jsonify({"error": "El encabezado 'x-contexto' es obligatorio"}), 400

        ensure_user_id(session)
        user_id = session['user_id']
        session_id = session['session_id']

        chat_history = get_chat_history(user_id, session_id)

        # ✅ Extraer datos del usuario y guardarlos en MongoDB
        nuevos_datos = detectar_datos_usuario(user_message)
        if nuevos_datos:
            current_app.logger.info(f"🛠️ Datos nuevos detectados: {nuevos_datos}")
            manejar_datos_usuario(user_id, nuevos_datos, session, current_app.db.usuarios, current_app.logger)
            
            # ✅ Llamar a Pipedrive sin esperar un motivo de visita específico
            enviar_a_pipedrive(user_id)

        # Cargar contexto
        try:
            context_content = load_context_content(context_filename)
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 400

        messages = [{"role": "system", "content": context_content}] + chat_history
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=os.getenv('OPEN_API_MODEL', 'gpt-3.5-turbo'),
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        bot_response = response.choices[0].message.content

        return jsonify({'response': bot_response}), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error en /chat: {e}")
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/history', methods=['GET'])
def get_history():
    """ Recupera el historial de la conversación del usuario """
    ensure_user_id(session)
    user_id = session['user_id']
    session_id = session['session_id']

    chat_history = get_chat_history(user_id, session_id)

    return jsonify({'history': chat_history})

@chat_bp.route('/reset', methods=['POST'])
def reset_chat():
    """ Resetea la conversación del usuario en la sesión y MongoDB """
    ensure_user_id(session)
    user_id = session['user_id']
    session_id = session['session_id']

    new_session_id = str(uuid.uuid4())
    session['session_id'] = new_session_id

    chats_collection = current_app.db.chats
    chats_collection.delete_one({"user_id": user_id, "session_id": session_id})

    return jsonify({'success': True, 'message': 'Chat reseteado con éxito'}), 200
