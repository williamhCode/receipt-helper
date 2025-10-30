from sqlalchemy import create_engine
import os

from src.models import Base

db_url = os.getenv("DATABASE_PUBLIC_URL", "postgresql:///receipt_helper")
engine = create_engine(db_url)
Base.metadata.create_all(engine)

