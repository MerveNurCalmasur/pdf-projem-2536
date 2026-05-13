from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime,timezone,timedelta
from database import Base # Az önce oluşturduğumuz dosyadan Base'i çağırıyoruz
TURKEY_TZ = timezone(timedelta(hours=3))
def turkey_time():
    return datetime.now(TURKEY_TZ).replace(tzinfo=None)

# kullanıcı tablosu
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String, default="member") # admin veya member

    # Kullanıcının yaptığı işlemlerle bağlantı kuruyoruz.
    operations = relationship("Operation", back_populates="owner")

# işlem tablosu - limit kontrolü için önemli
class Operation(Base):
    __tablename__ = "operations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Üye değilse boş kalır
    ip_address = Column(String, nullable=True) # Üye olmayanları IP'den tanımak için
    operation_type = Column(String) # merge, convert, sign
    file_name = Column(String, nullable=True)   
    file_size = Column(Integer, nullable=True)  
    status = Column(String, default="success")
    timestamp = Column(DateTime, default=turkey_time)

    owner = relationship("User", back_populates="operations")