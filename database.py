"""
Heidi Server — Database helper

Provides a connection pool and a simple helper to run queries.
"""

import mysql.connector
from mysql.connector import pooling
from config import settings

# Create a connection pool (reuses connections, avoids opening/closing per request)
_pool = pooling.MySQLConnectionPool(
    pool_name="heidi_pool",
    pool_size=5,
    host=settings.db_host,
    port=settings.db_port,
    user=settings.db_user,
    password=settings.db_password,
    database=settings.db_name,
)


def get_connection():
    """Get a connection from the pool. Use with `with` statement."""
    return _pool.get_connection()
