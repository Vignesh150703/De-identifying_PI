from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func
from app.config import PG_URI


engine = create_engine(PG_URI, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
Base = declarative_base()




class Person(Base):
__tablename__ = "persons"
id = Column(Integer, primary_key=True)
name = Column(String)
external_id = Column(String, unique=True, nullable=True)
created_at = Column(DateTime(timezone=True), server_default=func.now())
files = relationship("File", back_populates="person", cascade="all, delete-orphan")
ocr_texts = relationship("OCRText", back_populates="person", cascade="all, delete-orphan")




class File(Base):
__tablename__ = "files"
id = Column(Integer, primary_key=True)
person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
filename = Column(String, nullable=False)
minio_path = Column(String, nullable=False)
etag = Column(String, nullable=True)
file_type = Column(String, nullable=True)
status = Column(String, default="uploaded")
created_at = Column(DateTime(timezone=True), server_default=func.now())
person = relationship("Person", back_populates="files")




class OCRText(Base):
__tablename__ = "ocr_texts"
id = Column(Integer, primary_key=True)
person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
text = Column(Text, nullable=False)
minio_path = Column(String, nullable=True)
created_at = Column(DateTime(timezone=True), server_default=func.now())
person = relationship("Person", back_populates="ocr_texts")




def init_db():
Base.metadata.create_all(bind=engine)




if __name__ == "__main__":
init_db()
print("DB initialized")