from shared_queue import WelcomeEmailEvent
from worker.infrastructure.email.interface import EmailProvider


class SendWelcomeEmailHandler:
    def __init__(self, email_provider: EmailProvider):
        self.email_provider = email_provider

    async def handle(self, payload: dict) -> None:
        """
        Processes a welcome email event.
        Validates the event schema first for predictable, stable consumption.
        """
        # Validate task payload using our unified event schema
        event = WelcomeEmailEvent(**payload)

        subject = "Welcome to KLegally!"
        body = (
            f"Hello and welcome to KLegally!\n\n"
            f"Your account (User ID: {event.user_id}) has been successfully created.\n"
            f"We are excited to have you on board!\n\n"
            f"Best regards,\nThe KLegally Team"
        )

        await self.email_provider.send(
            to=str(event.email),
            subject=subject,
            body=body,
        )
