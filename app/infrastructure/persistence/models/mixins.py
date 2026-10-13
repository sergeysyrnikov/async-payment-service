from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any, Callable, Generic, Self, TypeVar, cast
from uuid import UUID, uuid4

from sqlalchemy import DateTime, func
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

DomainT = TypeVar("DomainT")


class TimestampsMixin:
    """Reusable created/updated timestamps for persistence entities."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PrimaryKeyMixin:
    """Reusable primary key for persistence entities."""

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)


_TIMESTAMP_OMIT_IF_NONE: frozenset[str] = frozenset({"created_at", "updated_at"})


class DomainMappingMixin(Generic[DomainT]):
    """Generic ORM <-> domain mapping for dataclass-based domain models."""

    __domain_cls__: type[DomainT]
    __to_domain_converters__: dict[str, Callable[[Any], Any]] = {}
    __from_domain_converters__: dict[str, Callable[[Any], Any]] = {}

    @classmethod
    def _orm_primary_key_attribute_names(cls) -> frozenset[str]:
        """Return ORM attribute names for columns that are part of the primary key."""
        mapper = sa_inspect(cls)
        if mapper is None:
            msg = f"{cls.__name__} is not a mapped SQLAlchemy declarative class"
            raise TypeError(msg)
        return frozenset(col.key for col in mapper.columns if col.primary_key)

    @classmethod
    def _domain_field_names(cls) -> tuple[str, ...]:
        domain_cls = getattr(cls, "__domain_cls__", None)
        if domain_cls is None:
            raise AttributeError(f"{cls.__name__} must define __domain_cls__")

        if is_dataclass(domain_cls):
            return tuple(field.name for field in fields(domain_cls))

        annotations: dict[str, Any] = getattr(domain_cls, "__annotations__", None) or {}
        return tuple(cast(list[str], annotations.keys()))

    def to_domain(self) -> DomainT:
        """Convert ORM model to domain entity."""
        domain_cls: type[DomainT] = self.__class__.__domain_cls__
        converters = self.__class__.__to_domain_converters__

        kwargs: dict[str, Any] = {}
        for field_name in self.__class__._domain_field_names():
            value = getattr(self, field_name)
            converter = converters.get(field_name)
            if converter is not None:
                value = converter(value)
            kwargs[field_name] = value

        return domain_cls(**kwargs)

    @classmethod
    def from_domain(cls, domain_obj: DomainT) -> Self:
        """Convert domain entity to ORM model.

        Omits kwargs for primary-key attributes and created_at/updated_at when the
        domain value is None so ORM/database defaults (e.g. UUID, server_default) apply.
        """
        converters = cls.__from_domain_converters__
        pk_attrs = cls._orm_primary_key_attribute_names()

        kwargs: dict[str, Any] = {}
        for field_name in cls._domain_field_names():
            value = getattr(domain_obj, field_name)
            if value is None and (field_name in pk_attrs or field_name in _TIMESTAMP_OMIT_IF_NONE):
                continue
            converter = converters.get(field_name)
            if converter is not None:
                value = converter(value)
            kwargs[field_name] = value

        return cls(**kwargs)
