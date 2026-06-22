import asyncio
import redis.asyncio as redis

async def basic_example():
    r = redis.Redis(host='localhost', port=6379, decode_responses=True, password='qwerty')
    await r.set('foo', 'bar')
    value = await r.get('foo')
    print(value)
    # bar
    await r.aclose()

asyncio.run(basic_example())