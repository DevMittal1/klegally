import asyncio
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


password_hasher = PasswordHasher()


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(password_hasher.hash, password)


async def verify_password(
    password: str,
    hashed_password: str,
) -> bool:
    try:
        return await asyncio.to_thread(
            password_hasher.verify,
            hashed_password,
            password,
        )

    except VerifyMismatchError:
        return False
