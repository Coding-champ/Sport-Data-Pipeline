"""
Database Manager
Erweiterte Datenbankoperationen mit SQLAlchemy
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from src.core.config import settings
from src.database.schema import Base


class DatabaseManager:
    """Erweiterte Datenbankverwaltung mit SQLAlchemy und AsyncPG"""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self.pool = None  # AsyncPG Pool
        self.logger = logging.getLogger(__name__)

    def initialize_sync(self):
        """Initialisiert synchrone SQLAlchemy Engine und SessionFactory"""
        try:
            # Verwende den vollständigen DSN, wenn gesetzt, sonst fallback auf Komponenten
            database_url = settings.database_url
            # Falls der DSN den async-Treiber beinhaltet, für Sync-Engine auf psycopg2 umschalten
            if "+asyncpg" in database_url:
                database_url = database_url.replace("+asyncpg", "+psycopg2")
            # psycopg2 auf Windows: SSL und GSS deaktivieren, wenn nicht explizit gesetzt
            if "+psycopg2" in database_url:
                params_to_add = []
                if "sslmode=" not in database_url:
                    params_to_add.append("sslmode=disable")
                if "gssencmode=" not in database_url:
                    params_to_add.append("gssencmode=disable")
                if params_to_add:
                    sep = "&" if "?" in database_url else "?"
                    database_url = f"{database_url}{sep}{'&'.join(params_to_add)}"
            self.engine = create_engine(
                database_url,
                poolclass=QueuePool,
                pool_size=getattr(settings, "database_pool_size", 20),
                future=True,
            )
            self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
            # Leichter Verbindungscheck
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self.logger.info("Sync database engine initialized (SQLAlchemy)")
        except Exception as e:
            self.logger.error(f"Failed to initialize sync database: {e}")
            # Engine/SessionLocal auf None setzen, damit Aufrufer damit umgehen können
            self.engine = None
            self.SessionLocal = None
            raise

    async def initialize_async(self):
        """Initialisiert asynchronen asyncpg Pool auf Basis von DATABASE_URL"""
        try:
            dsn = settings.database_url
            # asyncpg erwartet postgresql:// ohne +asyncpg
            if "+asyncpg" in dsn:
                dsn = dsn.replace("+asyncpg", "")
            self.pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=getattr(settings, "database_pool_min_size", 10),
                max_size=getattr(settings, "database_pool_max_size", 20),
                command_timeout=60,
            )
            # Leichter Pool-Check
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            self.logger.info("Async database pool initialized (asyncpg)")
        except Exception as e:
            self.logger.error(f"Failed to initialize async database pool: {e}")
            self.pool = None
            raise

    async def initialize(self):
        """Initialisiert beide Verbindungstypen"""
        self.initialize_sync()
        await self.initialize_async()

    def get_session(self) -> Session:
        """Gibt eine neue SQLAlchemy Session zurück"""
        if not self.SessionLocal:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self.SessionLocal()

    @asynccontextmanager
    async def get_async_connection(self):
        """Context Manager für AsyncPG Verbindungen"""
        if not self.pool:
            raise RuntimeError("Async database pool not initialized")

        async with self.pool.acquire() as connection:
            yield connection

    async def execute_query(self, query: str, *args) -> list[dict]:
        """Führt eine Abfrage aus und gibt Ergebnisse zurück"""
        async with self.get_async_connection() as conn:
            result = await conn.fetch(query, *args)
            return [dict(row) for row in result]

    async def execute_insert(self, query: str, *args) -> Any:
        """Führt einen Insert aus und gibt die ID zurück"""
        async with self.get_async_connection() as conn:
            return await conn.fetchval(query, *args)

    async def execute_many(self, query: str, data: list[tuple]):
        """Führt mehrere Operationen aus"""
        async with self.get_async_connection() as conn:
            await conn.executemany(query, data)

    async def bulk_insert(
        self, table: str, data: list[dict], conflict_resolution: str = "DO NOTHING"
    ):
        """Bulk Insert mit Konfliktbehandlung"""
        if not data:
            return

        columns = list(data[0].keys())
        placeholders = ",".join([f"${i+1}" for i in range(len(columns))])

        # Normalize conflict clause: allow callers to pass either the full
        # "ON CONFLICT ..." or just the body "(cols) DO ..." or even empty
        conflict_clause = ""
        if conflict_resolution:
            cr = conflict_resolution.strip()
            if cr.lower().startswith("on conflict"):
                conflict_clause = cr  # already complete
            else:
                conflict_clause = f"ON CONFLICT {cr}"

        query = f"""
        INSERT INTO {table} ({','.join(columns)}) 
        VALUES ({placeholders})
        {conflict_clause}
        """

        values = [list(row.values()) for row in data]
        await self.execute_many(query, values)

        self.logger.info(f"Bulk inserted {len(data)} records into {table}")

    def create_tables(self):
        """Erstellt alle Tabellen"""
        if not self.engine:
            raise RuntimeError("Sync database not initialized")

        Base.metadata.create_all(bind=self.engine)
        self.logger.info("Database tables created")

    def drop_tables(self):
        """Löscht alle Tabellen (Vorsicht!)"""
        if not self.engine:
            raise RuntimeError("Sync database not initialized")

        Base.metadata.drop_all(bind=self.engine)
        self.logger.warning("All database tables dropped")

    async def health_check(self) -> dict[str, Any]:
        """Führt einen Gesundheitscheck der Datenbank durch"""
        try:
            # Async Pool Check
            async with self.get_async_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                async_status = "healthy" if result == 1 else "unhealthy"

            # Sync Engine Check
            with self.get_session() as session:
                session.execute(text("SELECT 1"))
                sync_status = "healthy"

            return {
                "async_pool": async_status,
                "sync_engine": sync_status,
                "pool_size": self.pool.get_size() if self.pool else 0,
                "pool_idle": self.pool.get_idle_size() if self.pool else 0,
            }

        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return {"async_pool": "unhealthy", "sync_engine": "unhealthy", "error": str(e)}

    async def close(self):
        """Schließt alle Datenbankverbindungen"""
        if self.pool:
            await self.pool.close()
            self.logger.info("Async database pool closed")

        if self.engine:
            self.engine.dispose()
            self.logger.info("Sync database engine disposed")
