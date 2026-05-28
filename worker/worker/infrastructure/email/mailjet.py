import asyncio
from mailjet_rest import Client
from worker.infrastructure.email.interface import EmailProvider


class MailjetEmailProvider(EmailProvider):
    def __init__(self, api_key_public: str, api_key_private: str, sender_email: str):
        self.client = Client(
            auth=(api_key_public, api_key_private),
            version="v3.1"
        )
        self.sender_email = sender_email

    async def send(self, to: str, subject: str, body: str) -> None:
        """
        Sends an email using the Mailjet REST client.
        Runs asynchronously via asyncio.to_thread to keep the event loop responsive.
        """
        data = {
            "Messages": [
                {
                    "From": {
                        "Email": self.sender_email,
                        "Name": "KLegally Platform"
                    },
                    "To": [
                        {
                            "Email": to,
                            "Name": to.split("@")[0].capitalize()
                        }
                    ],
                    "Subject": subject,
                    "TextPart": body
                }
            ]
        }

        # Thread-pool execution for CPU/IO blocking synchronous API calls
        response = await asyncio.to_thread(self.client.send.create, data=data)
        
        # Mailjet v3.1 sends status 200 on success
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to send email via Mailjet. Status: {response.status_code}, Response: {response.json()}"
            )
        print(f"Email successfully sent via Mailjet to {to}!")
