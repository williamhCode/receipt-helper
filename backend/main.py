from typing import Annotated

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi import Depends, FastAPI

from .models import Base, SessionRoom

# fastapi app -------------------------------------------------
app = FastAPI(title="Reciept Helper", version="0.0.1")

# database setup -----------------------------------------------
db_url = "sqlite:///./reciept-helper.db"
engine = create_engine(db_url, connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)

# dependency --------------------------------------------------
def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# sessions ---------------------------------------------------
# @app.post("/sessions/create")
# def create_session(response: Response, db: SessionDep):
