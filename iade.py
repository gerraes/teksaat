import os
import sqlite3
import streamlit as st
from werkzeug.utils import secure_filename

# Streamlit ayarları
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

st.set_page_config(page_title="İade Yönetimi", layout="wide")

PLATFORMS = [
    "A101", "Trendyol", "Hepsiburada", "Boyner", "Beymen", "N11", "Amazon",
    "Teksaat.com", "Teknosa", "Çiçeksepeti", "Pazarama", "PttAvm", "Feshfed",
    "İdefix", "Diğer", "Nevade Exporgin", "Carrefour", "Flo", "LCW", "Bim"
]

USERS = {
    "customer_service": {"password": "cs123", "role": "customer_service"},
    "warehouse": {"password": "wh123", "role": "warehouse"}
}

def get_db_connection():
    conn = sqlite3.connect("returns.db")
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            product TEXT,
            brand TEXT,
            platform TEXT,
            reason TEXT,
            return_date TEXT,
            status TEXT DEFAULT 'Bekliyor',
            image_path TEXT,
            approved_by TEXT
        )
    ''')
    conn.commit()
    conn.close()

def update_table_schema():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(returns)")
    columns = [col[1] for col in cursor.fetchall()]
    if "approved_by" not in columns:
        cursor.execute("ALTER TABLE returns ADD COLUMN approved_by TEXT")
        conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {"png", "jpg", "jpeg", "gif"}

def login():
    st.title("Giriş Yap")
    username = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")
    
    if st.button("Giriş Yap"):
        user = USERS.get(username)
        if user and user['password'] == password:
            st.session_state['username'] = username
            st.session_state['role'] = user['role']
            st.success("Giriş başarılı!")
            return True
        else:
            st.error("Geçersiz kullanıcı adı veya şifre!")
    return False

def display_returns():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM returns").fetchall()
    conn.close()
    
    for row in rows:
        st.write(f"**ID**: {row['id']}, **Sipariş No**: {row['order_id']}, **Ürün**: {row['product']}, **Marka**: {row['brand']}, **Platform**: {row['platform']}, **İade Sebebi**: {row['reason']}, **Durum**: {row['status']}, **Onaylayan**: {row['approved_by'] if row['approved_by'] else 'Bekliyor'}")
        if row['image_path']:
            st.image(row['image_path'], width=100)

def add_return():
    st.title("Yeni İade Ekle")
    
    order_id = st.text_input("Sipariş Numarası")
    product = st.text_input("Ürün")
    brand = st.text_input("Marka")
    platform = st.selectbox("Platform", PLATFORMS)
    reason = st.selectbox("İade Sebebi", ["Beğenmedim", "Beden Uymadı", "Fiyat Sebebi", "Diğer"])
    return_date = st.date_input("İade Tarihi")
    
    image = st.file_uploader("Ürün Görseli", type=["png", "jpg", "jpeg", "gif"])
    
    if st.button("Ekle"):
        if image and allowed_file(image.name):
            image_path = os.path.join(UPLOAD_FOLDER, secure_filename(image.name))
            with open(image_path, "wb") as f:
                f.write(image.getbuffer())
        else:
            image_path = None
        
        conn = get_db_connection()
        conn.execute('''INSERT INTO returns (order_id, product, brand, platform, reason, return_date, image_path) 
                        VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                     (order_id, product, brand, platform, reason, return_date, image_path))
        conn.commit()
        conn.close()
        
        st.success("İade başarıyla eklendi!")

def update_status():
    return_id = st.number_input("İade ID", min_value=1)
    status = st.selectbox("Durum", ["Bekliyor", "Onaylandı", "Reddedildi"])
    
    if st.button("Durumu Güncelle"):
        approved_by = st.session_state.get('username')
        
        conn = get_db_connection()
        conn.execute('''UPDATE returns SET status = ?, approved_by = ? WHERE id = ?''', 
                     (status, approved_by, return_id))
        conn.commit()
        conn.close()
        
        st.success(f"Durum '{status}' olarak güncellendi.")

# Ana sayfa akışı
if 'username' not in st.session_state:
    if not login():
        st.stop()

st.title("📦 İade Yönetimi")
role = st.session_state.get('role')

if role == "customer_service":
    if st.button("Yeni İade Ekle"):
        add_return()

if role == "warehouse":
    update_status()

st.subheader("Tüm İadeler")
display_returns()
