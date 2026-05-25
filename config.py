import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# API
TOKEN = os.getenv("OPENROUTER_TOKEN")

# Модель — стабильные варианты
LLM_MODEL = "baidu/cobuddy:free"

# Настройки
GENERATION_TEMPERATURE = 0.85
MAX_TOKENS_OUTPUT = 1000
MAX_CONVERSATION_HISTORY = 10
MEMORY_KEY = "chat_history"
