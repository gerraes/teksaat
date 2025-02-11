import os
from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Güvenlik için gizli anahtar

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["ALLOWED_EXTENSIONS"] = {"png", "jpg", "jpeg", "gif"}
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Maksimum dosya boyutu: 16 MB

# Desteklenen platformlar (picklist için)
PLATFORMS = [
    "A101", "Trendyol", "Hepsiburada", "Boyner", "Beymen", "N11", "Amazon", 
    "Teksaat.com", "Teknosa", "Çiçeksepeti", "Pazarama", "PttAvm", "Feshfed", 
    "İdefix", "Diğer", "Nevade Exporgin", "Carrefour", "Flo", "LCW", "Bim"
]

# Kullanıcı bilgileri (basit örnek)
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
    # Eğer tablo yoksa oluşturur
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
    """
    Mevcut tablo şemasını kontrol eder, eksik sütun varsa ALTER TABLE ile ekler.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(returns)")
    columns = [col[1] for col in cursor.fetchall()]
    if "approved_by" not in columns:
        cursor.execute("ALTER TABLE returns ADD COLUMN approved_by TEXT")
        conn.commit()
    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

# Ana sayfa ve iade yönetimi şablonu
html_code = '''
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>İade Yönetimi</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
</head>
<body>
    <div class="container mt-4">
        <div class="d-flex justify-content-between align-items-center">
            <h1 class="text-center">📦 İade Yönetimi</h1>
            <div>
                <span>Giriş Yapan: <strong>{{ session.get('username') }}</strong></span>
                <a href="{{ url_for('logout') }}" class="btn btn-outline-secondary btn-sm ms-2">Çıkış</a>
            </div>
        </div>
        {% if session.get('role') == 'customer_service' %}
        <button class="btn btn-success my-3" data-bs-toggle="modal" data-bs-target="#addModal">➕ Yeni İade</button>
        {% endif %}

        <table class="table table-striped">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Resim</th>
                    <th>Sipariş No</th>
                    <th>Ürün</th>
                    <th>Marka</th>
                    <th>Platform</th>
                    <th>İade Sebebi</th>
                    <th>İade Tarihi</th>
                    <th>Durum</th>
                    <th>Onaylayan</th>
                    <th>İşlem</th>
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr id="row-{{ row.id }}">
                    <td>{{ row.id }}</td>
                    <td>
                        {% if row.image_path %}
                            <img src="{{ row.image_path }}" width="50" height="50">
                        {% else %}
                            <span class="text-muted">Yok</span>
                        {% endif %}
                    </td>
                    <td>{{ row.order_id }}</td>
                    <td>{{ row.product }}</td>
                    <td>{{ row.brand }}</td>
                    <td>{{ row.platform }}</td>
                    <td>{{ row.reason }}</td>
                    <td>{{ row.return_date }}</td>
                    <td id="status-{{ row.id }}">{{ row.status }}</td>
                    <td>{{ row.approved_by if row.approved_by else 'Bekliyor' }}</td>
                    <td>
                        {% if row.status == "Bekliyor" and session.get('role') == "warehouse" %}
                            <button class="btn btn-success btn-sm" onclick="updateStatus({{ row.id }}, 'Onaylandı')">✅ Onayla</button>
                            <button class="btn btn-danger btn-sm" onclick="updateStatus({{ row.id }}, 'Reddedildi')">❌ Reddet</button>
                        {% else %}
                            <span class="badge bg-secondary">{{ row.status }}</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <!-- Modal (Yeni İade Ekle) -->
    <div class="modal fade" id="addModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Yeni İade Ekle</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form id="returnForm" enctype="multipart/form-data">
                        <div class="mb-3">
                            <label>Sipariş Numarası</label>
                            <input type="text" name="order_id" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Ürün</label>
                            <input type="text" name="product" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Marka</label>
                            <input type="text" name="brand" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Platform</label>
                            <select name="platform" class="form-control" required>
                                {% for platform in platforms %}
                                    <option value="{{ platform }}">{{ platform }}</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="mb-3">
                            <label>İade Sebebi</label>
                            <select name="reason" class="form-control">
                                <option>Beğenmedim</option>
                                <option>Beden Uymadı</option>
                                <option>Fiyat Sebebi</option>
                                <option>Diğer</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label>İade Tarihi</label>
                            <input type="date" name="return_date" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Ürün Görseli</label>
                            <input type="file" name="image" class="form-control">
                        </div>
                        <button type="submit" class="btn btn-primary">Ekle</button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <script>
        $("#returnForm").submit(function(event) {
            event.preventDefault();
            var formData = new FormData(this);
            $.ajax({
                url: "/add",
                type: "POST",
                data: formData,
                contentType: false,
                processData: false,
                success: function() {
                    location.reload();
                }
            });
        });

        function updateStatus(id, status) {
            $.post("/update_status", { id: id, status: status }, function(response) {
                if (response.success) {
                    $("#status-" + id).text(status);
                    location.reload();  // Durumu güncelledikten sonra sayfayı yeniden yükler
                }
            });
        }
    </script>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM returns").fetchall()
    conn.close()
    return render_template_string(html_code, rows=rows, platforms=PLATFORMS)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = USERS.get(username)
        if user and user['password'] == password:
            session['username'] = username
            session['role'] = user['role']
            return redirect(url_for('index'))
        else:
            error = 'Geçersiz kullanıcı adı veya şifre!'
    return render_template_string('''
    <form method="post">
        <label>Kullanıcı Adı</label>
        <input type="text" name="username" required><br>
        <label>Şifre</label>
        <input type="password" name="password" required><br>
        <button type="submit">Giriş Yap</button>
    </form>
    <p>{{ error }}</p>
    ''')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/add', methods=['POST'])
def add_return():
    order_id = request.form['order_id']
    product = request.form['product']
    brand = request.form['brand']
    platform = request.form['platform']
    reason = request.form['reason']
    return_date = request.form['return_date']
    
    image = request.files.get('image')
    image_path = None
    if image and allowed_file(image.filename):
        image_filename = secure_filename(image.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], image_filename)
        image.save(image_path)
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO returns (order_id, product, brand, platform, reason, return_date, image_path) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (order_id, product, brand, platform, reason, return_date, image_path))
    conn.commit()
    conn.close()
    
    return jsonify(success=True)

@app.route('/update_status', methods=['POST'])
def update_status():
    return_id = request.form['id']
    status = request.form['status']
    approved_by = session.get('username')
    
    conn = get_db_connection()
    conn.execute('''
        UPDATE returns SET status = ?, approved_by = ? WHERE id = ?
    ''', (status, approved_by, return_id))
    conn.commit()
    conn.close()

    return jsonify(success=True)

if __name__ == '__main__':
    create_table()
    update_table_schema()  # Şema güncelleniyor
    app.run(debug=True)
