from datetime import datetime

def manejar_datos_usuario(user_id, nuevos_datos, session, usuarios_collection, logger):
    """
    Acumula en la sesión los datos extraídos del mensaje del usuario.
    Cuando se tienen los campos requeridos ('nombre', 'email', 'motivo_visita'),
    guarda la información en MongoDB usando la colección usuarios.
    """
    if 'datos_acumulados' not in session:
        session['datos_acumulados'] = {}
        logger.info("📝 Inicializando datos acumulados en sesión")
    
    logger.info(f"🔍 Antes de actualizar, datos en sesión: {session.get('datos_acumulados', {})}")
    logger.info(f"🔄 Nuevos datos detectados: {nuevos_datos}")
    
    for campo, valor in nuevos_datos.items():
        if valor:
            if campo not in session['datos_acumulados']:
                session['datos_acumulados'][campo] = valor
                logger.info(f"✅ Campo actualizado en sesión: {campo} = {valor}")
            elif isinstance(session['datos_acumulados'][campo], list) and isinstance(valor, list):
                session['datos_acumulados'][campo].extend(valor)
    session.modified = True
    
    logger.info(f"🆕 Después de actualizar, datos en sesión: {session.get('datos_acumulados', {})}")
    
    campos_requeridos = ['nombre', 'email', 'motivo_visita']
    if all(campo in session['datos_acumulados'] for campo in campos_requeridos):
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
            logger.info(f"✅ Datos guardados en MongoDB: {usuario_final}")
            session.pop('datos_acumulados')
            session.modified = True
            logger.info("🗑️ Datos de sesión limpiados después de guardar.")
        except Exception as e:
            logger.error(f"❌ Error al guardar en MongoDB: {e}")
