# myapp/routes/usuarios.py
from flask import Blueprint, request, jsonify, current_app
from myapp.services.ml_service import entrenar_modelo

usuarios_bp = Blueprint('usuarios', __name__)

@usuarios_bp.route('/', methods=['POST'])
def obtener_usuarios():
    try:
        usuarios = list(current_app.db.usuarios.find({}, {'_id': 0}))
        return jsonify({'usuarios': usuarios})
    except Exception as e:
        current_app.logger.error(f"Error en el endpoint /usuarios: {e}")
        return jsonify({"error": str(e)}), 500

@usuarios_bp.route('/entrenar_modelo', methods=['POST'])
def entrenar_endpoint():
    try:
        modelo, encoder = entrenar_modelo()
        if modelo:
            return jsonify({"message": "Modelo entrenado exitosamente"})
        return jsonify({"message": "No hay suficientes datos para entrenar el modelo"}), 400
    except Exception as e:
        current_app.logger.error(f"Error en el endpoint /entrenar_modelo: {e}")
        return jsonify({"error": str(e)}), 500
