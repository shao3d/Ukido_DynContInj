import asyncio
import json
from src.router import Router

async def test():
    router = Router()
    result = await router.route("Добрый день! У меня внучок очень застенчивый, боюсь ему будет трудно в группе", "test_user", [])
    print(json.dumps(result, ensure_ascii=False, indent=2))

asyncio.run(test())
