"""Interface for external payment gateway."""

from abc import ABC, abstractmethod
from decimal import Decimal

from app.domain.models.payment import Currency, GatewayResult


class IPaymentGateway(ABC):
    """Port for an external payment processing gateway."""

    @abstractmethod
    async def process(
        self,
        *,
        amount: Decimal,
        currency: Currency,
    ) -> GatewayResult:
        """Process a payment charge and return the gateway result."""
        ...
