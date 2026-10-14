"""Payments API routes."""

from typing import Annotated
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path, status

from app.application.commands.payment_commands import CreatePaymentCommand
from app.application.services.payment_service import PaymentService
from app.core.di.containers import Container
from app.interfaces.api.dependencies import require_idempotency_key
from app.interfaces.api.schemas.payments import PaymentCreatedOutDto, PaymentInDto, PaymentOutDto

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post(
    "",
    response_model=PaymentCreatedOutDto,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Создать платёж",
    description="Принимает платёж в асинхронную обработку и возвращает 202 Accepted. "
    "Требует обязательный заголовок Idempotency-Key; повторный вызов с тем же ключом "
    "возвращает уже созданный платёж.",
)
@inject
async def create_payment(
    payment: PaymentInDto,
    idempotency_key: Annotated[str, Depends(require_idempotency_key)],
    service: Annotated[PaymentService, Depends(Provide[Container.payment_service])],
) -> PaymentCreatedOutDto:
    """Создаёт платёж и событие для обработки (outbox) в одной транзакции."""
    data = payment.model_dump()
    data["webhook_url"] = str(payment.webhook_url)
    command = CreatePaymentCommand(**data, idempotency_key=idempotency_key)
    created = await service.create_payment(command)
    return PaymentCreatedOutDto.from_domain(created)


@router.get(
    "/{payment_id}",
    response_model=PaymentOutDto,
    status_code=status.HTTP_200_OK,
    summary="Получить платёж",
    description="Возвращает детальную информацию о платеже по его идентификатору.",
)
@inject
async def get_payment(
    payment_id: Annotated[UUID, Path(description="Идентификатор платежа")],
    service: Annotated[PaymentService, Depends(Provide[Container.payment_service])],
) -> PaymentOutDto:
    """Возвращает полную информацию о платеже; 404 если платёж не найден."""
    payment = await service.get_payment(payment_id=payment_id)
    return PaymentOutDto.from_domain(payment)
