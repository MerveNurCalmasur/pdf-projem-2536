from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Request , Form 
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from pypdf import PdfWriter
from passlib.context import CryptContext
from typing import List
from datetime import datetime, date     #limit kontrol için
import os
import uuid
import subprocess
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import io
from backend import models, schemas
from backend.database import engine, SessionLocal , Base
import tempfile
import subprocess



# Şifre hashleme 
pwd_context = CryptContext(schemes=["bcrypt"])

# Veritabanı tablolarını oluştur
models.Base.metadata.create_all(bind=engine)

# FastAPI motorunu başlat
app = FastAPI()

#CORS ayarı — HTML dosyasından gelen isteklere izin ver
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def limit_kontrol(ip: str, db: Session,user_id: int=None):

    if user_id:
        return
    
    bugun_baslangic = datetime.combine(date.today(), datetime.min.time())
    islem_sayisi = db.query(models.Operation).filter(
        models.Operation.ip_address == ip,
        models.Operation.timestamp >= bugun_baslangic
    ).count()

    if islem_sayisi >= 3:
        raise HTTPException(
            status_code=429,
            detail="Günlük 3 işlem limitinizi doldurdunuz! Yarın tekrar deneyin."
        )
# anasayfa
@app.get("/")
def ana_sayfa():
    return {"mesaj": "Sistem çalışıyor! PDF projesine hoş geldin."}

# kayıt(üye) 
@app.post("/signup", response_model=schemas.UserResponse)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):

    # Email daha önce alınmış mı?
    existing_email = db.query(models.User).filter( models.User.email == user.email).first() #veri tabanında daha önce bu e mail ile kayıt yapılmış mı bakar
    if existing_email:
        raise HTTPException(status_code=400, detail="Bu email zaten kayıtlı!") #kayıt varsa hata verir.

    # Kullanıcı adı daha önce alınmış mı?
    existing_username = db.query(models.User).filter(models.User.username == user.username).first() #veritabanından kullanıcı adı ile daha önce kayıt olmuş mu bakar
    if existing_username:
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten alınmış!") #kayıt varsa hata verir.

    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=pwd_context.hash(user.password),  # Hashli şifre(güvenli şifre)
        role="member"
    )
    db.add(new_user)  #listeye ekle
    db.commit()       #değişiklikleri kaydet
    db.refresh(new_user)     #veritabanından son halini geri al 
    return new_user

# giriş yap
@app.post("/login")
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(
        models.User.username == user.username
    ).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı!")

    if not pwd_context.verify(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="Şifre hatalı!")

    return {"mesaj": "Giriş başarılı!", "kullanici": db_user.username, "rol": db_user.role}

# pdf birleştirme
@app.post("/merge")
async def merge_pdfs(
    request: Request,
    files: List[UploadFile]=File(...), # Dosya yükleme 
    username: str = Form(None),  # ✅ opsiyonel, giriş yapmışsa gelir
    db: Session = Depends(get_db)
):
    ip = request.client.host
    # Kullanıcı giriş yapmış mı kontrol et
    user_id = None
    if username:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            user_id = user.id
    
    limit_kontrol(ip, db, user_id)  # user_id varsa limit yok

    if len(files) < 2:
        raise HTTPException(status_code=400, detail="En az 2 PDF yükleyin!")

    os.makedirs("uploads", exist_ok=True)
    merger = PdfWriter()

    try:
        for file in files:
            if not file.filename.endswith(".pdf"):
                raise HTTPException(
                    status_code=400,
                    detail=f"{file.filename} PDF değil!"
                )
            merger.append(file.file)

        # Benzersiz dosya adı
        output_filename = f"{uuid.uuid4()}_birlesik.pdf"
        output_path = f"uploads/{output_filename}"

        with open(output_path, "wb") as f_out:
            merger.write(f_out)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")

    finally:
        merger.close()

    # DB'ye kaydet (return'den ÖNCE)
    yeni_islem = models.Operation(
        operation_type="merge",
        ip_address=ip,
        file_name=output_filename,
        status="success"
    )
    db.add(yeni_islem)
    db.commit()

    return FileResponse(
        path=output_path,
        filename="birlesik_dosya.pdf",
        media_type="application/pdf"
    )

