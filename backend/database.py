from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Veritabanı dosyasının bilgisayardaki yeri
SQLALCHEMY_DATABASE_URL = "sqlite:///./pdf_database.db"

# Veritabanı motorunu kuruyoruz
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False} #birden fazla uzer ın aynı aynda giriş yapmasını sağlar.
)

# Veritabanı ile işlem yapmamızı sağlayan oturum 
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Tabloların temelini oluşturan sınıf
Base = declarative_base()