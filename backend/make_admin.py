import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine("postgresql+asyncpg://postgres:Derly2020@localhost:5432/prescia_maps")
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE users SET is_admin = true WHERE email = 'apgrant719@gmail.com'"))
        result = await conn.execute(text("SELECT id, email, username, is_admin FROM users WHERE email = 'apgrant719@gmail.com'"))
        row = result.fetchone()
        print(f"Updated: {row}")
    await engine.dispose()

asyncio.run(main())
