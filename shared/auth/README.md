# Shared Authentication Module (`shared-auth`)

A production-grade, highly secure, and event-loop-friendly shared authentication module for the **KLegally** microservices monorepo. This package is built using Python 3.12+, FastAPI, PyJWT, Argon2, and Pydantic Settings.

## 🛠️ Tech Stack & Features

- **Fully Asynchronous API**: All cryptographic and hashing functions are async-native.
- **Asymmetric Signature Verification (RS256)**: Implements RS256 algorithm with separate private (signing) and public (verifying) RSA keys.
- **Refresh Token Rotation (RTR)**: Support for generating and verifying long-lived refresh tokens with strict token-type checks.
- **Non-blocking Hashing**: Uses `asyncio.to_thread` for CPU-intensive Argon2 password operations, keeping your event loop completely responsive.
- **FastAPI User Dependency**: Clean dependency-injection pattern for route protection (`get_current_user`).
- **Thread-safe Request Context**: `AuthContextMiddleware` using Python's `contextvars` to access the authenticated user payload anywhere in the execution stack.

---

## 📂 Structure

```text
shared/
└── auth/
    ├── pyproject.toml
    ├── README.md
    └── auth/
        ├── __init__.py
        │
        ├── config.py
        ├── constants.py
        │
        ├── jwt/
        │   ├── __init__.py
        │   ├── access.py
        │   ├── verification.py
        │   └── schemas.py
        │
        ├── security/
        │   ├── __init__.py
        │   └── hashing.py
        │
        ├── dependencies/
        │   ├── __init__.py
        │   └── current_user.py
        │
        ├── middleware/
        │   ├── __init__.py
        │   └── auth_context.py
        │
        └── exceptions/
            ├── __init__.py
            └── auth.py
```

---

## ⚙️ Configuration & Setup

The package reads configuration from environment variables (or a local `.env` file). The following variables are required:

```ini
JWT_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----
<RSA 2048-bit Private Key>
-----END PRIVATE KEY-----"

JWT_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----
<RSA 2048-bit Public Key>
-----END PUBLIC KEY-----"

JWT_ALGORITHM="RS256"
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
JWT_ISSUER="auth-service"
JWT_AUDIENCE="api-gateway"
```

---

## 🚀 Installation

Inside any microservice (e.g., `api/`), simply add the shared package as a local dependency using `uv`:

```bash
uv add ../shared/auth
```

This updates your service's `pyproject.toml` automatically:
```toml
[project]
dependencies = [
    "shared-auth",
]

[tool.uv.sources]
shared-auth = { path = "../shared/auth" }
```

---

## 💡 Usage Examples

### 1. Router Protection via Dependency Injection

Use the standard `Depends(get_current_user)` inside your FastAPI routers:

```python
from fastapi import APIRouter, Depends
from auth.dependencies.current_user import get_current_user

router = APIRouter()

@router.get("/me")
async def me(current_user = Depends(get_current_user)):
    return {
        "user_id": current_user["sub"],
        "role": current_user["role"],
        "org_id": current_user["org_id"],
    }
```

### 2. Refresh Token Rotation

Create and exchange refresh tokens securely:

```python
from fastapi import APIRouter, HTTPException, status
from auth.jwt.access import create_access_token, create_refresh_token
from auth.jwt.verification import verify_refresh_token

router = APIRouter()

@router.post("/refresh")
async def refresh(refresh_token: str):
    # Verify the refresh token asynchronously
    payload = await verify_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Issue a new access token
    new_access = await create_access_token(
        user_id=payload["sub"],
        session_id=payload["sid"],
        org_id=payload["org_id"],
        role=payload["role"]
    )
    return {"access_token": new_access}
```

### 3. Context-based Authentication (Without Dependency Injection)

For service layers, databases, or utilities deep down the call stack where passing dependencies is tedious, use our **Context Propagation Middleware**:

**Add the middleware to your FastAPI app:**
```python
from fastapi import FastAPI
from auth.middleware.auth_context import AuthContextMiddleware

app = FastAPI()
app.add_middleware(AuthContextMiddleware)
```

**Retrieve authenticated user details anywhere:**
```python
from auth.middleware.auth_context import get_auth_context

def perform_db_query():
    # Access auth payload at any level of the call stack!
    user_context = get_auth_context()
    if user_context:
        print(f"Executing query for user: {user_context['sub']}")
```

### 4. Password Hashing and Verification (Async)

```python
from auth.security.hashing import hash_password, verify_password

# Hash a password asynchronously (non-blocking)
hashed = await hash_password("mypassword123")

# Verify password asynchronously
is_valid = await verify_password("mypassword123", hashed) # Returns True
```

---

## 🧪 Running Verification Tests

To verify password hashing, JWT access, and refresh token validation, run:

```bash
uv run python /Users/dev/.gemini/antigravity/brain/cc42c07d-8360-4b32-80e3-e3897437f613/scratch/test_auth.py
```
