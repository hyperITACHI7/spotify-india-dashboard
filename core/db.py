try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

from core.secrets import database

def get_connection():
    """
    Returns a psycopg2 connection using the credentials defined in core/secrets.py.
    """
    if psycopg2 is None:
        raise ImportError("psycopg2 is not installed. Database connection unavailable.")
        
    return psycopg2.connect(
        host=database.host,
        port=database.port,
        dbname=database.name,
        user=database.user,
        password=database.password,
        cursor_factory=RealDictCursor,
        connect_timeout=3,
    )
