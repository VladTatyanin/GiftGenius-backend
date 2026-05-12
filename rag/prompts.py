def get_free_generation_prompt() -> str:
    return """Ты креативный эксперт по выбору подарков.

Вопрос: {question}
Получатель: {recipient}
Повод: {occasion}
Интересы: {interests}
Бюджет: {budget_str} руб
История: {chat_history}

ПРАВИЛА:
- Придумывай ЛЮБЫЕ подарки (не ограничен базой)
- 3-5 идей
- Формат: 🎁 Название | 💰 Цена | 💡 Почему

ТВОЙ ОТВЕТ:"""


def get_gift_search_prompt() -> str:
    return """Извлеки параметры из вопроса. Верни ТОЛЬКО JSON.

Вопрос: {question}

Формат: {{"interests":["интерес1"],"budget_min":null,"budget_max":null,"recipient":null,"occasion":null}}

Пример: "подарок брату-геймеру до 5000" → {{"interests":["игры"],"budget_min":null,"budget_max":5000,"recipient":"брат","occasion":null}}

Твой ответ (только JSON):"""