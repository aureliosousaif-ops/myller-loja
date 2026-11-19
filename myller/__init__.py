import os

from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env na raiz do projeto.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
