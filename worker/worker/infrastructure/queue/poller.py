import json
import asyncio
from redis.asyncio import Redis
from worker.handlers import SendWelcomeEmailHandler
from worker.ingestion import DocumentIngestionPipeline
from shared_queue import QueueService, DocumentStatus


async def process_single_message(
    message_id: str,
    payload: dict,
    handler: SendWelcomeEmailHandler,
) -> None:
    """
    Parses and handles a single message from the Redis Stream for welcome email.
    """
    if "payload" not in payload:
        return

    try:
        task_payload = json.loads(payload["payload"])
        print(f"Received stream message [{message_id}]: {task_payload}")
        await handler.handle(task_payload)
    except Exception as inner_ex:
        print(f"Error executing task payload on message [{message_id}]: {inner_ex}")


async def process_stream_response(
    response: list,
    handler: SendWelcomeEmailHandler,
) -> str:
    """
    Processes all messages from an xread response list and returns the last processed ID.
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
    last_id = "0-0"

    print(f"Async Redis worker started. Polling stream '{stream_key}' starting from offset '{last_id}'...")

    while True:
        try:
            response = await redis_client.xread(
                streams={stream_key: last_id},
                count=1,
                block=2000
            )

            if not response:
                await asyncio.sleep(0.5)
                continue

            processed_id = await process_stream_response(response, handler)
            if processed_id != "0-0":
                last_id = processed_id

        except Exception as e:
            print(f"Worker polling loop error: {e}. Retrying in 3 seconds...")
            await asyncio.sleep(3)


async def _handle_ingestion_failure(
    stream: str,
    group: str,
    message_id: str,
    document_id: str,
    attempt: int,
    handler_err: Exception,
    queue_service: QueueService,
    redis_client: Redis,
    db,
) -> None:
    """
    Handles retries and dead letter queue routing when a processing stage fails.
    """
    if attempt < 3:
        next_attempt = attempt + 1
        print(f"[{group}] Scheduling retry {next_attempt}/3 for document '{document_id}'...")
        await queue_service.publish(
            stream,
            {"document_id": document_id, "attempt": next_attempt}
        )
    else:
        print(f"[{group}] Document '{document_id}' exceeded 3 attempts. Routing to DLQ stream 'document:failed'!")
        await queue_service.publish(
            "document:failed",
            {
                "document_id": document_id,
                "stage": group,
                "error": str(handler_err),
                "attempt": attempt
            }
        )
        # Mark database status as FAILED in MongoDB
        await db["documents"].update_one(
            {"_id": document_id},
            {"$set": {
                "status": DocumentStatus.FAILED.value,
                "error": str(handler_err)
            }}
        )

    # Acknowledge the failed message so it is removed from the pending entries list (PEL)
    await redis_client.xack(stream, group, message_id)


async def _process_ingestion_message(
    redis_client: Redis,
    stream: str,
    group: str,
    message_id: str,
    payload: dict,
    handler_coro,
    queue_service: QueueService,
    db,
) -> None:
    """
    Executes and acknowledges a single document ingestion stream task.
    """
    if "payload" not in payload:
        # Malformed stream payload, acknowledge immediately to clear it
        await redis_client.xack(stream, group, message_id)
        return

    document_id = "unknown"
    attempt = 1
    try:
        task_payload = json.loads(payload["payload"])
        document_id = task_payload.get("document_id")
        attempt = task_payload.get("attempt", 1)

        print(f"[{group}] Received document ingestion event for ID '{document_id}' (attempt {attempt}/3)")

        # Route to our high-fidelity async pipeline handler stage
        await handler_coro(document_id)

        # Acknowledge the message upon successful execution
        await redis_client.xack(stream, group, message_id)
        print(f"[{group}] Successfully completed and acknowledged message [{message_id}] for document '{document_id}'.")

    except Exception as handler_err:
        print(f"[{group}] Critical handler failure on document '{document_id}': {handler_err}")
        await _handle_ingestion_failure(
            stream=stream,
            group=group,
            message_id=message_id,
            document_id=document_id,
            attempt=attempt,
            handler_err=handler_err,
            queue_service=queue_service,
            redis_client=redis_client,
            db=db,
        )


async def poll_stream_group(
    redis_client: Redis,
    stream: str,
    group: str,
    consumer_name: str,
    handler_coro,
    queue_service: QueueService,
    db,
) -> None:
    """
    Polls a specific Redis Stream with a Consumer Group, executes the handler coroutine,
    handles ACKs, automatic retries (up to 3), and routes persistent failures to Dead Letter queue.
    """
    print(f"[Worker] Starting consumer group worker on stream '{stream}' with group '{group}'...")

    # Ensure the consumer group exists
    try:
        await queue_service.create_consumer_group(stream, group)
    except Exception as e:
        print(f"[Worker] Group setup note: {e}")

    while True:
        try:
            # Block up to 2000ms, reading 1 unread message (">")
            response = await redis_client.xreadgroup(
                groupname=group,
                consumername=consumer_name,
                streams={stream: ">"},
                count=1,
                block=2000
            )

            if not response:
                await asyncio.sleep(0.5)
                continue

            for stream_name, messages in response:
                for message_id, payload in messages:
                    await _process_ingestion_message(
                        redis_client=redis_client,
                        stream=stream,
                        group=group,
                        message_id=message_id,
                        payload=payload,
                        handler_coro=handler_coro,
                        queue_service=queue_service,
                        db=db,
                    )

        except Exception as e:
            print(f"[{group}] Exception in stream poller loop: {e}. Retrying in 3 seconds...")
            await asyncio.sleep(3)


async def run_ingestion_workers(
    redis_client: Redis,
    pipeline: DocumentIngestionPipeline,
    queue_service: QueueService,
    db,
) -> None:
    """
    Spawns concurrent background poller tasks for the full ingestion pipeline:
    - Parsing Workers (document:parse stream)
    - Chunk Workers (document:chunk stream)
    - Embedding Workers (document:embed stream)
    """
    print("[Worker] Spawning concurrent async document ingestion pipelines...")

    # Spawn 3 concurrent tasks to poll each stream concurrently
    parse_task = asyncio.create_task(
        poll_stream_group(
            redis_client=redis_client,
            stream="document:parse",
            group="parse-group",
            consumer_name="parse-consumer-1",
            handler_coro=pipeline.parse_document,
            queue_service=queue_service,
            db=db,
        )
    )

    chunk_task = asyncio.create_task(
        poll_stream_group(
            redis_client=redis_client,
            stream="document:chunk",
            group="chunk-group",
            consumer_name="chunk-consumer-1",
            handler_coro=pipeline.chunk_document,
            queue_service=queue_service,
            db=db,
        )
    )

    embed_task = asyncio.create_task(
        poll_stream_group(
            redis_client=redis_client,
            stream="document:embed",
            group="embed-group",
            consumer_name="embed-consumer-1",
            handler_coro=pipeline.embed_document,
            queue_service=queue_service,
            db=db,
        )
    )

    # Let them run in the background
    await asyncio.gather(parse_task, chunk_task, embed_task)
