import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Add local path and shared path to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/queue"))

from worker.handlers import SendWelcomeEmailHandler
from worker.infrastructure.email.interface import EmailProvider
from worker.infrastructure.email.mailjet import MailjetEmailProvider


class MockEmailProvider(EmailProvider):
    async def send(self, to: str, subject: str, body: str) -> None:
        # Declared as a stub to satisfy Python's Abstract Base Class (ABC) contract.
        # This is programmatically overridden with an AsyncMock in __init__ for assertions.
        pass

    def __init__(self):
        # Override the method with an AsyncMock for assertions
        self.send = AsyncMock()


async def test_welcome_email_handler():
    print("Testing SendWelcomeEmailHandler (decoupled job logic)...")
    
    # 1. Initialize mock provider and job handler (Dependency Injection)
    mock_provider = MockEmailProvider()
    handler = SendWelcomeEmailHandler(mock_provider)

    # 2. Define valid inbound payload corresponding to WelcomeEmailEvent schema
    payload = {
        "user_id": "user_abc123",
        "email": "test_recipient@klegally.com"
    }

    # 3. Invoke handler
    await handler.handle(payload)

    # 4. Verify provider was called with correct arguments
    mock_provider.send.assert_called_once()
    kwargs = mock_provider.send.call_args[1]
    assert kwargs["to"] == "test_recipient@klegally.com"
    assert "Welcome to KLegally!" in kwargs["subject"]
    assert "user_abc123" in kwargs["body"]
    print("Email Provider assertions verified successfully!")
    print("Job handler is fully transport-independent and handles tasks perfectly!")


async def test_mailjet_email_provider():
    print("Testing MailjetEmailProvider (async thread pool wrapper logic)...")
    
    # Mock Mailjet REST client instances
    mock_client_instance = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client_instance.send.create.return_value = mock_response

    with patch("worker.infrastructure.email.mailjet.Client", return_value=mock_client_instance):
        provider = MailjetEmailProvider(
            api_key_public="mock_pub",
            api_key_private="mock_priv",
            sender_email="verified@example.com"
        )
        
        await provider.send(
            to="user@example.com",
            subject="Hello",
            body="Test email"
        )
        
        # Verify Mailjet send call was made inside thread pool
        mock_client_instance.send.create.assert_called_once()
        kwargs = mock_client_instance.send.create.call_args[1]
        assert "Messages" in kwargs["data"]
        msg = kwargs["data"]["Messages"][0]
        assert msg["From"]["Email"] == "verified@example.com"
        assert msg["To"][0]["Email"] == "user@example.com"
        assert msg["Subject"] == "Hello"
        assert msg["TextPart"] == "Test email"
        print("Mailjet provider schema assertions verified successfully!")


async def run_all_tests():
    await test_welcome_email_handler()
    print("-" * 60)
    await test_mailjet_email_provider()
    print("All worker tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
