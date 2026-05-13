from pydantic import BaseModel, EmailStr, field_validator

# Kullanıcı kayıt olurken (Sign Up) hangi bilgileri göndermek zorunda?
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator("password")
    def sifre_kontrol(cls, v):
        if len(v) < 6:
            raise ValueError("Şifre en az 6 karakter olmalı!")
        return v

# Kullanıcı giriş yaparken (Login) neleri göndermeli?
class UserLogin(BaseModel):
    username: str
    password: str

# Kullanıcı bilgisi dönerken şifreyi gizler
class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str

    class Config:
        from_attributes = True

# PDF işlemi bittiğinde kullanıcıya ne döneceğiz? (İsteğe bağlı, ileride kullanacağız)
class OperationResult(BaseModel):
    status: str
    message: str