from flask import Blueprint, request, jsonify, session, current_app
from datetime import datetime
import uuid
import os
from flask_cors import CORS
from flask import Flask

from openai import OpenAI
import difflib  # 📌 Para buscar coincidencias similares
from myapp.utils.regex_utils import detectar_datos_usuario
from myapp.utils.session_helpers import ensure_user_id
from myapp.utils.data_utils import manejar_datos_usuario
from myapp.services.woocomerce_service import WC_SITE_URL, add_to_cart, create_order_for_checkout, get_add_to_cart_url, get_cart, get_checkout_url, verificar_producto_en_carrito, obtener_productos_con_categorias

chat_bp = Blueprint('chat', __name__)
app = Flask(__name__)  # 🔥 Definir app antes de usar CORS
CORS(app, supports_credentials=True)
client = OpenAI(api_key=os.getenv('OPEN_API_KEY'))

def load_context_content(context_filename):
    safe_filename = os.path.basename(context_filename)
    context_dir = os.getenv("CONTEXTS_DIR", "context")
    context_filepath = os.path.join(os.getenv("CONTEXTS_DIR", "context"), safe_filename + ".txt")
    if os.path.exists(context_filepath):
        with open(context_filepath, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise FileNotFoundError(f"❌ ERROR: Archivo de contexto no encontrado: {context_filepath}")

def procesar_mensaje(user_message, context_filename, user_id, session_id):
    """Procesa un mensaje y devuelve la respuesta del chatbot."""
    try:
        # 🔍 Verificar si el usuario quiere comprar algo antes de OpenAI
        if any(palabra in user_message.lower() for palabra in ["comprar", "agregar", "carrito"]):
            respuesta_carrito = manejar_carrito(user_message)
            if respuesta_carrito and "❌" not in respuesta_carrito:
                return {"response": f"✅ Producto agregado con éxito. Confirma aquí: {respuesta_carrito}"}
            else:
                current_app.logger.info("⚠️ Producto no encontrado en el carrito. Continuando con OpenAI.")

        # ✅ Recuperar historial de conversación
        chat_history = get_chat_history(user_id, session_id)

        # ✅ Extraer y guardar datos del usuario en MongoDB
        nuevos_datos = detectar_datos_usuario(user_message)
        if nuevos_datos:
            manejar_datos_usuario(user_id, nuevos_datos, session, current_app.db.usuarios, current_app.logger)
            enviar_a_pipedrive(user_id)

        # ✅ Cargar contexto del chatbot
        try:
            context_content = load_context_content(context_filename)
        except FileNotFoundError as e:
            return {"error": str(e)}

        # ✅ Generar respuesta con OpenAI
        messages = [{"role": "system", "content": context_content}] + chat_history
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=os.getenv('OPEN_API_MODEL', 'gpt-3.5-turbo'),
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        bot_response = response.choices[0].message.content

        # ✅ Guardar historial de conversación en MongoDB
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": bot_response})
        current_app.db.chats.update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": {"history": chat_history}},
            upsert=True
        )

        return {"response": bot_response}

    except Exception as e:
        current_app.logger.error(f"❌ Error en procesar_mensaje: {e}")
        return {"error": str(e)}

@chat_bp.before_request
def set_session_permanent():
    session.permanent = True
    if 'session_id' not in session:
        user_id = session.get('user_id', str(uuid.uuid4()))
        session['session_id'] = str(uuid.uuid4())

        existing_chat = current_app.db.chats.find_one({"user_id": user_id})
        if existing_chat:
            session['session_id'] = existing_chat["session_id"]  # Recuperar la sesión existente

        current_app.logger.info(f"🆕 Nueva session_id creada: {session['session_id']}")
    else:
        current_app.logger.info(f"♻️ Sesión existente: {session['session_id']}")

from myapp.utils.regex_utils import detectar_producto_y_cantidad
from myapp.services.woocomerce_service import get_add_to_cart_url
import requests



@chat_bp.route('/ver_cookies', methods=['GET'])
def ver_cookies():
    cookies = request.cookies
    print(f"📢 Cookies recibidas en Flask: {cookies}")
    print(f"📢 Estado actual de la sesión: {session}")  # Agregar antes del return
      # Debug en consola del servidor
    return jsonify({"cookies_recibidas": dict(cookies)})



@chat_bp.route('/guardar_sesion', methods=['POST'])
def guardar_sesion():
    # 🔍 Mostrar todas las cookies recibidas
    cookies = request.cookies
    current_app.logger.info(f"📢 Cookies recibidas en el servidor: {cookies}")
    print(f"📢 Cookies recibidas en Flask: {cookies}")  # Debug en consola del servidor

    # Buscar la cookie de WooCommerce
    woocommerce_session = request.cookies.get('wp_woocommerce_session')
    
    if woocommerce_session:
        session['wp_woocommerce_session'] = woocommerce_session
        print(f"📢 Estado actual de la sesión: {session}")  # Agregar antes del return

        return jsonify({"mensaje": "✅ Sesión de WooCommerce guardada correctamente"}), 200
    else:
        current_app.logger.info(f"📢 Estado actual de la sesión: {session}")  # Agregar antes del return
        return jsonify({
        "error": "⚠️ No se encontró la sesión de WooCommerce en las cookies",
        "cookies_recibidas": dict(cookies)  # 🔍 Corrección: Añadir una coma y convertir cookies a dict
        }), 400

