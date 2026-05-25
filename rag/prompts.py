def get_free_generation_prompt() -> str:
    return """Ты эксперт по подаркам. Верни ответ ТОЛЬКО В ФОРМАТЕ JSON.

Вопрос: {question}

Формат ответа:
{{
    "gifts": [
        {{
            "name": "Название подарка",
            "price": 5000,
            "description": "Краткое описание почему подходит"
        }}
    ]
}}

Правила:
- 3-5 подарков
- Цена в рублях
- Описание короткое (10-30 слов)

Твой ответ (только JSON, без лишнего текста):"""


def get_gift_search_prompt() -> str:
    return """Извлеки параметры из вопроса. Верни ТОЛЬКО JSON.

Вопрос: {question}

Формат: {{"interests":["интерес1"],"budget_min":null,"budget_max":null,"recipient":null,"occasion":null}}

Пример: "подарок брату-геймеру до 5000" → {{"interests":["игры"],"budget_min":null,"budget_max":5000,"recipient":"брат","occasion":null}}

Твой ответ (только JSON):"""