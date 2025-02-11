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

# Inicializa el cliente de OpenAI usando la variable de entorno
client = OpenAI(api_key=os.getenv('OPEN_API_KEY'))

def load_context_content(context_filename):
    safe_filename = os.path.basename(context_filename)
    # Usa el directorio definido en Config (o la variable de entorno)
    context_dir = os.getenv("CONTEXTS_DIR", "context")
    context_filepath = os.path.join(context_dir, safe_filename + ".txt")
    if os.path.exists(context_filepath):
        with open(context_filepath, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise FileNotFoundError(f"Context file {context_filepath} not found")

@chat_bp.before_request
def set_session_permanent():
    session.permanent = True
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

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
            return jsonify({"error": "Datos incompletos"}), 400
        
        ensure_user_id(session)
        user_id = session['user_id']
        
        # Actualiza la colección interactions en la DB
        interactions_collection = current_app.db.interactions
        interactions_collection.update_one(
            {"user_id": user_id},
            {'$inc': {'count': 1},
             '$push': {'messages': {'user_message': user_message, 'timestamp': datetime.now()}}},
            upsert=True
        )
        
        nuevos_datos = detectar_datos_usuario(user_message)
        if nuevos_datos:
            # Guarda los datos supervisados en la colección de usuarios
            manejar_datos_usuario(user_id, nuevos_datos, session, current_app.db.usuarios, current_app.logger)
        
        context_content = load_context_content(context_filename)
        
        messages = [
            {"role": "system", "content": context_content},
            {"role": "user", "content": user_message}
        ]
        
        response = client.chat.completions.create(
            model=os.getenv('OPEN_API_MODEL', 'gpt-3.5-turbo'),
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        bot_response = response.choices[0].message.content
        
        chat_entry = {
            'user_id': user_id,
            'session_id': session['session_id'],
            'user_message': user_message,
            'response': bot_response,
            'timestamp': datetime.utcnow()
        }
        current_app.db.chats.insert_one(chat_entry)
        
        return jsonify({'response': bot_response}), 200
    except Exception as e:
        current_app.logger.error(f"Error en el endpoint /chat: {e}")
        return jsonify({'error': str(e)}), 500

@chat_bp.route('/reset', methods=['POST'])
def reset():
    try:
        context_filename = request.headers.get('x-contexto')
        if not context_filename:
            return jsonify({"message": "Falta header 'x-contexto'"}), 400
        
        user_id = session.get('user_id', 'anonymous')
        new_conversation_id = str(uuid.uuid4())
        session['conversation_id'] = new_conversation_id
        
        context_content = load_context_content(context_filename)
        
        current_app.db.chats.update_one(
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
        
        return jsonify({'success': True})
    except Exception as e:
        current_app.logger.error(f"Error en el endpoint /reset: {e}")
        return jsonify({"error": str(e)}), 500

@chat_bp.route('/contextos', methods=['GET'])
def get_history():
    try:
        session_id = session.get('session_id')
        conversation_id = session.get('conversation_id')
        conversation = current_app.db.chats.find_one({
            'session_id': session_id,
            'conversation_id': conversation_id
        })
        history = conversation['history'] if conversation and 'history' in conversation else []
        return jsonify({'history': history})
    except Exception as e:
        current_app.logger.error(f"Error en el endpoint /contextos: {e}")
        return jsonify({"error": str(e)}), 500
