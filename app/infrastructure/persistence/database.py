"""Database repository and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base

from app.core.config.database import DatabaseSettings

# Create base class for declarative models
Base = declarative_base()


class DatabaseManager:
    """Database connection manager with connection pooling."""

    def __init__(
        self,
        db_settings: DatabaseSettings,
    ) -> None:
        """Initialize database manager."""
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self.settings = db_settings

    @property
    def engine(self) -> AsyncEngine:
        """Get SQLAlchemy engine instance."""
        if not self._engine:
            self._engine = create_async_engine(
                str(self.settings.dsn),
                echo=self.settings.echo,
                pool_size=self.settings.pool_size,
                max_overflow=self.settings.max_overflow,
                pool_timeout=self.settings.pool_timeout,
                pool_recycle=self.settings.pool_recycle,
                pool_pre_ping=True,  # Enable connection health checks
            )
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get session factory for creating new database sessions."""
        if not self._session_factory:
            self._session_factory = async_sessionmaker[AsyncSession](
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session with automatic cleanup."""
        session: AsyncSession = self.session_factory()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def create_all(self) -> None:
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all(self) -> None:
        """Drop all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def dispose(self) -> None:
        """Dispose of the database engine and connection pool."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
