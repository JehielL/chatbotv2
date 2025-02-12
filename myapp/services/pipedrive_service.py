import os
import requests

# Lee las variables de entorno
PIPEDRIVE_API_TOKEN = os.getenv("PIPEDRIVE_API_TOKEN")
PIPEDRIVE_BASE_URL = "https://api.pipedrive.com/v1"  # URL base de la API de Pipedrive

def create_person(person_data):
    """
    Crea una persona en Pipedrive.
    
    person_data: diccionario con la información de la persona.
    Ejemplo:
      {
         "name": "Juan Perez",
         "email": "juan@example.com",
         "phone": "1234567890"
      }
    """
    url = f"{PIPEDRIVE_BASE_URL}/persons?api_token={PIPEDRIVE_API_TOKEN}"
    response = requests.post(url, json=person_data)
    response.raise_for_status()
    return response.json()

def update_deal(deal_id, update_data):
    """
    Actualiza un negocio (deal) en Pipedrive.
    
    deal_id: ID del negocio a actualizar.
    update_data: diccionario con la información a actualizar.
    """
    url = f"{PIPEDRIVE_BASE_URL}/deals/{deal_id}?api_token={PIPEDRIVE_API_TOKEN}"
    response = requests.put(url, json=update_data)
    response.raise_for_status()
    return response.json()

def create_deal(deal_data):
    """
    Crea un nuevo negocio (deal) en Pipedrive.
    
    deal_data: diccionario con la información del negocio.
    Ejemplo:
      {
         "title": "Motivo Visita: Consulta de gadgets",
         "pipeline_id": 6,  # ID del pipeline en Pipedrive donde se creará el deal
         "person_id": 123   # (Opcional) si se quiere asociar inmediatamente la persona
      }
    """
    url = f"{PIPEDRIVE_BASE_URL}/deals?api_token={PIPEDRIVE_API_TOKEN}"
    response = requests.post(url, json=deal_data)
    response.raise_for_status()
    return response.json()
