import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Any
import asyncio
import platform

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import ConnectionPool, AsyncConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore

from app.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB,
    DB_POOL_SIZE, DB_MAX_OVERFLOW, DB_POOL_TIMEOUT, DB_POOL_RECYCLE,
    DB_CONNECTION_RETRIES,
    DB_RETRY_DELAY,
    postgresql_async_connection_string,
    postgresql_connection_string
)

logger = logging.getLogger(__name__)

# Type variable for function return types
T = TypeVar('T')

# Connection settings
connection_kwargs = {
    "autocommit": True,
    "prepare_threshold": 0,
    "row_factory": dict_row
}

# Singleton instances
_connection_pool = None
_async_connection_pool = None
_postgres_saver = None
_async_postgres_saver = None
_postgres_store = None


def with_retry(max_retries: int = DB_CONNECTION_RETRIES, delay: int = DB_RETRY_DELAY) -> Callable:
    """
    Decorator for retrying database operations with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay in seconds between retries

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    current_delay = delay * (2 ** (retries - 1))  # Exponential backoff

                    if retries < max_retries:
                        logger.warning(
                            f"Database operation failed: {str(e)}. "
                            f"Retrying in {current_delay}s ({retries}/{max_retries})..."
                        )
                        time.sleep(current_delay)
                    else:
                        logger.error(f"Failed after {max_retries} retry attempts: {str(e)}")
                        raise

            # This line should never be reached, but keeps type checkers happy
            raise RuntimeError("Unexpected control flow in retry decorator")

        return wrapper

    return decorator


def get_connection_pool() -> ConnectionPool:
    """
    Get or create a PostgreSQL connection pool.
    This is a singleton pattern to ensure we only have one connection pool.
    """
    global _connection_pool

    if _connection_pool is None:
        try:
            # Create connection pool
            _connection_pool = ConnectionPool(
                conninfo=postgresql_connection_string,
                max_size=DB_POOL_SIZE,
                kwargs=connection_kwargs,
            )

            logger.info("PostgreSQL connection pool initialized")
        except Exception as e:
            print(e)
            logger.error(f"Failed to initialize PostgreSQL connection pool: {str(e)}")
            raise

    return _connection_pool


async def get_async_connection_pool() -> AsyncConnectionPool:
    """
    Get or create an asynchronous PostgreSQL connection pool.
    This is a singleton pattern to ensure we only have one connection pool.
    """
    global _async_connection_pool

    if _async_connection_pool is None:
        try:
            # Create async connection pool
            _async_connection_pool = AsyncConnectionPool(
                conninfo=postgresql_connection_string,
                max_size=DB_POOL_SIZE,
                kwargs=connection_kwargs,
            )

            logger.info("Async PostgreSQL connection pool initialized")
        except Exception as e:
            print(e)
            logger.error(f"Failed to initialize async PostgreSQL connection pool: {str(e)}")
            raise

    return _async_connection_pool


@with_retry()
def get_postgres_saver() -> PostgresSaver:
    """
    Get or create a PostgresSaver instance.
    This is a singleton pattern to ensure we only have one instance.
    """
    global _postgres_saver

    if _postgres_saver is None:
        try:
            pool = get_connection_pool()

            # Create PostgresSaver
            _postgres_saver = PostgresSaver(pool)

            # Initialize tables
            _postgres_saver.setup()
            logger.info("PostgreSQL saver initialized successfully")
        except Exception as e:
            print(e)
            logger.error(f"Failed to initialize PostgreSQL saver: {str(e)}")
            raise

    return _postgres_saver


async def get_async_postgres_saver(max_retries: int = 3, retry_delay: float = 1.0):
    """
    Crea un checkpointer PostgreSQL asíncrono con manejo robusto de conexiones.
    
    Args:
        max_retries: Número máximo de intentos de conexión
        retry_delay: Tiempo de espera entre intentos (en segundos)
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    
    # CORRECCIÓN CRÍTICA: Configurar Event Loop para Windows
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔧 Creando checkpointer PostgreSQL asíncrono (intento {attempt + 1}/{max_retries})...")
            
            # Pool de conexiones más robusto con configuración optimizada
            pool = AsyncConnectionPool(
                postgresql_async_connection_string,  # Usar la variable correcta
                min_size=2,           # Mínimo 2 conexiones
                max_size=10,          # Máximo 10 conexiones
                max_idle=300.0,       # 5 minutos de idle máximo
                max_lifetime=3600.0,  # 1 hora de vida máxima por conexión
                timeout=30.0,         # 30 segundos timeout para obtener conexión
                reconnect_timeout=10.0, # 10 segundos timeout para reconexión
                open=True
            )
            
            logger.info("✅ Pool de conexiones PostgreSQL async creado exitosamente")
            
            # Crear checkpointer con el pool
            saver = AsyncPostgresSaver(pool)
            
            # Inicializar las tablas si es necesario
            await saver.setup()
            
            logger.info("✅ Async PostgreSQL saver inicializado exitosamente")
            return saver
            
        except Exception as e:
            logger.warning(f"⚠️ Error creando async saver (intento {attempt + 1}/{max_retries}): {str(e)}")
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))  # Backoff exponencial
            else:
                logger.error(f"❌ Falló la creación del async saver después de {max_retries} intentos")
                raise Exception(f"No se pudo conectar a PostgreSQL después de {max_retries} intentos: {str(e)}")


@with_retry()
def get_postgres_store() -> PostgresStore:
    """
    Get or create a PostgresStore instance.
    This is a singleton pattern to ensure we only have one instance.
    """
    global _postgres_store

    if _postgres_store is None:
        try:
            pool = get_connection_pool()

            # Create PostgresStore
            _postgres_store = PostgresStore(pool)
            logger.info("PostgreSQL store initialized successfully")
        except Exception as e:
            print(e)
            logger.error(f"Failed to initialize PostgreSQL store: {str(e)}")
            raise

    return _postgres_store


def check_postgres_connection() -> bool:
    """
    Check if the PostgreSQL connection is working.

    Returns:
        bool: True if the connection is working, False otherwise.
    """
    try:
        pool = get_connection_pool()
        with pool.connection() as conn:
            cursor = conn.cursor()
            # Usamos un alias para asegurar que la clave del diccionario sea conocida
            cursor.execute("SELECT 1 AS one")
            result = cursor.fetchone()
            return result is not None and result.get("one") == 1
    except Exception as e:
        logger.error(f"PostgreSQL connection check failed: {str(e)}")
        return False


def close_postgres_connections() -> None:
    """
    Close all PostgreSQL connections.
    Called on application shutdown.
    """
    global _connection_pool, _async_connection_pool, _postgres_saver, _async_postgres_saver, _postgres_store

    try:
        if _connection_pool is not None:
            _connection_pool.close()
            logger.info("PostgreSQL connection pool closed")

        if _async_connection_pool is not None:
            # Close async pool
            asyncio.create_task(_async_connection_pool.close())
            logger.info("Async PostgreSQL connection pool closing")
    except Exception as e:
        logger.error(f"Error closing PostgreSQL connection pools: {str(e)}")

    # Reset singleton instances
    _connection_pool = None
    _async_connection_pool = None
    _postgres_saver = None
    _async_postgres_saver = None
    _postgres_store = None
