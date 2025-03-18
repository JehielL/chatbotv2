import re
import difflib
from myapp.services.woocomerce_service import obtener_productos, obtener_productos_con_categorias


regex_patterns = {
    'nombre': re.compile(r'(?i)(?:mi nombre es|soy|me llamo|mi nombre)\s+([A-ZÁÉÍÓÚÜÑa-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑa-záéíóúüñ]+)*)'),
    'telefono': re.compile(r'(\+?\d{1,4}[-.\s]?\(?\d{1,}\)?[-.\s]?\d{1,}[-.\s]?\d{1,}[-.\s]?\d{1,})'),
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    'empresa': re.compile(r'(?i)(?:trabajo en|empresa es|soy de)\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ0-9\s&.,-]{3,})'),
    'motivo_visita': re.compile(r'(?i)(?:visitar|visita|reunirme con| conocer| me interesa | quiero saber | conocer )\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ0-9\s&.,-]{3,})'),
    'intencion': re.compile(r'\b(agregar|añadir|comprar|compra(r)?|carrito|ver carrito|mostrar carrito|pagar|finalizar compra|checkout)\b', re.IGNORECASE),
    'cantidad': re.compile(r'\b(\d+)\b', re.IGNORECASE)  # ✅ Solo detecta números
}

def normalizar_texto(texto):
    """ Convierte texto en minúsculas, quita caracteres especiales y reemplaza guiones por espacios. """
    return texto.lower().replace("-", " ").replace("&", " y ").replace(",", "").strip()

def detectar_producto_y_cantidad(mensaje):
    """
    Detecta la intención del usuario, el producto, la cantidad y la categoría en el mensaje.
    Retorna: {"intencion": "agregar", "producto_id": 101, "cantidad": 2, "categoria": "robots"}
    """
    mensaje = normalizar_texto(mensaje)  # ✅ Normalizar el mensaje del usuario

    # 🔍 Obtener productos con categorías
    productos_disponibles = obtener_productos_con_categorias()

    # 📌 Debug: Mostrar qué productos está obteniendo WooCommerce
    print(f"🔍 Productos obtenidos: {productos_disponibles.keys()}")

    # 🔍 Detectar intención
    intencion_match = regex_patterns["intencion"].search(mensaje)
    intencion = intencion_match.group(1).lower() if intencion_match else None

    # 🔍 Buscar producto en la lista de productos dinámicos usando `difflib`
    producto_id = None
    categoria = None
    producto_detectado = None

    # 🔎 Verificar coincidencia exacta primero
    producto_cercano = encontrar_producto_mas_cercano(mensaje, productos_disponibles)
    if producto_cercano:
        producto_id, categoria = productos_disponibles[producto_cercano]
        producto_detectado = producto_cercano


    # 🔎 Si no se encontró coincidencia exacta, usar `difflib`
    if not producto_id:
        producto_cercano = encontrar_producto_mas_cercano(mensaje, productos_disponibles)
        if producto_cercano:
            producto_id, categoria = productos_disponibles[producto_cercano]
            producto_detectado = producto_cercano

    # 🔍 Detectar cantidad correctamente
    cantidad = 1  # Por defecto 1
    cantidad_match = regex_patterns["cantidad"].search(mensaje)
    if cantidad_match:
        cantidad = int(cantidad_match.group(1))  # Extraer solo el número

    # 🛠️ Log para depuración final
    print(f"✅ Producto detectado: {producto_detectado} (ID: {producto_id}, Categoría: {categoria}), Cantidad: {cantidad}")

    return {
        "intencion": intencion,
        "producto_id": producto_id,
        "cantidad": cantidad,
        "categoria": categoria
    }

import difflib  # 📌 Para buscar coincidencias similares

def encontrar_producto_mas_cercano(mensaje, productos_disponibles):
    """ Encuentra el producto más parecido al mensaje del usuario. """
    nombres_productos = list(productos_disponibles.keys())  # Extrae los nombres de los productos
    coincidencias = difflib.get_close_matches(mensaje, nombres_productos, n=1, cutoff=0.5)

    if coincidencias:
        return coincidencias[0]  # Devuelve el producto más parecido encontrado
    return None

def detectar_datos_usuario(mensaje):
    """ Detecta datos personales del usuario en el mensaje """
    datos = {}
    for campo, patron in regex_patterns.items():
        matches = patron.findall(mensaje)
        if matches:
            # ✅ Si la coincidencia es una tupla, la convertimos en una cadena
            if isinstance(matches[0], tuple):
                matches = [" ".join(match).strip() for match in matches]

            if campo in ['nombre', 'empresa', 'motivo_visita']:
                datos[campo] = matches[-1].strip()
            else:
                datos[campo] = [match.replace(" ", "") for match in matches]
    return datos

