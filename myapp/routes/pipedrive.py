# myapp/routes/pipedrive.py
from flask import Blueprint, request, jsonify, current_app
from myapp.services.pipedrive_service import create_person, update_deal

pipedrive_bp = Blueprint('pipedrive', __name__)

@pipedrive_bp.route('/upload', methods=['POST'])
def upload_to_pipedrive():
    """
    Este endpoint extrae la información del usuario captada por el chatbot, que se ha
    almacenado en la colección 'usuarios', y la sube a Pipedrive.
    
    Se espera recibir un JSON con las siguientes claves:
      - user_id: El identificador del usuario (para buscar los datos en la DB)
      - dealId: El ID del negocio (deal) existente en Pipedrive donde se desea asociar la persona
      - motivovisita: El motivo de la visita (que se usará, por ejemplo, para actualizar el título del deal)
    
    Los datos del usuario (como nombre, correo, teléfono, etc.) se extraen de la colección 'usuarios'.
    """
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "No se proporcionó user_id"}), 400

        # Obtén los datos del usuario de la colección 'usuarios'
        usuario = current_app.db.usuarios.find_one({"user_id": user_id}, {"_id": 0})
        if not usuario:
            return jsonify({"error": "No se encontraron datos para el usuario"}), 404

        # Prepara los datos para crear la persona en Pipedrive
        person_data = {
            "name": usuario.get("nombre") or usuario.get("nombreCliente"),
            "email": usuario.get("email") or usuario.get("correoElectronico"),
            "phone": usuario.get("telefono")
        }
        person_response = create_person(person_data)
        person_id = person_response.get("data", {}).get("id")
        if not person_id:
            raise Exception("No se pudo crear la persona en Pipedrive")

        # Obtén el ID del negocio (deal) y el motivo de la visita desde el request
        deal_id = data.get("dealId")
        if not deal_id:
            return jsonify({"error": "Falta el ID del negocio (dealId)"}), 400

        motivovisita = data.get("motivovisita") or data.get("motivoVisita")
        
        # Prepara los datos para actualizar el negocio: 
        # Se asocia la persona y se actualiza el título del deal con el motivo de la visita
        update_data = {
            "person_id": person_id,
            "title": motivovisita if motivovisita else "Nuevo Deal"
        }
        deal_response = update_deal(deal_id, update_data)

        return jsonify({
            "person": person_response,
            "deal": deal_response
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error subiendo datos a Pipedrive: {e}")
        return jsonify({"error": str(e)}), 500
