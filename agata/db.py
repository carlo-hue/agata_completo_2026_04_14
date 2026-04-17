#db.py
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get DATABASE_URL from .env
DATABASE_URL = os.getenv('DATABASE_URL')

from sqlalchemy.pool import NullPool

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,  # Ricicla connessioni ogni 5 minuti (da 3600)
    future=True,
    # pool_size=5,
    # max_overflow=10,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_clean_session():
    """Crea una sessione pulita senza stato di transazione precedente.

    Usa questo invece di SessionLocal() direttamente quando il codice precedente
    potrebbe aver lasciato la sessione in stato 'aborted'.

    Questo scarta tutte le connessioni dal pool per essere sicuri che nessuna
    sia rimasta in stato "aborted" da errori precedenti.
    """
    # Scarta tutte le connessioni dal pool (forza new connections)
    engine.dispose()

    session = SessionLocal()
    try:
        session.rollback()
    except:
        pass
    return session


@contextmanager
def get_db():
    """Context manager per SQLAlchemy sessions.

    Garantisce che la sessione sia sempre chiusa anche in caso di eccezione,
    prevenendo connection leak dal pool.

    Usage:
        with get_db() as db:
            projects = db.query(Project).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
