import re

regex_patterns = {
    'nombre': re.compile(r'(?i)(?:mi nombre es|soy|me llamo|mi nombre)\s+([A-ZÁÉÍÓÚÜÑa-záéíóúüñ]+(?:\s+[A-ZÁÉÍÓÚÜÑa-záéíóúüñ]+)*)'),
    'telefono': re.compile(r'(\+?\d{1,4}[-.\s]?\(?\d{1,}\)?[-.\s]?\d{1,}[-.\s]?\d{1,}[-.\s]?\d{1,})'),
    'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    'empresa': re.compile(r'(?i)(?:trabajo en|empresa es|soy de)\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ0-9\s&.,-]{3,})'),
    'motivo_visita': re.compile(r'(?i)(?:visitar|visita|reunirme con| conocer| me interesa | quiero saber | conocer )\s+([A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ0-9\s&.,-]{3,})')
}

def detectar_datos_usuario(mensaje):
    datos = {}
    for campo, patron in regex_patterns.items():
        matches = patron.findall(mensaje)
        if matches:
            if campo in ['nombre', 'empresa', 'motivo_visita']:
                datos[campo] = matches[-1].strip()
            else:
                datos[campo] = [match.replace(" ", "") for match in matches]
    return datos
