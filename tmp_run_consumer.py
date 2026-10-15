"""Temporary direct processing diagnostic (delete after run)."""

import asyncio
import uuid

from app.application.commands.payment_commands import ProcessPaymentCommand
from app.core.di.containers import Container

PAYMENT_ID = uuid.UUID("181958a1-263a-4fed-a45e-cdadbe068353")


async def main() -> None:
    container = Container()
    processor = container.payment_processor()
    try:
        await processor.process_payment(ProcessPaymentCommand(payment_id=PAYMENT_ID))
        print("PROCESS OK")
    except Exception:
        import traceback

        traceback.print_exc()


asyncio.run(main())
