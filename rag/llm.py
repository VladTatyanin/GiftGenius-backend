from langchain_openai import ChatOpenAI
import config


def get_llm(api_key: str = None, temperature: float = 0.85, max_tokens_output: int = 1000):
    """Получение LLM через OpenRouter с повторными попытками"""

    llm = ChatOpenAI(
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        model_name=config.LLM_MODEL,
        temperature=temperature,
        max_tokens=max_tokens_output,
        default_headers={
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "GiftGenius"
        }
    )

    print(f"✅ Using OpenRouter model: {config.LLM_MODEL}")
    return llm