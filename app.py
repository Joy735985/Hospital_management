from flask import Flask, render_template, request, redirect, session, url_for, flash
from db import get_connection
import bcrypt

app = Flask(__name__)
app.secret_key = "change_this_secret_key"


def get_user(username):
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM app_users WHERE username=%s", (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def login_required():
    return "user_id" in session


def username_exists(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM app_users WHERE username=%s LIMIT 1", (username,))
    exists = cur.fetchone() is not None
    cur.close()
    conn.close()
    return exists


@app.route("/")
def home():
    if not login_required():
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "doctor").strip()

        allowed_roles = {"admin", "doctor", "nurse", "labtech", "receptionist", "accountant"}
        if role not in allowed_roles:
            flash("Invalid role")
            return redirect(url_for("signup"))

        if not username or not password:
            flash("Username and password are required")
            return redirect(url_for("signup"))

        if username_exists(username):
            flash("Username already exists")
            return redirect(url_for("signup"))

        pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO app_users(username, password_hash, role) VALUES (%s, %s, %s)",
            (username, pw_hash, role)
        )
        conn.commit()
        cur.close()
        conn.close()

        flash("Account created. Please login.")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").encode("utf-8")

        user = get_user(username)
        if not user:
            flash("Invalid username or password")
            return redirect(url_for("login"))

        stored_hash = user["password_hash"].encode("utf-8")
        if bcrypt.checkpw(password, stored_hash):
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect(url_for("dashboard"))

        flash("Invalid username or password")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM patients")
    patients_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM visits")
    visits_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM diagnoses")
    diagnoses_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM prescriptions")
    prescriptions_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM lab_results")
    lab_results_count = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "dashboard.html",
        patients_count=patients_count,
        visits_count=visits_count,
        diagnoses_count=diagnoses_count,
        prescriptions_count=prescriptions_count,
        lab_results_count=lab_results_count
    )


