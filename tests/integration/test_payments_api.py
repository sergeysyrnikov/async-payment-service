"""Integration tests for the payments API."""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.services.payment_service import PaymentService
from app.domain.exceptions import EntityNotFoundError
from app.domain.models.payment import Currency, Payment, PaymentStatus

PAYMENT_BODY = {
    "amount": "100.50",
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {"order_id": "42"},
    "webhook_url": "https://example.com/webhook",
}


def make_persisted_payment(**overrides) -> Payment:
    """Build a payment as it looks right after creation."""
    defaults = dict(
        amount=Decimal("100.50"),
        currency=Currency.RUB,
        idempotency_key="idem-key-1",
        webhook_url="https://example.com/webhook",
        description="Test payment",
        metadata={"order_id": "42"},
        status=PaymentStatus.PENDING,
        id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Payment(**defaults)


def test_create_payment_returns_202(client: TestClient, container, auth_headers):
    """POST /payments returns 202 Accepted with payment_id, status and created_at."""
    payment = make_persisted_payment()
    mock_service = AsyncMock(spec=PaymentService)
    mock_service.create_payment = AsyncMock(return_value=payment)

    with container.payment_service.override(mock_service):
        response = client.post(
            "/api/v1/payments",
            json=PAYMENT_BODY,
            headers={**auth_headers, "Idempotency-Key": "idem-key-1"},
        )

    assert response.status_code == 202
    data = response.json()
    assert data["payment_id"] == str(payment.id)
    assert data["status"] == "pending"
    assert data["created_at"] is not None
    command = mock_service.create_payment.await_args.args[0]
    assert command.idempotency_key == "idem-key-1"
    assert command.amount == Decimal("100.50")
    assert command.currency is Currency.RUB
    assert command.webhook_url == "https://example.com/webhook"


def test_create_payment_requires_idempotency_key(client: TestClient, container, auth_headers):
    """Missing Idempotency-Key header is rejected with 422."""
    response = client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers=auth_headers,
    )

    assert response.status_code == 422


def test_create_payment_rejects_empty_idempotency_key(client: TestClient, auth_headers):
    """An empty or whitespace-only Idempotency-Key is rejected with 400."""
    for key in ("", "   "):
        response = client.post(
            "/api/v1/payments",
            json=PAYMENT_BODY,
            headers={**auth_headers, "Idempotency-Key": key},
        )
        assert response.status_code == 400


def test_create_payment_rejects_non_positive_amount(client: TestClient, auth_headers):
    """A negative or zero amount fails validation (going below zero is not allowed)."""
    for amount in ("-10.00", "0"):
        response = client.post(
            "/api/v1/payments",
            json={**PAYMENT_BODY, "amount": amount},
            headers={**auth_headers, "Idempotency-Key": f"key-{amount}"},
        )
        assert response.status_code == 422


def test_get_payment_returns_details(client: TestClient, container, auth_headers):
    """GET /payments/{id} returns the full payment details."""
    payment = make_persisted_payment()
    mock_service = AsyncMock(spec=PaymentService)
    mock_service.get_payment = AsyncMock(return_value=payment)

    with container.payment_service.override(mock_service):
        response = client.get(f"/api/v1/payments/{payment.id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["payment_id"] == str(payment.id)
    assert data["status"] == "pending"
    assert data["amount"] == "100.50"
    assert data["currency"] == "RUB"
    assert data["idempotency_key"] == "idem-key-1"
    assert data["webhook_url"] == "https://example.com/webhook"
    assert data["metadata"] == {"order_id": "42"}


def test_get_payment_not_found(client: TestClient, container, auth_headers):
    """Unknown payment id: 404 with the PAYMENT_NOT_FOUND error code."""
    mock_service = AsyncMock(spec=PaymentService)
    mock_service.get_payment = AsyncMock(
        side_effect=EntityNotFoundError(message="Payment not found", code="PAYMENT_NOT_FOUND"),
    )

    with container.payment_service.override(mock_service):
        response = client.get(f"/api/v1/payments/{uuid4()}", headers=auth_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PAYMENT_NOT_FOUND"


def test_endpoints_require_api_key(client: TestClient, container):
    """Without X-API-Key all endpoints respond 401."""
    assert client.get("/api/v1/").status_code == 401
    assert client.get("/api/v1/health/").status_code == 401
    assert client.get(f"/api/v1/payments/{uuid4()}").status_code == 401
    assert (
        client.post(
            "/api/v1/payments",
            json=PAYMENT_BODY,
            headers={"Idempotency-Key": "idem-key-1"},
        ).status_code
        == 401
    )


def test_endpoints_reject_wrong_api_key(client: TestClient, auth_headers):
    """A wrong X-API-Key is rejected with 401."""
    response = client.get("/api/v1/", headers={"X-API-Key": "wrong-key"})

    assert response.status_code == 401
