import os

modelo = "gpt-3-5-turbo-0125"

temperatura = 0

tokens_maximos_respuesta= 250

MAX_USER_MESSAGE_TOKENS = 700

direccion_api_docker = "/app/private/openai_api_key"

base_de_datos = "api-bd-1"

CONTEXT_DIR = os.path.join(os.path.dirname(__file__), "context")