@app.route("/patients", methods=["GET", "POST"])
def patients():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    action = request.form.get("action", "")

    if request.method == "POST" and action == "add":
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        user_id = session["user_id"]

        cur.execute("""
            INSERT INTO patients (full_name, phone, address, created_by, updated_by)
            VALUES (%s, %s, %s, %s, %s)
        """, (full_name, phone, address, user_id, user_id))
        conn.commit()
        return redirect(url_for("patients"))

    if request.method == "POST" and action == "update":
        patient_id = request.form["patient_id"]
        full_name = request.form.get("full_name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        user_id = session["user_id"]

        cur.execute("""
            UPDATE patients
            SET full_name=%s, phone=%s, address=%s, updated_by=%s
            WHERE patient_id=%s
        """, (full_name, phone, address, user_id, patient_id))
        conn.commit()
        return redirect(url_for("patients"))

    if request.method == "POST" and action == "delete":
        patient_id = request.form["patient_id"]
        user_id = session["user_id"]

        cur.execute("""
            UPDATE patients
            SET is_deleted=1, updated_by=%s
            WHERE patient_id=%s
        """, (user_id, patient_id))
        conn.commit()
        return redirect(url_for("patients"))

    search = request.args.get("q", "").strip()

    if search:
        cur.execute("""
            SELECT * FROM patients
            WHERE is_deleted=0 AND (full_name LIKE %s OR phone LIKE %s)
            ORDER BY patient_id ASC
        """, (f"%{search}%", f"%{search}%"))
    else:
        cur.execute("""
            SELECT * FROM patients
            WHERE is_deleted=0
            ORDER BY patient_id ASC
        """)

    patients_list = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("patients.html", patients=patients_list, q=search)


@app.route("/visits", methods=["GET", "POST"])
def visits():
    if not login_required():
        return redirect(url_for("login"))
    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        patient_id = request.form["patient_id"]
        chief_complaint = request.form.get("chief_complaint", "")
        notes = request.form.get("notes", "")
        user_id = session["user_id"]

        cur.execute(
            """
            INSERT INTO visits (patient_id, doctor_id, chief_complaint, notes, status, created_by, updated_by)
            VALUES (%s, %s, %s, %s, 'open', %s, %s)
            """,
            (patient_id, user_id, chief_complaint, notes, user_id, user_id)
        )
        conn.commit()

    cur.execute("SELECT patient_id, full_name FROM patients ORDER BY patient_id ASC")
    patient_list = cur.fetchall()

    cur.execute("""
        SELECT v.visit_id, v.patient_id, p.full_name, v.visit_time, v.status, v.chief_complaint
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_id ASC
    """)
    visits_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("visits.html", patients=patient_list, visits=visits_list)


@app.route("/diagnoses", methods=["GET", "POST"])
def diagnoses():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        visit_id = request.form["visit_id"]
        diagnosis_text = request.form["diagnosis_text"]
        severity = request.form.get("severity", "low")
        reason = request.form.get("reason", "")
        user_id = session["user_id"]

        cur.execute(
            """
            INSERT INTO diagnoses (visit_id, diagnosis_text, severity, reason, created_by, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (visit_id, diagnosis_text, severity, reason, user_id, user_id)
        )
        conn.commit()

    cur.execute("""
        SELECT v.visit_id, p.full_name
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_id ASC
    """)
    visit_list = cur.fetchall()

    cur.execute("""
        SELECT d.diagnosis_id, d.visit_id, p.full_name, d.diagnosis_text, d.severity, d.reason, d.created_at
        FROM diagnoses d
        JOIN visits v ON d.visit_id = v.visit_id
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY d.diagnosis_id ASC
    """)
    diagnoses_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("diagnoses.html", visits=visit_list, diagnoses=diagnoses_list)


@app.route("/doctors", methods=["GET", "POST"])
def doctors():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        doctor_user_id = request.form["doctor_user_id"]
        specialization = request.form.get("specialization", "")
        availability_note = request.form.get("availability_note", "")

        cur.execute("""
            INSERT INTO doctors (doctor_id, specialization, availability_note)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE specialization=VALUES(specialization), availability_note=VALUES(availability_note)
        """, (doctor_user_id, specialization, availability_note))
        conn.commit()

    cur.execute("SELECT user_id, username FROM app_users WHERE role='doctor' ORDER BY user_id ASC")
    doctor_users = cur.fetchall()

    cur.execute("""
        SELECT d.doctor_id, u.username, d.specialization, d.availability_note
        FROM doctors d
        JOIN app_users u ON d.doctor_id = u.user_id
        ORDER BY d.doctor_id ASC
    """)
    doctor_profiles = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("doctors.html", doctor_users=doctor_users, doctor_profiles=doctor_profiles)


@app.route("/appointments", methods=["GET", "POST"])
def appointments():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    action = request.form.get("action", "")

    if request.method == "POST" and action == "create":
        patient_id = request.form["patient_id"]
        doctor_id = request.form["doctor_id"]
        appointment_time = request.form["appointment_time"]
        reason = request.form.get("reason", "")
        user_id = session["user_id"]

        cur.execute("""
            INSERT INTO appointments
            (patient_id, doctor_id, appointment_time, status, reason, created_by, updated_by)
            VALUES (%s, %s, %s, 'booked', %s, %s, %s)
        """, (patient_id, doctor_id, appointment_time, reason, user_id, user_id))
        conn.commit()

    if request.method == "POST" and action == "reschedule":
        appointment_id = request.form["appointment_id"]
        new_time = request.form["appointment_time"]
        user_id = session["user_id"]

        cur.execute("""
            UPDATE appointments
            SET appointment_time=%s, status='rescheduled', updated_by=%s
            WHERE appointment_id=%s
        """, (new_time, user_id, appointment_id))
        conn.commit()

    if request.method == "POST" and action == "cancel":
        appointment_id = request.form["appointment_id"]
        user_id = session["user_id"]

        cur.execute("""
            UPDATE appointments
            SET status='cancelled', updated_by=%s
            WHERE appointment_id=%s
        """, (user_id, appointment_id))
        conn.commit()

    patient_q = request.args.get("patient", "").strip()
    doctor_q  = request.args.get("doctor", "").strip()
    status_q  = request.args.get("status", "").strip()

    sql = """
        SELECT a.appointment_id, a.appointment_time, a.status, a.reason,
               p.full_name,
               u.username AS doctor_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        JOIN app_users u ON a.doctor_id = u.user_id
        WHERE 1=1
    """
    params = []

    if patient_q:
        sql += " AND p.full_name LIKE %s"
        params.append(f"%{patient_q}%")
    if doctor_q:
        sql += " AND u.username LIKE %s"
        params.append(f"%{doctor_q}%")
    if status_q:
        sql += " AND a.status=%s"
        params.append(status_q)

    sql += " ORDER BY a.appointment_id DESC"
    cur.execute(sql, tuple(params))
    appt_list = cur.fetchall()

    cur.execute("SELECT patient_id, full_name FROM patients ORDER BY patient_id ASC")
    patients_list = cur.fetchall()

    cur.execute("SELECT user_id, username FROM app_users WHERE role='doctor' ORDER BY user_id ASC")
    doctors_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "appointments.html",
        patients=patients_list,
        doctors=doctors_list,
        appts=appt_list,
        patient_q=patient_q,
        doctor_q=doctor_q,
        status_q=status_q
    )


@app.route("/prescriptions", methods=["GET", "POST"])
def prescriptions():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        visit_id      = request.form["visit_id"]
        medicine_name = request.form["medicine_name"]
        dose          = request.form.get("dose", "")
        frequency     = request.form.get("frequency", "")
        duration_days = request.form.get("duration_days", "")
        reason        = request.form.get("reason", "")
        user_id       = session["user_id"]

        cur.execute(
            """
            INSERT INTO prescriptions
            (visit_id, medicine_name, dose, frequency, duration_days, status, reason, created_by, updated_by)
            VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s)
            """,
            (visit_id, medicine_name, dose, frequency,
             duration_days if duration_days else None, reason, user_id, user_id)
        )
        conn.commit()

    cur.execute("""
        SELECT v.visit_id, p.full_name
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_id ASC
    """)
    visit_list = cur.fetchall()

    cur.execute("""
        SELECT pr.prescription_id, pr.visit_id, p.full_name, pr.medicine_name, pr.dose, pr.frequency,
               pr.duration_days, pr.status, pr.reason, pr.created_at
        FROM prescriptions pr
        JOIN visits v ON pr.visit_id = v.visit_id
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY pr.prescription_id ASC
    """)
    prescriptions_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("prescriptions.html", visits=visit_list, prescriptions=prescriptions_list)


@app.route("/lab_results", methods=["GET", "POST"])
def lab_results():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        visit_id     = request.form["visit_id"]
        test_name    = request.form["test_name"]
        result_value = request.form.get("result_value", "")
        unit         = request.form.get("unit", "")
        normal_range = request.form.get("normal_range", "")
        status       = request.form.get("status", "pending")
        reason       = request.form.get("reason", "")
        user_id      = session["user_id"]

        cur.execute(
            """
            INSERT INTO lab_results
            (visit_id, test_name, result_value, unit, normal_range, status, reason, created_by, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (visit_id, test_name, result_value, unit, normal_range, status, reason, user_id, user_id)
        )
        conn.commit()

    cur.execute("""
        SELECT v.visit_id, p.full_name
        FROM visits v
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY v.visit_id ASC
    """)
    visit_list = cur.fetchall()

    cur.execute("""
        SELECT lr.lab_result_id, lr.visit_id, p.full_name, lr.test_name, lr.result_value, lr.unit,
               lr.normal_range, lr.status, lr.reason, lr.created_at
        FROM lab_results lr
        JOIN visits v ON lr.visit_id = v.visit_id
        JOIN patients p ON v.patient_id = p.patient_id
        ORDER BY lr.lab_result_id ASC
    """)
    lab_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("lab_results.html", visits=visit_list, labs=lab_list)


# ── PHARMACY ────────────────────────────────────────────────
@app.route("/pharmacy", methods=["GET", "POST"])
def pharmacy():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    if request.method == "POST":
        action = request.form.get("action", "add")

        if action == "add":
            medicine_name = request.form.get("medicine_name", "").strip()
            category      = request.form.get("category", "").strip()
            stock_qty     = request.form.get("stock_qty", 0)
            unit_price    = request.form.get("unit_price", 0.0)
            expiry_date   = request.form.get("expiry_date", "") or None

            cur.execute("""
                INSERT INTO medicines (medicine_name, category, stock_qty, unit_price, expiry_date)
                VALUES (%s, %s, %s, %s, %s)
            """, (medicine_name, category, stock_qty, unit_price, expiry_date))
            conn.commit()

        elif action == "update_stock":
            medicine_id = request.form.get("medicine_id")
            stock_qty   = request.form.get("stock_qty", 0)

            cur.execute("""
                UPDATE medicines SET stock_qty=%s WHERE medicine_id=%s
            """, (stock_qty, medicine_id))
            conn.commit()

    # Search / filter
    search = request.args.get("q", "").strip()
    if search:
        cur.execute("""
            SELECT * FROM medicines
            WHERE medicine_name LIKE %s OR category LIKE %s
            ORDER BY medicine_name ASC
        """, (f"%{search}%", f"%{search}%"))
    else:
        cur.execute("SELECT * FROM medicines ORDER BY medicine_name ASC")

    medicines_list = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("pharmacy.html", medicines=medicines_list, q=search)


# ── AUDIT ────────────────────────────────────────────────────
@app.route("/audit")
def audit():
    if "user_id" not in session:
        return redirect(url_for("login"))

    table     = request.args.get("table", "patients")
    record_id = request.args.get("record_id", "").strip()

    conn = get_connection()
    cur = conn.cursor(dictionary=True)

    logs = []

    if table == "patients":
        sql = """
            SELECT a.audit_id, a.patient_id AS record_id, a.operation_type, a.changed_at, u.username,
                   a.old_full_name, a.new_full_name, a.old_phone, a.new_phone, a.old_address, a.new_address
            FROM audit_patients a
            LEFT JOIN app_users u ON a.actor_user_id = u.user_id
        """
        params = []
        if record_id:
            sql += " WHERE a.patient_id=%s"
            params.append(record_id)
        sql += " ORDER BY a.changed_at ASC"
        cur.execute(sql, tuple(params))
        logs = cur.fetchall()

    elif table == "visits":
        sql = """
            SELECT a.audit_id, a.visit_id AS record_id, a.operation_type, a.changed_at, u.username,
                   a.old_status, a.new_status
            FROM audit_visits a
            LEFT JOIN app_users u ON a.actor_user_id = u.user_id
        """
        params = []
        if record_id:
            sql += " WHERE a.visit_id=%s"
            params.append(record_id)
        sql += " ORDER BY a.changed_at ASC"
        cur.execute(sql, tuple(params))
        logs = cur.fetchall()

    elif table == "diagnoses":
        sql = """
            SELECT a.audit_id, a.diagnosis_id AS record_id, a.operation_type, a.changed_at, u.username,
                   a.old_diagnosis_text, a.new_diagnosis_text, a.old_severity, a.new_severity,
                   a.old_reason, a.new_reason
            FROM audit_diagnoses a
            LEFT JOIN app_users u ON a.actor_user_id = u.user_id
        """
        params = []
        if record_id:
            sql += " WHERE a.diagnosis_id=%s"
            params.append(record_id)
        sql += " ORDER BY a.changed_at ASC"
        cur.execute(sql, tuple(params))
        logs = cur.fetchall()

    elif table == "prescriptions":
        sql = """
            SELECT a.audit_id, a.prescription_id AS record_id, a.operation_type, a.changed_at, u.username,
                   a.old_status, a.new_status, a.old_reason, a.new_reason
            FROM audit_prescriptions a
            LEFT JOIN app_users u ON a.actor_user_id = u.user_id
        """
        params = []
        if record_id:
            sql += " WHERE a.prescription_id=%s"
            params.append(record_id)
        sql += " ORDER BY a.changed_at ASC"
        cur.execute(sql, tuple(params))
        logs = cur.fetchall()

    elif table == "lab_results":
        sql = """
            SELECT a.audit_id, a.lab_result_id AS record_id, a.operation_type, a.changed_at, u.username,
                   a.old_status, a.new_status, a.old_result_value, a.new_result_value,
                   a.old_reason, a.new_reason
            FROM audit_lab_results a
            LEFT JOIN app_users u ON a.actor_user_id = u.user_id
        """
        params = []
        if record_id:
            sql += " WHERE a.lab_result_id=%s"
            params.append(record_id)
        sql += " ORDER BY a.changed_at ASC"
        cur.execute(sql, tuple(params))
        logs = cur.fetchall()

    elif table == "appointments":
        sql = """
            SELECT a.audit_id, a.appointment_id AS record_id, a.operation_type, a.changed_at, u.username,
                   a.old_status, a.new_status, a.old_time, a.new_time, a.old_reason, a.new_reason
            FROM audit_appointments a
            LEFT JOIN app_users u ON a.actor_user_id = u.user_id
        """
        params = []
        if record_id:
            sql += " WHERE a.appointment_id=%s"
            params.append(record_id)
        sql += " ORDER BY a.changed_at ASC"
        cur.execute(sql, tuple(params))
        logs = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("audit.html", logs=logs, table=table, record_id=record_id)


if __name__ == "__main__":
    app.run(debug=True)