from flask import Flask, request, jsonify

app = Flask(__name__)

def manejar_carrito(user_message):
    """ 
    Maneja la detección de intención de compra y devuelve solo la URL generada. 
    """
    mensaje = user_message.lower()

    # ✅ Extraer datos del mensaje del usuario
    datos = detectar_producto_y_cantidad(user_message)
    if not datos["producto_id"]:
        return "❌ No encontré el producto en nuestro catálogo. Prueba con otro nombre."

    product_id = datos["producto_id"]
    cantidad = datos["cantidad"]
    categoria = datos["categoria"]  # Puede ser "gadgets", "robots", etc.

    # ✅ Generar la URL sin hacer POST
    cart_url = get_add_to_cart_url(product_id, categoria, cantidad)

    return cart_url  # 🔥 Ahora solo devolvemos la URL


def get_chat_history(user_id, session_id):
    """ Recupera el historial de chat desde MongoDB """
    chats_collection = current_app.db.chats
    conversation = chats_collection.find_one({"user_id": user_id, "session_id": session_id})
    
    if conversation and "history" in conversation:
        return conversation["history"]  # Devolver historial existente
    return []  # Si no hay historial, devolver lista vacía

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
        data = request.get_json()
        user_message = data.get('message', '')
        context_filename = request.headers.get('x-contexto')

        if not user_message:
            return jsonify({"error": "El campo 'message' es obligatorio"}), 400
        if not context_filename:
            return jsonify({"error": "El encabezado 'x-contexto' es obligatorio"}), 400

        ensure_user_id(session)
        user_id = session['user_id']
        session_id = session['session_id']

        # 🔍 Si el mensaje es sobre carrito, devolvemos la URL directamente
        if any(palabra in user_message.lower() for palabra in ["comprar", "agregar", "carrito"]):
            cart_url = manejar_carrito(user_message)
            return jsonify({"response":" ✅ Producto Agregado Al carrito con exito, haz click para confirmar.", "url": cart_url})  # 🔥 Ahora solo devolvemos la URL

        # ✅ Recuperar historial de conversación
        chat_history = get_chat_history(user_id, session_id)

        # ✅ Extraer y guardar datos del usuario en MongoDB
        nuevos_datos = detectar_datos_usuario(user_message)
        if nuevos_datos:
            current_app.logger.info(f"🛠️ Datos nuevos detectados: {nuevos_datos}")
            manejar_datos_usuario(user_id, nuevos_datos, session, current_app.db.usuarios, current_app.logger)
            enviar_a_pipedrive(user_id)

        # ✅ Cargar contexto del chatbot
        try:
            context_content = load_context_content(context_filename)
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 400

        # ✅ Generar respuesta con OpenAI
        messages = [{"role": "system", "content": context_content}] + chat_history
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=os.getenv('OPEN_API_MODEL', 'gpt-3.5-turbo'),
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        bot_response = response.choices[0].message.content

        # ✅ Guardar historial de conversación
        chat_history.append({"role": "user", "content": user_message})
        chat_history.append({"role": "assistant", "content": bot_response})
        current_app.db.chats.update_one(
            {"user_id": user_id, "session_id": session_id},
            {"$set": {"history": chat_history}},
            upsert=True
        )

        return jsonify({'response': bot_response}), 200

    except Exception as e:
        current_app.logger.error(f"❌ Error en /chat: {e}")
        return jsonify({'error': str(e)}), 500

from flask import request, jsonify

woocommerce_session = None  # Variable global para almacenar la sesión

@chat_bp.route('/sesion', methods=['POST'])
def recibir_sesion():
    if not request.json or 'wp_woocommerce_session' not in request.json:
        return jsonify({"error": "No se recibió sesión de WooCommerce"}), 400

    session['wp_woocommerce_session'] = request.json['wp_woocommerce_session']
    print("📡 Sesión de WooCommerce recibida:", session['wp_woocommerce_session'])  # Debugging

    return jsonify({"message": "Sesión guardada correctamente"}), 200

@chat_bp.route('/ver_sesion', methods=['GET'])
def ver_sesion():
    return jsonify({"wp_woocommerce_session": session.get('wp_woocommerce_session', 'No guardada')})

@chat_bp.route('/check_session', methods=['GET'])
def check_session():
    """
    Verifica si la sesión de WooCommerce está almacenada.
    """
    woocommerce_session = session.get('wp_woocommerce_session', None)
    if woocommerce_session:
        return jsonify({"message": "Sesión encontrada", "session": woocommerce_session}), 200
    else:
        return jsonify({"error": "No se encontró la sesión"}), 404
    
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