# PDF'E DÖNÜŞTÜRME (JPG/PNG → PDF)
@app.post("/convert")
async def convert_to_pdf(
    request: Request,
    files: List[UploadFile] = File(description="Dönüştürülecek resim dosyaları"),
    username: str = Form(None),  # ✅ opsiyonel, giriş yapmışsa gelir
    db: Session = Depends(get_db)
):
    ip = request.client.host
    # Kullanıcı giriş yapmış mı kontrol et
    user_id = None
    if username:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            user_id = user.id
    
    limit_kontrol(ip, db, user_id)  # user_id varsa limit yok

    # Sadece resim dosyalarını kabul et
    izinli_uzantilar = [".jpg", ".jpeg", ".png", ".webp"]
    
    for file in files:
        uzanti = os.path.splitext(file.filename)[1].lower()
        if uzanti not in izinli_uzantilar:
            raise HTTPException(
                status_code=400,
                detail=f"{file.filename} desteklenmiyor! Sadece JPG, PNG, WEBP kabul edilir."
            )

    os.makedirs("uploads", exist_ok=True)

    try:
        resimler = []

        for file in files:
            # Dosyayı oku ve PIL Image'e çevir
            icerik = await file.read()
            
            import io
            resim = Image.open(io.BytesIO(icerik))
            
            # PDF için RGB moduna çevir
            if resim.mode != "RGB":
                resim = resim.convert("RGB")
            
            resimler.append(resim)

        # Benzersiz dosya adı
        output_filename = f"{uuid.uuid4()}_donusturulmus.pdf"
        output_path = f"uploads/{output_filename}"

        # İlk resmi kaydet, diğerlerini ekle
        if len(resimler) == 1:
            resimler[0].save(output_path, "PDF")
        else:
            resimler[0].save(
                output_path,
                "PDF",
                save_all=True,
                append_images=resimler[1:]
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")

    # DB'ye kaydet
    yeni_islem = models.Operation(
        operation_type="convert",
        ip_address=request.client.host,
        file_name=output_filename,
        status="success"
    )
    db.add(yeni_islem)
    db.commit()

    return FileResponse(
        path=output_path,
        filename="donusturulmus.pdf",
        media_type="application/pdf"
    )

# FİLİGRAN EKLEME
@app.post("/watermark")
async def add_watermark(
    request: Request,
    file: UploadFile = File(description="Filigran eklenecek PDF"),
    text: str = Form(description="Filigran metni (örn: GİZLİ, TASLAK)"),
    username: str = Form(None),  # ✅ opsiyonel, giriş yapmışsa gelir
    db: Session = Depends(get_db)
):
    ip = request.client.host
    # Kullanıcı giriş yapmış mı kontrol et
    user_id = None
    if username:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            user_id = user.id
    
    limit_kontrol(ip, db, user_id)  # user_id varsa limit yok

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyası yükleyebilirsiniz!")

    os.makedirs("uploads", exist_ok=True)

    try:
        # 1. Yüklenen PDF'i oku
        icerik = await file.read()
        pdf_reader = PdfWriter()
        
        from pypdf import PdfReader
        kaynak_pdf = PdfReader(io.BytesIO(icerik))

        # 2. Filigran sayfası oluştur
        filigran_buffer = io.BytesIO()
        c = canvas.Canvas(filigran_buffer, pagesize=letter)
        
        # Filigran ayarları
        c.setFont("Helvetica-Bold", 60)
        c.setFillColorRGB(0.8, 0.8, 0.8, alpha=0.4)  # Gri, yarı saydam
        
        # Sayfanın ortasına çapraz yaz
        c.saveState()
        c.translate(300, 400)
        c.rotate(45)
        c.drawCentredString(0, 0, text)
        c.restoreState()
        c.save()

        # 3. Her sayfaya filigran ekle
        filigran_buffer.seek(0)
        filigran_pdf = PdfReader(filigran_buffer)
        filigran_sayfasi = filigran_pdf.pages[0]

        pdf_writer = PdfWriter()
        for sayfa in kaynak_pdf.pages:
            sayfa.merge_page(filigran_sayfasi)
            pdf_writer.add_page(sayfa)

        # 4. Kaydet
        output_filename = f"{uuid.uuid4()}_filigranli.pdf"
        output_path = f"uploads/{output_filename}"

        with open(output_path, "wb") as f_out:
            pdf_writer.write(f_out)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hata: {str(e)}")

    # 5. DB'ye kaydet
    yeni_islem = models.Operation(
        operation_type="watermark",
        ip_address=request.client.host,
        file_name=output_filename,
        status="success"
    )
    db.add(yeni_islem)
    db.commit()

    return FileResponse(
        path=output_path,
        filename="filigranli_dosya.pdf",
        media_type="application/pdf"
    )



@app.post("/convert-office")
async def convert_office(
    request: Request,
    file: UploadFile = File(...),
    username: str = Form(None),
    db: Session = Depends(get_db)
):
    # Kullanıcıyı bul ve limit kontrolü yap (Senin önceki kodunla uyumlu)
    ip = request.client.host
    user_id = None
    if username:
        user = db.query(models.User).filter(models.User.username == username).first()
        if user:
            user_id = user.id
    
    # Oran limitini kontrol et (Daha önce yazdığımız fonksiyon)
    limit_kontrol(ip, db, user_id) 

    # 1. Dosyayı geçici olarak uploads klasörüne kaydet
    ext = os.path.splitext(file.filename)[1].lower()
    temp_name = f"temp_{uuid.uuid4()}{ext}"
    temp_path = os.path.join("uploads", temp_name)
    
    with open(temp_path, "wb") as f:
        f.write(await file.read())

        try: # <--- TRY BLOĞU BURADAN BAŞLIYOR
        # 2. LibreOffice (soffice) Yolu
            soffice_path = os.path.join(os.getcwd(), "libreoffice", "program", "soffice")
            
            command = [
                soffice_path,
                "--headless", 
                "--convert-to", "pdf", 
                "--outdir", "uploads", 
                temp_path
            ]
            print(f"Mevcut dizin: {os.getcwd()}")
            print(f"Dizin içeriği: {os.listdir('.')}")
            # Dönüştürmeyi başlat
            subprocess.run(command, check=True)

            # 3. PDF yolunu belirle
            output_filename = temp_name.replace(ext, ".pdf")
            output_path = os.path.join("uploads", output_filename)

            # Orijinal dosyayı hemen sil
            if os.path.exists(temp_path): 
                os.remove(temp_path)

            # 4. Veritabanına kaydet
            new_action = models.UserAction(
                action_type="convert-office",
                ip_address=ip,
                file_name=output_filename,
                status="success",
                user_id=user_id
            )
            db.add(new_action)
            db.commit()

            return FileResponse(path=output_path, filename="donusturulmus.pdf")

        except Exception as e:
            # Hata olursa temizlik yap
            if os.path.exists(temp_path): 
                os.remove(temp_path)
            print(f"Dönüştürme Hatası: {str(e)}") # Loglara bakman için
            raise HTTPException(status_code=500, detail=f"Dönüştürme hatası: {str(e)}")

    # 4. Veritabanına kaydet
    new_action = models.UserAction(
        action_type="convert-office",
        ip_address=ip,
        file_name=output_filename,
        status="success",
        user_id=user_id
    )
    db.add(new_action)
    db.commit()

    return FileResponse(path=output_path, filename="donusturulmus.pdf")

# kullanıcılar 
@app.get("/admin/users", response_model=List[schemas.UserResponse])
def tum_kullanicilar(db: Session = Depends(get_db)):
    users = db.query(models.User).all()
    return users


# ADMIN — TÜM İŞLEMLER
@app.get("/admin/islemler")
def tum_islemler(db: Session = Depends(get_db)):
    islemler = db.query(models.Operation).order_by(
        models.Operation.timestamp.desc()
    ).all()
    
    sonuc = []
    for islem in islemler:
        sonuc.append({
            "id": islem.id,
            "islem_turu": islem.operation_type,
            "ip_adresi": islem.ip_address,
            "dosya_adi": islem.file_name,
            "durum": islem.status,
            "tarih": islem.timestamp.strftime("%d.%m.%Y %H:%M") if islem.timestamp else None
        })
    return sonuc

@app.post("/create-admin")
def create_admin(user: schemas.UserCreate, db: Session = Depends(get_db)):
    sifre = user.password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=pwd_context.hash(sifre),
        role="admin"  # ✅ admin rolü
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"mesaj": f"{user.username} admin olarak oluşturuldu!"}

# ADMIN — İSTATİSTİK
@app.get("/admin/istatistik")
def istatistik(db: Session = Depends(get_db)):
    toplam = db.query(models.Operation).count()
    
    birlestirme = db.query(models.Operation).filter(
        models.Operation.operation_type == "merge"
    ).count()
    
    donusturme = db.query(models.Operation).filter(
        models.Operation.operation_type == "convert"
    ).count()
    
    filigran = db.query(models.Operation).filter(
        models.Operation.operation_type == "watermark"
    ).count()
    
    toplam_kullanici = db.query(models.User).count()

    return {
        "toplam_islem": toplam,
        "birlestirme": birlestirme,
        "donusturme": donusturme,
        "filigran": filigran,
        "toplam_kullanici": toplam_kullanici
    }
# ADMIN — KULLANICI SİL
@app.delete("/admin/kullanici/{kullanici_id}")
def kullanici_sil(kullanici_id: int, db: Session = Depends(get_db)):
    kullanici = db.query(models.User).filter(
        models.User.id == kullanici_id
    ).first()
    
    if not kullanici:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı!")
    
    db.delete(kullanici)
    db.commit()
    return {"mesaj": f"{kullanici.username} silindi!"}

