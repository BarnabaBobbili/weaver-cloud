"""
Minimal asyncpg connection test — tries multiple configurations.
Run: python test_db_conn.py
"""
import asyncio
import ssl
import asyncpg


async def try_connect(label: str, **kwargs):
    print(f"\n[{label}] Trying...")
    try:
        conn = await asyncpg.connect(**kwargs)
        result = await conn.fetchval("SELECT version()")
        print(f"[{label}] SUCCESS: {result[:60]}")
        await conn.close()
        return True
    except Exception as e:
        print(f"[{label}] FAILED: {type(e).__name__}: {e}")
        return False


async def main():
    print(f"asyncpg version: {asyncpg.__version__}")

    base = dict(
        host="aws-1-ap-south-1.pooler.supabase.com",
        user="postgres.fnurcwzctcgeusvxcrjn",
        password="Barnaba130702",
        database="postgres",
    )

    # 1. Transaction pooler (port 6543) — ssl="require" (no cert verification)
    await try_connect("pooler-6543-ssl-require", **base, port=6543, ssl="require")

    # 2. Transaction pooler (port 6543) — no SSL
    await try_connect("pooler-6543-no-ssl", **base, port=6543)

    # 3. Direct connection (port 5432) — ssl="require"
    base_direct = {**base, "host": "aws-1-ap-south-1.pooler.supabase.com"}
    await try_connect("direct-5432-ssl-require", **base_direct, port=5432, ssl="require")

    # 4. Transaction pooler with full SSL context
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    await try_connect("pooler-6543-ssl-ctx", **base, port=6543, ssl=ctx)


asyncio.run(main())
