import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from config import MYSQL_URL, MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE

logger = logging.getLogger(__name__)

# Base class for database models
Base = declarative_base()

# Attempt to create the database if it doesn't exist
def init_db_schema():
    """Ensure database exists and create all tables"""
    try:
        # Connect to MySQL server without database first
        temp_url = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/"
        temp_engine = create_engine(temp_url)
        with temp_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DATABASE}"))
            logger.info(f"Database {MYSQL_DATABASE} verified/created successfully.")
        temp_engine.dispose()
    except Exception as e:
        logger.error(f"Error checking/creating database: {e}")

# Call database check
init_db_schema()

# Create SQLAlchemy engine
engine = create_engine(
    MYSQL_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create tables if they do not exist"""
    try:
        from models.db_models import StockPriceRealtime, Screening, NewsSentiment
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
        print("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        print(f"Error creating database tables: {e}")

# Create tables
create_tables()

def get_db():
    """FastAPI Dependency for database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
