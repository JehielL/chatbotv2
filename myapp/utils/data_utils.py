# myapp/utils/data_utils.py
from datetime import datetime

def manejar_datos_usuario(user_id, nuevos_datos, session, usuarios_collection, logger):
    """
    Actualiza en la sesión los datos extraídos del mensaje del usuario.
    Cuando se tienen los campos requeridos ('nombre', 'email', 'motivo_visita'),
    guarda la información en MongoDB usando la colección 'usuarios'.
    Se actualiza el valor existente con el nuevo, en caso de ser distinto.
    """
    # Inicializa el diccionario de datos si aún no existe
    if 'datos_acumulados' not in session:
        session['datos_acumulados'] = {}
        logger.info("Inicializando datos acumulados en sesión.")
    
    logger.info(f"Datos en sesión antes de actualizar: {session.get('datos_acumulados', {})}")
    logger.info(f"Datos nuevos detectados: {nuevos_datos}")
    
    for campo, valor in nuevos_datos.items():
        if valor:
            # Actualiza el valor con el nuevo, sin condicionar su existencia
            session['datos_acumulados'][campo] = valor
            logger.info(f"Campo '{campo}' actualizado a: {valor}")
    session.modified = True
    
    logger.info(f"Datos en sesión después de actualizar: {session.get('datos_acumulados', {})}")
    
    # Si se tienen los campos requeridos, se guarda en la colección 'usuarios'
    campos_requeridos = ['nombre', 'email', 'motivo_visita']
    if all(campo in session['datos_acumulados'] and session['datos_acumulados'][campo] for campo in campos_requeridos):
        try:
            usuario_final = {
                'user_id': user_id,
                **session['datos_acumulados'],
                'fecha_registro': datetime.utcnow()
            }
            usuarios_collection.update_one(
                {'user_id': user_id},
                {'$set': usuario_final},
                upsert=True
            )
            logger.info(f"Datos guardados en MongoDB: {usuario_final}")
            session.pop('datos_acumulados')
            session.modified = True
            logger.info("Datos de sesión limpiados después de guardar.")
        except Exception as e:
            logger.error(f"Error al guardar en MongoDB: {e}")
