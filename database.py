import os
import json
import sqlite3
import hashlib
import secrets
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "heart_disease.db")
PBKDF2_ITERATIONS = 260000
ROLE_PATIENT = "Patient"
ROLE_DOCTOR = "Doctor"
ROLE_ADMIN = "Admin"


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt,
                                 PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password, stored):
    if not stored:
        return False
    try:
        _, iterations, salt_hex, hash_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                     bytes.fromhex(salt_hex), int(iterations))
        return secrets.compare_digest(digest.hex(), hash_hex)
    except (ValueError, TypeError):
        return False


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            fullname TEXT,
            email TEXT,
            is_banned INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
    c.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            age REAL, gender INTEGER, height REAL, weight REAL,
            ap_hi REAL, ap_lo REAL, cholesterol INTEGER, gluc INTEGER,
            smoke INTEGER, alco INTEGER, active INTEGER,
            predicted_class INTEGER, probability REAL, model_used TEXT,
            votes_json TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )""")
    columns = [row[1] for row in c.execute("PRAGMA table_info(predictions)")]
    if "votes_json" not in columns:
        c.execute("ALTER TABLE predictions ADD COLUMN votes_json TEXT")
    columns = [row[1] for row in c.execute("PRAGMA table_info(users)")]
    if "specialization" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN specialization TEXT")
    if "license_no" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN license_no TEXT")
    if "is_approved" not in columns:
        c.execute("ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 1")
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER NOT NULL UNIQUE,
            patient_id INTEGER NOT NULL,
            doctor_id INTEGER,
            status TEXT NOT NULL DEFAULT 'Pending',
            verdict TEXT,
            notes TEXT,
            recommended_tests TEXT,
            follow_up_date TEXT,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            FOREIGN KEY(prediction_id) REFERENCES predictions(id)
                ON DELETE CASCADE,
            FOREIGN KEY(patient_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(doctor_id) REFERENCES users(id) ON DELETE SET NULL
        )""")
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO users (username, password_hash, role, fullname, email)
            VALUES (?, ?, ?, ?, ?)
        """, ("admin", hash_password("admin123"), ROLE_ADMIN,
              "Administrator", "admin@example.com"))
    conn.commit()
    conn.close()


def validate_login(username, password):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None, "invalid"
    if not verify_password(password, row["password_hash"]):
        return None, "invalid"
    if row["is_banned"]:
        return None, "banned"
    if row["role"] == ROLE_DOCTOR and not row["is_approved"]:
        return None, "pending"
    user = dict(row)
    del user["password_hash"]
    return user, "ok"


def register_user(username, password, role, fullname, email,
                  specialization=None, license_no=None, is_approved=1):
    conn = _connect()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, role, fullname,
                               email, specialization, license_no,
                               is_approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, hash_password(password), role, fullname, email,
              specialization, license_no, is_approved))
        conn.commit()
        return c.lastrowid, None
    except sqlite3.IntegrityError:
        return None, "taken"
    finally:
        conn.close()


def username_exists(username):
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE LOWER(username)=LOWER(?)",
              (username.strip(),))
    found = c.fetchone()[0] > 0
    conn.close()
    return found


def email_exists(email):
    if not email:
        return False
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE LOWER(email)=LOWER(?)",
              (email.strip(),))
    found = c.fetchone()[0] > 0
    conn.close()
    return found


def get_all_users():
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT id, username, role, fullname, email, is_banned,
                        specialization, license_no, is_approved, created_at
                 FROM users ORDER BY id""")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_user_by_id(user_id):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT id, username, role, fullname, email, is_banned,
                        specialization, license_no, is_approved, created_at
                 FROM users WHERE id=?""", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_profile(user_id, fullname, email, new_password=None):
    conn = _connect()
    c = conn.cursor()
    if new_password:
        c.execute("UPDATE users SET fullname=?, email=?, password_hash=? WHERE id=?",
                  (fullname, email, hash_password(new_password), user_id))
    else:
        c.execute("UPDATE users SET fullname=?, email=? WHERE id=?",
                  (fullname, email, user_id))
    conn.commit()
    conn.close()


def update_user_role(user_id, new_role):
    conn = _connect()
    conn.execute("UPDATE users SET role=? WHERE id=?", (new_role, user_id))
    conn.commit()
    conn.close()


def ban_user(user_id):
    conn = _connect()
    conn.execute("UPDATE users SET is_banned=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def unban_user(user_id):
    conn = _connect()
    conn.execute("UPDATE users SET is_banned=0 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = _connect()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def count_active_admins():
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE role=? AND is_banned=0",
              (ROLE_ADMIN,))
    total = c.fetchone()[0]
    conn.close()
    return total


def get_pending_doctors():
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT id, username, fullname, email, specialization,
                        license_no, created_at
                 FROM users
                 WHERE role=? AND is_approved=0 AND is_banned=0
                 ORDER BY created_at""", (ROLE_DOCTOR,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def approve_doctor(user_id):
    conn = _connect()
    conn.execute("UPDATE users SET is_approved=1 WHERE id=? AND role=?",
                 (user_id, ROLE_DOCTOR))
    conn.commit()
    conn.close()


def count_predictions_by_user():
    conn = _connect()
    c = conn.cursor()
    c.execute("SELECT user_id, COUNT(*) FROM predictions GROUP BY user_id")
    counts = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return counts


def add_prediction(user_id, values, predicted_class, probability, model_used,
                   votes=None):
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        INSERT INTO predictions
        (user_id, age, gender, height, weight, ap_hi, ap_lo,
         cholesterol, gluc, smoke, alco, active,
         predicted_class, probability, model_used, votes_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (user_id, values["age"], values["gender"], values["height"],
          values["weight"], values["ap_hi"], values["ap_lo"],
          values["cholesterol"], values["gluc"], values["smoke"],
          values["alco"], values["active"],
          predicted_class, probability, model_used,
          json.dumps(votes) if votes else None))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id


def get_predictions(user_id=None):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if user_id:
        c.execute("SELECT * FROM predictions WHERE user_id=? ORDER BY timestamp DESC",
                  (user_id,))
    else:
        c.execute("""SELECT p.*, u.username AS account
                     FROM predictions p JOIN users u ON p.user_id=u.id
                     ORDER BY p.timestamp DESC""")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_prediction_by_id(pred_id):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""SELECT p.*, u.username AS account, u.fullname AS account_name
                 FROM predictions p JOIN users u ON p.user_id=u.id
                 WHERE p.id=?""", (pred_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_prediction(pred_id):
    conn = _connect()
    conn.execute("DELETE FROM predictions WHERE id=?", (pred_id,))
    conn.commit()
    conn.close()


def request_review(prediction_id, patient_id):
    conn = _connect()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO reviews (prediction_id, patient_id)
            VALUES (?, ?)
        """, (prediction_id, patient_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def get_review_for_prediction(prediction_id):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT r.*,
               du.fullname AS doctor_name,
               du.username AS doctor_username,
               du.specialization AS doctor_specialization
        FROM reviews r
        LEFT JOIN users du ON r.doctor_id = du.id
        WHERE r.prediction_id=?
    """, (prediction_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_review_by_id(review_id):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT r.*,
               pu.fullname AS patient_name,
               pu.username AS patient_username,
               du.fullname AS doctor_name,
               du.username AS doctor_username,
               du.specialization AS doctor_specialization
        FROM reviews r
        JOIN users pu ON r.patient_id = pu.id
        LEFT JOIN users du ON r.doctor_id = du.id
        WHERE r.id=?
    """, (review_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_reviews():
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT r.id, r.prediction_id, r.requested_at,
               p.age, p.gender, p.probability, p.predicted_class
        FROM reviews r
        JOIN predictions p ON r.prediction_id = p.id
        WHERE r.doctor_id IS NULL AND r.status='Pending'
        ORDER BY r.requested_at
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_reviews_for_doctor(doctor_id, status=None):
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if status:
        c.execute("""
            SELECT r.*, p.probability AS ai_probability,
                   p.timestamp AS predicted_at,
                   pu.fullname AS patient_name,
                   pu.username AS patient_username
            FROM reviews r
            JOIN predictions p ON r.prediction_id = p.id
            JOIN users pu ON r.patient_id = pu.id
            WHERE r.doctor_id=? AND r.status=?
            ORDER BY r.requested_at DESC
        """, (doctor_id, status))
    else:
        c.execute("""
            SELECT r.*, p.probability AS ai_probability,
                   p.timestamp AS predicted_at,
                   pu.fullname AS patient_name,
                   pu.username AS patient_username
            FROM reviews r
            JOIN predictions p ON r.prediction_id = p.id
            JOIN users pu ON r.patient_id = pu.id
            WHERE r.doctor_id=?
            ORDER BY r.requested_at DESC
        """, (doctor_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_reviews_for_predictions(prediction_ids):
    if not prediction_ids:
        return {}
    conn = _connect()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    marks = ",".join("?" * len(prediction_ids))
    c.execute(f"""
        SELECT r.*, du.fullname AS doctor_name
        FROM reviews r
        LEFT JOIN users du ON r.doctor_id = du.id
        WHERE r.prediction_id IN ({marks})
    """, tuple(prediction_ids))
    found = {row["prediction_id"]: dict(row) for row in c.fetchall()}
    conn.close()
    return found


def claim_review(review_id, doctor_id):
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        UPDATE reviews
        SET doctor_id=?, status='In Review'
        WHERE id=? AND doctor_id IS NULL AND status='Pending'
    """, (doctor_id, review_id))
    won = c.rowcount == 1
    conn.commit()
    conn.close()
    return won


def submit_review(review_id, doctor_id, verdict, notes,
                  recommended_tests=None, follow_up_date=None):
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        UPDATE reviews
        SET status='Reviewed', verdict=?, notes=?, recommended_tests=?,
            follow_up_date=?, reviewed_at=CURRENT_TIMESTAMP
        WHERE id=? AND doctor_id=? AND status='In Review'
    """, (verdict, notes, recommended_tests, follow_up_date,
          review_id, doctor_id))
    saved = c.rowcount == 1
    conn.commit()
    conn.close()
    return saved


def get_review_stats():
    conn = _connect()
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN verdict='Agree' THEN 1 ELSE 0 END),
               SUM(CASE WHEN verdict='Disagree' THEN 1 ELSE 0 END)
        FROM reviews WHERE status='Reviewed'
    """)
    reviewed, agree, disagree = c.fetchone()
    conn.close()
    agreement = round(100.0 * agree / reviewed, 1) if reviewed else None
    return {"reviewed": reviewed, "agree": agree or 0,
            "disagree": disagree or 0, "agreement": agreement}
