from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os, sqlite3, time, json, hashlib, datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# ══ الإعدادات ══
USERNAME = "UserDNA"
PASSWORD = "90663584"
LEARNING_SAMPLES = 10
RISK_WARNING = 40
RISK_CRITICAL = 70
PERSONAL_APPS = ["الرسائل 💬", "البريد الإلكتروني 📧", "المحفظة البنكية 💳", "الصور الشخصية 🖼️"]
DB = "userdna.db"

# فلتر عرض الوقت في القوالب
@app.template_filter('strftime')
def _jinja2_filter_timestamp(ts):
    return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

# ══ أدوات تشفير كلمات المرور ══
def hash_password(password):
    salt = os.urandom(16).hex()
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"

def verify_password(password, stored):
    salt, h = stored.split(":")
    return hashlib.sha256((salt + password).encode()).hexdigest() == h

# ══ قاعدة البيانات (3 جداول) ══
def init_db():
    db = sqlite3.connect(DB)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        typing_speed REAL DEFAULT 100.0,
        mouse_jitter REAL DEFAULT 5.0,
        learned INTEGER DEFAULT 0,
        failed_attempts INTEGER DEFAULT 0,
        locked_until REAL DEFAULT 0,
        created_at REAL
    );
    CREATE TABLE IF NOT EXISTS learning_samples (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        typing_speed REAL,
        mouse_jitter REAL,
        created_at REAL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS risk_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        risk_score INTEGER,
        status TEXT,
        alerts TEXT,
        created_at REAL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    """)
    db.commit()
    db.close()

def query(sql, params=(), fetch_one=False, fetch_all=False):
    db = sqlite3.connect(DB)
    cur = db.execute(sql, params)
    data = cur.fetchone() if fetch_one else cur.fetchall() if fetch_all else None
    db.commit()
    db.close()
    return data

init_db()

# المستخدم الافتراضي
if not query("SELECT id FROM users WHERE username=?", (USERNAME,), fetch_one=True):
    query("INSERT INTO users (username, password_hash, created_at) VALUES (?,?,?)",
          (USERNAME, hash_password(PASSWORD), time.time()))

# ══ المسارات ══
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        row = query("SELECT * FROM users WHERE username=?", (username,), fetch_one=True)

        if row and row[7] > time.time():
            mins = int((row[7] - time.time()) / 60) + 1
            error = f"الحساب مقفل مؤقتاً، حاول بعد {mins} دقيقة"
        elif row and verify_password(password, row[2]):
            session['user'] = row[0]
            session['username'] = row[1]
            query("UPDATE users SET failed_attempts=0 WHERE id=?", (row[0],))
            return redirect(url_for('dashboard'))
        else:
            if row:
                fails = row[6] + 1
                if fails >= 5:
                    query("UPDATE users SET failed_attempts=0, locked_until=? WHERE id=?",
                          (time.time() + 900, row[0]))
                    error = "تم قفل الحساب 15 دقيقة بعد 5 محاولات فاشلة"
                else:
                    query("UPDATE users SET failed_attempts=? WHERE id=?", (fails, row[0]))
                    error = f"بيانات خاطئة — محاولة {fails} من 5"
            else:
                error = "اسم المستخدم أو كلمة المرور غير صحيحة"
    return render_template('login.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html',
                           user=session['username'], personal_apps=PERSONAL_APPS)

@app.route('/analyze_behavior', methods=['POST'])
def analyze_behavior():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401

    uid = session['user']
    row = query("SELECT * FROM users WHERE id=?", (uid,), fetch_one=True)
    data = request.json or {}
    speed = data.get('typing_speed', row[3])
    jitter = data.get('mouse_jitter', row[4])

    # وضع التعلم
    if not row[5]:
        query("INSERT INTO learning_samples (user_id, typing_speed, mouse_jitter, created_at) VALUES (?,?,?,?)",
              (uid, speed, jitter, time.time()))
        count = query("SELECT COUNT(*) FROM learning_samples WHERE user_id=?", (uid,), fetch_one=True)[0]

        if count >= LEARNING_SAMPLES:
            samples = query("SELECT typing_speed, mouse_jitter FROM learning_samples WHERE user_id=?", (uid,))
            avg_speed = sum(s[0] for s in samples) / len(samples)
            avg_jitter = sum(s[1] for s in samples) / len(samples)
            query("UPDATE users SET typing_speed=?, mouse_jitter=?, learned=1 WHERE id=?",
                  (avg_speed, avg_jitter, uid))
        return jsonify({
            "learning": True,
            "progress": min(100, int(count / LEARNING_SAMPLES * 100)),
            "risk_score": 0, "status": "Learning Mode"
        })

    # المراقبة
    diff = abs(speed - row[3]) + abs(jitter - row[4]) * 10
    risk_score = min(100, max(0, int(20 + diff)))
    status = ("Critical - Full Lockdown" if risk_score > RISK_CRITICAL
              else "Warning - Apps Locked" if risk_score > RISK_WARNING
              else "Secure")
    alerts = "🚨 انحراف كبير عن النمط السلوكي!" if risk_score > RISK_WARNING else "✅ السلوك متسق مع البصمة"

    if risk_score > RISK_WARNING:
        query("INSERT INTO risk_events (user_id, risk_score, status, alerts, created_at) VALUES (?,?,?,?,?)",
              (uid, risk_score, status, alerts, time.time()))

    return jsonify({
        "learning": False,
        "risk_score": risk_score,
        "status": status,
        "locked_apps": PERSONAL_APPS if risk_score > RISK_WARNING else [],
        "alerts": alerts
    })

@app.route('/security_log')
def security_log():
    if 'user' not in session:
        return redirect(url_for('login'))
    events = query("""
        SELECT risk_score, status, alerts, created_at
        FROM risk_events WHERE user_id=? ORDER BY created_at DESC LIMIT 50
    """, (session['user'],), fetch_all=True)
    samples = query("""
        SELECT typing_speed, mouse_jitter, created_at
        FROM learning_samples WHERE user_id=? ORDER BY created_at
    """, (session['user'],), fetch_all=True)
    return render_template('security_log.html', events=events, samples=samples)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=False)