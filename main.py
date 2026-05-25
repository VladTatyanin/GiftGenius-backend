import asyncio
from rag.chain import get_rag_chain, clear_memory

async def main():
    chain = get_rag_chain(session_id="user_123", temperature=0.85)

    while True:
        question = input("\nЧто ищем? ")

        if question.lower() == '/exit':
            break
        elif question.lower() == '/clear':
            chain.clear_memory()
            print("История очищена!")
            continue
        elif not question.strip():
            continue

        result = await chain.generate_gift_ideas(question)
        print(f"\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())