from flask import Blueprint, request, jsonify, current_app
import requests
import os
from openai import OpenAI
import uuid
from myapp.routes.chat import procesar_mensaje

from myapp.routes.chat import chat 

whatsapp_bp = Blueprint('whatsapp', __name__)

WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_VERIFY_TOKEN = "futurito123"

@whatsapp_bp.route('/whatsapp/webhook', methods=['POST'])
def receive_message():
    """Recibe mensajes de WhatsApp y los procesa con la lógica del chatbot"""
    data = request.get_json()
    print("📩 Mensaje recibido:", data)

    if "entry" in data:
        for entry in data["entry"]:
            for change in entry["changes"]:
                if "messages" in change["value"]:
                    for message in change["value"]["messages"]:
                        sender_number = message["from"]  
                        user_text = message["text"]["body"]

                        user_id = sender_number  
                        session_id = f"whatsapp_{user_id}_{uuid.uuid4().hex[:8]}"  # 🔥 Evita colisiones de sesión

                        print(f"🆔 Nuevo mensaje de {user_id} con session_id {session_id}")

                        response_data = procesar_mensaje(user_text, "robota-context", user_id, session_id)
                        bot_response = response_data.get("response", "No se pudo procesar tu mensaje.")

                        print(f"🛠️ Mensaje procesado para {user_id}: {bot_response}")

                        send_whatsapp_message(sender_number, bot_response)

    return jsonify({"status": "received"}), 200


def send_whatsapp_message(phone, message):
    """Envía un mensaje de WhatsApp usando la API de Meta"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {"messaging_product": "whatsapp", "to": phone, "text": {"body": message}}

    response = requests.post(url, json=payload, headers=headers)
    print(f"📤 Respuesta enviada a {phone}: {response.json()}")

@whatsapp_bp.route('/whatsapp/webhook', methods=['GET'])
def verify():
    """Verificación inicial del webhook de Meta"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return challenge, 200  
    return "Forbidden", 403  
