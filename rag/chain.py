import json
import re
import asyncio
from typing import Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

import config
from rag.llm import get_llm
from rag.prompts import get_free_generation_prompt, get_gift_search_prompt


class SimpleMemory:
    def __init__(self):
        self.messages = []

    def add_user_message(self, content: str):
        self.messages.append(("user", content))

    def add_ai_message(self, content: str):
        self.messages.append(("assistant", content))

    def format_for_prompt(self, limit: int = 10) -> str:
        recent = self.messages[-limit * 2:] if self.messages else []
        if not recent:
            return "Нет истории"

        formatted = []
        for role, content in recent:
            role_name = "Пользователь" if role == "user" else "Ассистент"
            formatted.append(f"{role_name}: {content}")

        return "\n".join(formatted)

    def clear(self):
        self.messages = []


user_sessions = {}


async def invoke_with_retry(chain, input_data, max_retries=3, delay=2):
    """Вызов с повторными попытками при rate limit"""
    for attempt in range(max_retries):
        try:
            return await chain.ainvoke(input_data)
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "timeout" in error_str:
                if attempt < max_retries - 1:
                    wait = delay * (2 ** attempt)
                    print(f"Rate limit, retrying in {wait}s... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait)
                    continue
            raise e
    raise Exception("Max retries exceeded")


class GiftGeneratorChain:
    def __init__(self, session_id: str = 'default'):
        self.session_id = session_id
        self.llm = None
        self.memory = None

    def initialize(self, temperature: float = 0.85):
        self.llm = get_llm(
            config.TOKEN,
            temperature=temperature,
            max_tokens_output=1000
        )

        if self.session_id not in user_sessions:
            user_sessions[self.session_id] = SimpleMemory()
        self.memory = user_sessions[self.session_id]

        self.generation_prompt = ChatPromptTemplate.from_template(
            get_free_generation_prompt()
        )
        self.parser_prompt = ChatPromptTemplate.from_template(
            get_gift_search_prompt()
        )

        self.parse_chain = self.parser_prompt | self.llm | StrOutputParser()
        self.generate_chain = self.generation_prompt | self.llm | StrOutputParser()

        print(f"GiftGenerator initialized for session {self.session_id}")

    async def generate_gift_ideas(self, question: str) -> Dict:
        params = await self._extract_params(question)
        answer = await self._generate_free(question, params)

        self.memory.add_user_message(question)
        self.memory.add_ai_message(answer)

        return {
            "question": question,
            "params": params,
            "answer": answer,
            "session_id": self.session_id
        }

    async def _extract_params(self, question: str) -> Dict:
        """Извлечение параметров через LLM + fallback на regex"""

        try:
            result = await invoke_with_retry(
                self.parse_chain,
                {"question": question}
            )

            print(f"Parser output: {result[:200]}...")

            # Очистка
            result = result.strip()

            # Удаляем markdown блоки
            if '```json' in result:
                result = result.split('```json')[1].split('```')[0]
            elif '```' in result:
                result = result.split('```')[1].split('```')[0]

            result = result.strip()

            # Ищем JSON
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                result = json_match.group()

            params = json.loads(result)

            return {
                "interests": params.get('interests') or [],
                "budget_min": params.get('budget_min'),
                "budget_max": params.get('budget_max'),
                "recipient": params.get('recipient'),
                "occasion": params.get('occasion')
            }

        except Exception as e:
            print(f"⚠️ JSON parsing failed: {e}, using regex fallback")
            return self._extract_params_regex(question)

    def _extract_params_regex(self, question: str) -> Dict:
        """Извлечение параметров через regex"""

        q = question.lower()
        params = {
            "interests": [],
            "budget_min": None,
            "budget_max": None,
            "recipient": None,
            "occasion": None
        }

        # Бюджет
        patterns = [
            (r'до\s*(\d+)', 'max'),
            (r'от\s*(\d+)', 'min'),
            (r'(\d+)\s*-\s*(\d+)', 'range'),
            (r'(\d+)\s*руб', 'approx')
        ]

        for pattern, ptype in patterns:
            match = re.search(pattern, q)
            if match:
                if ptype == 'max':
                    params["budget_max"] = int(match.group(1))
                elif ptype == 'min':
                    params["budget_min"] = int(match.group(1))
                elif ptype == 'range':
                    params["budget_min"] = int(match.group(1))
                    params["budget_max"] = int(match.group(2))
                elif ptype == 'approx':
                    val = int(match.group(1))
                    params["budget_min"] = val
                    params["budget_max"] = val
                break

        # Получатель
        recipients = ["брат", "сестра", "мама", "папа", "друг", "подруга", "девушка", "парень", "жена", "муж",
                      "коллега"]
        for rec in recipients:
            if rec in q:
                params["recipient"] = rec
                break

        # Повод
        occasions = ["день рождения", "новый год", "8 марта", "23 февраля"]
        for occ in occasions:
            if occ in q:
                params["occasion"] = occ
                break

        # Интересы
        interests_map = {
            "игры": ["геймер", "игры", "компьютер", "ps5", "xbox"],
            "спорт": ["спорт", "фитнес", "бег", "тренажер"],
            "книги": ["книги", "читает", "литература"],
            "техника": ["техника", "гаджеты", "смартфон", "ноутбук"],
            "кулинария": ["кулинария", "готовит", "выпечка"],
            "путешествия": ["путешествия", "туры", "отпуск"]
        }

        for interest, keywords in interests_map.items():
            if any(kw in q for kw in keywords):
                params["interests"].append(interest)

        return params

    async def _generate_free(self, question: str, params: Dict) -> str:
        interests = params.get('interests', []) or []
        if isinstance(interests, str):
            interests = [interests]
        interests_str = ', '.join(interests) if interests else 'не указаны'

        budget_min = params.get('budget_min')
        budget_max = params.get('budget_max')

        if budget_min is None and budget_max is None:
            budget_str = "любой"
        elif budget_min is None:
            budget_str = f"до {budget_max}"
        elif budget_max is None:
            budget_str = f"от {budget_min}"
        else:
            budget_str = f"{budget_min} - {budget_max}"

        recipient = params.get('recipient') or 'не указан'
        occasion = params.get('occasion') or 'не указан'
        history = self.memory.format_for_prompt(config.MAX_CONVERSATION_HISTORY)

        response = await invoke_with_retry(
            self.generate_chain,
            {
                "question": question,
                "interests": interests_str,
                "budget_min": budget_min if budget_min else "любой",
                "budget_max": budget_max if budget_max else "любой",
                "budget_str": budget_str,
                "recipient": recipient,
                "occasion": occasion,
                "chat_history": history
            }
        )

        return response

    def clear_memory(self):
        self.memory.clear()
        print(f"Cleared memory for session {self.session_id}")


def get_rag_chain(session_id: str = 'default', **kwargs) -> GiftGeneratorChain:
    chain = GiftGeneratorChain(session_id)
    chain.initialize(temperature=kwargs.get('temperature', 0.85))
    return chain


def clear_memory(session_id: str):
    if session_id in user_sessions:
        user_sessions[session_id].clear()