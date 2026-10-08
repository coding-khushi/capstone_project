"""SQLite schema via SQLAlchemy (Phase 7+)."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, LargeBinary, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship
import datetime


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    root_path = Column(Text, nullable=False, unique=True)
    indexed_at = Column(DateTime, default=datetime.datetime.utcnow)

    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")



class ProjectFile(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    path = Column(Text, nullable=False)
    language = Column(String(64))
    indexed_at = Column(DateTime, default=datetime.datetime.utcnow)

    project = relationship("Project", back_populates="files")
    symbols = relationship("Symbol", back_populates="file", cascade="all, delete-orphan")
    embeddings = relationship("Embedding", back_populates="file", cascade="all, delete-orphan")


class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    name = Column(String(512), nullable=False, index=True)
    kind = Column(String(64))  # function, class, variable, import
    line_start = Column(Integer)
    line_end = Column(Integer)
    signature = Column(Text)

    file = relationship("ProjectFile", back_populates="symbols")


class Embedding(Base):
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_type = Column(String(64))
    line_start = Column(Integer)
    line_end = Column(Integer)
    vector = Column(LargeBinary, nullable=False)

    file = relationship("ProjectFile", back_populates="embeddings")


def get_engine(db_path: str = "percept.db"):
    return create_engine(f"sqlite:///{db_path}", echo=False)


def init_db(db_path: str = "percept.db"):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine
