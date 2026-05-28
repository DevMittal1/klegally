import json
import asyncio
from redis.asyncio import Redis
from worker.handlers import SendWelcomeEmailHandler


async def process_single_message(
    message_id: str,
    payload: dict,
    handler: SendWelcomeEmailHandler,
) -> None:
    """
    Parses and handles a single message from the Redis Stream.
    Isolated try/except block decreases cognitive complexity nesting levels.
    """
    if "payload" not in payload:
        return

    try:
        task_payload = json.loads(payload["payload"])
        print(f"Received stream message [{message_id}]: {task_payload}")
        # Execute our decoupled business job handler
        await handler.handle(task_payload)
    except Exception as inner_ex:
        print(f"Error executing task payload on message [{message_id}]: {inner_ex}")


async def process_stream_response(
    response: list,
    handler: SendWelcomeEmailHandler,
) -> str:
    """
    Processes all messages from an xread response list and returns the last processed ID.
    Method extraction simplifies code reading flow.
    """
    last_id = "0-0"
    for stream, messages in response:
        for message_id, payload in messages:
            await process_single_message(message_id, payload, handler)
            last_id = message_id
    return last_id


async def run_worker(redis_client: Redis, handler: SendWelcomeEmailHandler) -> None:
    """
    Asynchronous Redis Streams worker poller.
    Reads from the 'email_tasks' stream and routes them to our job handler.
    """
    stream_key = "email_tasks"
    # Start polling from '0-0' to read all past messages, or '$' to read only new ones.
    last_id = "0-0"

    print(f"Async Redis worker started. Polling stream '{stream_key}' starting from offset '{last_id}'...")

    while True:
        try:
            # Poll one message at a time, blocking up to 2000ms if empty
            response = await redis_client.xread(
                streams={stream_key: last_id},
                count=1,
                block=2000
            )

            if not response:
                await asyncio.sleep(0.5)
                continue

            # Process messages through structured helpers, maintaining extremely low nesting
            processed_id = await process_stream_response(response, handler)
            if processed_id != "0-0":
                last_id = processed_id

        except Exception as e:
            print(f"Worker polling loop error: {e}. Retrying in 3 seconds...")
            await asyncio.sleep(3)
