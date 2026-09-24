import json
import os
import re
import secrets
from datetime import date, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort, Response)
import database
import ml_model
app = Flask(__name__)
app.secret_key = os.environ.get("HDP_SECRET_KEY", "dev-only-key-change-me")
app.permanent_session_lifetime = timedelta(hours=12)
database.init_db()
ml_model.init()
ROLE_PATIENT = database.ROLE_PATIENT
ROLE_DOCTOR = database.ROLE_DOCTOR
ROLE_ADMIN = database.ROLE_ADMIN


def current_user():
    return session.get("user")


def login_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please sign in first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please sign in first.", "warning")
            return redirect(url_for("login"))
        if current_user().get("role") != ROLE_ADMIN:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def doctor_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash("Please sign in first.", "warning")
            return redirect(url_for("login"))
        if current_user().get("role") not in (ROLE_DOCTOR, ROLE_ADMIN):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


@app.before_request
def check_csrf():
    if request.method == "POST":
        expected = session.get("_csrf_token")
        supplied = request.form.get("csrf_token")
        if not expected or not supplied \
                or not secrets.compare_digest(expected, supplied):
            abort(400, description="Security token missing or invalid. "
                                   "Please go back and try again.")


@app.context_processor
def template_helpers():
    return {
        "csrf_token": csrf_token,
        "current_user": current_user(),
        "ROLE_PATIENT": ROLE_PATIENT,
        "ROLE_DOCTOR": ROLE_DOCTOR,
        "ROLE_ADMIN": ROLE_ADMIN,
    }


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Please enter both a username and a password.", "warning")
            return render_template("login.html")
        user, status = database.validate_login(username, password)
        if status == "ok":
            session.clear()
            session["user"] = user
            session.permanent = True
            flash(f"Welcome back, {user['fullname'] or user['username']}.", "success")
            return redirect(url_for("dashboard"))
        elif status == "banned":
            flash("This account has been suspended. Contact an administrator.", "danger")
        elif status == "pending":
            flash("Your doctor account is waiting for admin approval.", "warning")
        else:
            flash("Invalid username or password.", "danger")
    return render_template("login.html")


def validate_registration(username, fullname, email, password, confirm):
    errors = []
    if not re.fullmatch(r"[A-Za-z0-9_]{3,20}", username or ""):
        errors.append("Username must be 3-20 characters: letters, numbers "
                      "and underscores only.")
    if not (fullname and 2 <= len(fullname) <= 60):
        errors.append("Please enter your full name (up to 60 characters).")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", email or ""):
        errors.append("Please enter a valid email address.")
    if len(password or "") < 8 or not re.search(r"[A-Za-z]", password) \
            or not re.search(r"\d", password):
        errors.append("Password must be at least 8 characters and mix "
                      "letters with numbers.")
    if password != confirm:
        errors.append("The two passwords do not match.")
    if not errors and database.username_exists(username):
        errors.append("That username is already taken.")
    if not errors and database.email_exists(email):
        errors.append("An account already exists with that email address.")
    return errors


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user():
        return redirect(url_for("dashboard"))
    form = {}
    if request.method == "POST":
        is_doctor = (request.form.get("register_as") or "") == "Doctor"
        form = {
            "register_as": "Doctor" if is_doctor else "Patient",
            "username": (request.form.get("username") or "").strip(),
            "fullname": (request.form.get("fullname") or "").strip(),
            "email": (request.form.get("email") or "").strip(),
            "specialization": (request.form.get("specialization") or "").strip(),
            "license_no": (request.form.get("license_no") or "").strip(),
        }
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm_password") or ""
        errors = validate_registration(form["username"], form["fullname"],
                                       form["email"], password, confirm)
        if is_doctor:
            if not (2 <= len(form["specialization"]) <= 80):
                errors.append("Please enter your specialization "
                              "(2-80 characters), e.g. Cardiology.")
            if not re.fullmatch(r"[A-Za-z0-9\-/]{3,40}", form["license_no"] or ""):
                errors.append("Please enter a valid license number "
                              "(3-40 characters: letters, numbers, - or /).")
        if errors:
            for message in errors:
                flash(message, "warning")
        else:
            _, error = database.register_user(
                form["username"], password,
                ROLE_DOCTOR if is_doctor else ROLE_PATIENT,
                form["fullname"], form["email"],
                specialization=form["specialization"] if is_doctor else None,
                license_no=form["license_no"] if is_doctor else None,
                is_approved=0 if is_doctor else 1)
            if error == "taken":
                flash("That username is already taken.", "warning")
            elif is_doctor:
                flash("Doctor account created. You can sign in once an "
                      "administrator has approved it.", "success")
                return redirect(url_for("login"))
            else:
                flash("Account created. You can sign in now.", "success")
                return redirect(url_for("login"))
    return render_template("register.html", form=form)


@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


def _scope_user_id(user):
    return None if user["role"] == ROLE_ADMIN else user["id"]


@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    if user["role"] == ROLE_DOCTOR:
        return redirect(url_for("doctor_dashboard"))
    predictions = database.get_predictions(user_id=_scope_user_id(user))
    high = sum(1 for p in predictions if p["predicted_class"] == 1)
    low = len(predictions) - high
    last = predictions[0] if predictions else None
    results = ml_model.get_results()
    best_model = results.get("best_model")
    best_accuracy = results.get("models", {}).get(best_model, {}).get("accuracy")
    trend = [{"label": (p["timestamp"] or "")[:16],
              "value": round(p["probability"] * 100, 1)}
             for p in list(reversed(predictions[:10]))]
    return render_template("dashboard.html",
                           predictions=predictions[:10],
                           total=len(predictions), high=high, low=low,
                           last=last, trend=trend,
                           best_model=best_model, best_accuracy=best_accuracy,
                           engine_ready=ml_model.is_ready())


@app.route("/diagnosis", methods=["GET", "POST"])
@login_required
def diagnosis_form():
    if request.method == "GET":
        if current_user()["role"] == ROLE_DOCTOR:
            flash("Doctors do not run assessments - review patient "
                  "requests from your dashboard instead.", "info")
            return redirect(url_for("doctor_dashboard"))
        if not ml_model.is_ready():
            flash("No trained model found. Run:  python train_model.py", "danger")
        return render_template("predict.html", form={},
                               engine_ready=ml_model.is_ready())
    if current_user()["role"] == ROLE_DOCTOR:
        abort(403)
    if not ml_model.is_ready():
        flash("No trained model found. Run:  python train_model.py", "danger")
        return redirect(url_for("diagnosis_form"))
    form = request.form.to_dict()
    ok, errors = ml_model.validate_input(form)
    if not ok:
        for message in errors:
            flash(message, "warning")
        return render_template("predict.html", form=form, engine_ready=True)
    vector, readable = ml_model.prepare_input(form)
    try:
        outcome = ml_model.predict(vector)
    except Exception:
        app.logger.exception("Prediction failed")
        flash("Something went wrong while predicting.", "danger")
        return redirect(url_for("diagnosis_form"))
    user = current_user()
    saved_id = None
    try:
        saved_id = database.add_prediction(
            user["id"], readable, outcome["predicted_class"],
            outcome["probability"], outcome["model_used"],
            votes=outcome["votes"])
    except Exception:
        app.logger.exception("Could not save prediction")
        flash("The result is valid but could not be saved.", "warning")
    risk = ml_model.get_risk_level(outcome["probability"])
    return render_template("result.html",
                           outcome=outcome, risk=risk,
                           tips=ml_model.get_tips(risk["label"]),
                           bmi_category=ml_model.get_bmi_category(readable["bmi"]),
                           readable=readable,
                           level_labels=ml_model.LEVEL_LABELS,
                           saved_id=saved_id,
                           review=database.get_review_for_prediction(saved_id)
                           if saved_id else None)


@app.route("/history")
@login_required
def history():
    user = current_user()
    predictions = database.get_predictions(user_id=_scope_user_id(user))
    verdict = request.args.get("verdict", "all")
    if verdict == "high":
        predictions = [p for p in predictions if p["predicted_class"] == 1]
    elif verdict == "low":
        predictions = [p for p in predictions if p["predicted_class"] == 0]
    search = (request.args.get("q") or "").strip().lower()
    if search:
        predictions = [p for p in predictions
                       if search in str(p.get("model_used", "")).lower()]
    review_map = database.get_reviews_for_predictions([p["id"] for p in predictions])
    rows = [{**p, "risk": ml_model.get_risk_level(p["probability"]),
             "review": review_map.get(p["id"])}
            for p in predictions]
    return render_template("history.html", rows=rows, verdict=verdict,
                           search=search,
                           is_personal=(user["role"] != ROLE_ADMIN))


@app.route("/report/<int:pred_id>")
@login_required
def report(pred_id):
    return redirect(url_for("report_pdf", pred_id=pred_id))


def _build_pdf(lines):
    content = []
    y = 800
    for bold, size, text in lines:
        text = str(text).encode("latin-1", "replace").decode("latin-1")
        text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.append(f"BT /F{2 if bold else 1} {size} Tf 50 {y} Td ({text}) Tj ET")
        y -= size + 5
    stream = "\n".join(content).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF").encode()
    return bytes(out)


def _wrap_pdf_text(text, width=88, max_lines=8):
    text = " ".join(str(text or "").split())
    if not text:
        return []
    out = []
    while text and len(out) < max_lines:
        if len(text) <= width:
            out.append(text)
            text = ""
        else:
            cut = text.rfind(" ", 0, width)
            if cut < 20:
                cut = width
            out.append(text[:cut])
            text = text[cut:].strip()
    if text:
        if out:
            out[-1] = out[-1][:width - 3].rstrip() + "..."
        else:
            out.append(text[:width])
    return out


@app.route("/report-pdf/<int:pred_id>")
@login_required
def report_pdf(pred_id):
    user = current_user()
    record = database.get_prediction_by_id(pred_id)
    if not record:
        abort(404)
    review = database.get_review_for_prediction(pred_id)
    if not (record["user_id"] == user["id"] or user["role"] == ROLE_ADMIN
            or (review and review["doctor_id"] == user["id"])):
        abort(403)
    risk = ml_model.get_risk_level(record["probability"])
    bmi = round(record["weight"] / ((record["height"] / 100) ** 2), 2)
    labels = ml_model.LEVEL_LABELS
    try:
        votes = json.loads(record["votes_json"]) if record["votes_json"] else {}
    except (TypeError, ValueError):
        votes = {}
    lines = [
        (True, 15, "HEART DISEASE PREDICTION - RISK REPORT"),
        (False, 10, "Screening tool, educational use only, NOT a medical diagnosis."),
        (False, 8, ""),
        (True, 12, "Report details"),
        (False, 10, f"Report ID : {record['id']}    Date/Time: {record['timestamp']}"),
        (False, 10, f"Account   : {record.get('account_name') or record.get('account')}"),
        (False, 8, ""),
        (True, 12, "Clinical indicators"),
        (False, 10, f"Age: {int(record['age'])} years    Gender: "
                    f"{'Male' if record['gender'] == 1 else 'Female'}"),
        (False, 10, f"Height: {int(record['height'])} cm    "
                    f"Weight: {record['weight']} kg    BMI: {bmi}"),
        (False, 10, f"Systolic BP: {int(record['ap_hi'])} mmHg    "
                    f"Diastolic BP: {int(record['ap_lo'])} mmHg"),
        (False, 10, f"Pulse pressure: {int(record['ap_hi'] - record['ap_lo'])} mmHg"),
        (False, 10, f"Cholesterol: {labels.get(record['cholesterol'], record['cholesterol'])}"
                    f"    Glucose: {labels.get(record['gluc'], record['gluc'])}"),
        (False, 10, f"Smoker: {'Yes' if record['smoke'] else 'No'}    "
                    f"Alcohol: {'Yes' if record['alco'] else 'No'}    "
                    f"Active: {'Yes' if record['active'] else 'No'}"),
        (False, 8, ""),
        (True, 12, "AI prediction"),
        (False, 11, f"Ensemble (average of the models): "
                    f"{record['probability']:.1%}  ->  {risk['label']}"),
        (False, 10, f"Model used: {record['model_used']}"),
    ]
    if votes:
        lines.append((True, 11, "Single model breakdown"))
        for name, prob in votes.items():
            verdict = "High Risk" if prob >= 0.5 else "Low Risk"
            lines.append((False, 10, f"   {name}: {prob:.1%}  ({verdict})"))
    if review and review["status"] == "Reviewed":
        doctor_line = f"Reviewed by: {review.get('doctor_name') or 'Doctor'}"
        if review.get("doctor_specialization"):
            doctor_line += f"  ({review['doctor_specialization']})"
        lines.append((False, 8, ""))
        lines.append((True, 12, "Doctor review"))
        lines.append((False, 10, doctor_line))
        lines.append((False, 10, f"Verdict: {review['verdict']} - the doctor "
                                 f"{'agrees' if review['verdict'] == 'Agree' else 'disagrees'} "
                                 f"with the AI assessment."))
        for index, wrapped in enumerate(
                _wrap_pdf_text(review.get("notes"))):
            prefix = "Remarks: " if index == 0 else " " * 9
            lines.append((False, 10, f"{prefix}{wrapped}"))
        if review.get("recommended_tests"):
            for index, wrapped in enumerate(
                    _wrap_pdf_text(review["recommended_tests"],
                                   max_lines=3)):
                prefix = "Recommended tests: " if index == 0 else " " * 19
                lines.append((False, 10, f"{prefix}{wrapped}"))
        if review.get("follow_up_date"):
            lines.append((False, 10,
                          f"Follow-up date: {review['follow_up_date']}"))
    lines += [
        (False, 8, ""),
        (True, 10, "IMPORTANT - PLEASE READ"),
        (False, 9, "This is a SCREENING TOOL, NOT A MEDICAL DIAGNOSIS. It estimates risk"),
        (False, 9, "from statistical patterns in population data and can be wrong in both"),
        (False, 9, "directions. Always consult a qualified doctor before acting on any result."),
    ]
    return Response(_build_pdf(lines), mimetype="application/pdf",
                    headers={"Content-Disposition":
                             f"attachment; filename=heart_report_{pred_id}.pdf"})


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        fullname = (request.form.get("fullname") or "").strip()
        email = (request.form.get("email") or "").strip()
        new_password = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        errors = []
        if not fullname:
            errors.append("Your full name is required.")
        if "@" not in email:
            errors.append("A valid email address is required.")
        if new_password:
            if len(new_password) < 8:
                errors.append("The new password must be at least 8 characters.")
            if new_password != confirm:
                errors.append("The two passwords do not match.")
        if errors:
            for message in errors:
                flash(message, "warning")
            return redirect(url_for("profile"))
        database.update_user_profile(user["id"], fullname, email,
                                     new_password or None)
        refreshed = dict(session["user"])
        refreshed["fullname"], refreshed["email"] = fullname, email
        session["user"] = refreshed
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    record = database.get_user_by_id(user["id"]) or user
    return render_template("profile.html", record=record)


def _prediction_report_context(record):
    risk = ml_model.get_risk_level(record["probability"])
    bmi = round(record["weight"] / ((record["height"] / 100) ** 2), 2)
    try:
        votes = json.loads(record["votes_json"]) if record["votes_json"] else {}
    except (TypeError, ValueError):
        votes = {}
    return risk, bmi, votes


@app.route("/review/request/<int:pred_id>", methods=["POST"])
@login_required
def request_doctor_review(pred_id):
    user = current_user()
    if user["role"] != ROLE_PATIENT:
        abort(403)
    record = database.get_prediction_by_id(pred_id)
    if not record:
        abort(404)
    if record["user_id"] != user["id"]:
        abort(403)
    if database.request_review(pred_id, user["id"]):
        flash("Review requested. A doctor will look at it soon.", "success")
    else:
        flash("A doctor review was already requested for this "
              "assessment.", "info")
    return redirect(url_for("history"))


@app.route("/review/<int:review_id>", methods=["GET"])
@login_required
def view_review(review_id):
    user = current_user()
    review = database.get_review_by_id(review_id)
    if not review:
        abort(404)
    if not (review["patient_id"] == user["id"]
            or review["doctor_id"] == user["id"]
            or user["role"] == ROLE_ADMIN):
        abort(403)
    record = database.get_prediction_by_id(review["prediction_id"])
    if not record:
        abort(404)
    risk, bmi, votes = _prediction_report_context(record)
    return render_template("review.html", review=review, record=record,
                           risk=risk, bmi=bmi, votes=votes,
                           level_labels=ml_model.LEVEL_LABELS, can_edit=False)


@app.route("/doctor")
@doctor_required
def doctor_dashboard():
    user = current_user()
    pool = [{**r, "risk": ml_model.get_risk_level(r["probability"])}
            for r in database.get_pending_reviews()]
    in_progress = database.get_reviews_for_doctor(user["id"],
                                                  status="In Review")
    completed = database.get_reviews_for_doctor(user["id"],
                                                status="Reviewed")
    return render_template("doctor.html", pool=pool,
                           in_progress=in_progress, completed=completed)


@app.route("/doctor/claim/<int:review_id>", methods=["POST"])
@doctor_required
def doctor_claim(review_id):
    user = current_user()
    if user["role"] != ROLE_DOCTOR:
        abort(403)
    if database.claim_review(review_id, user["id"]):
        flash(f"Review #{review_id} claimed - it is now under "
              f"'My reviews in progress'.", "success")
    else:
        flash("That review was already taken by another doctor.", "warning")
    return redirect(url_for("doctor_dashboard"))


@app.route("/doctor/review/<int:review_id>", methods=["GET", "POST"])
@doctor_required
def doctor_review(review_id):
    user = current_user()
    review = database.get_review_by_id(review_id)
    if not review:
        abort(404)
    is_admin = user["role"] == ROLE_ADMIN
    if not is_admin and review["doctor_id"] != user["id"]:
        abort(403)
    record = database.get_prediction_by_id(review["prediction_id"])
    if not record:
        abort(404)
    risk, bmi, votes = _prediction_report_context(record)
    if review["status"] == "Reviewed":
        flash("This review is finished and can no longer be edited.", "info")
        return render_template("review.html", review=review, record=record,
                               risk=risk, bmi=bmi, votes=votes,
                               level_labels=ml_model.LEVEL_LABELS,
                               can_edit=False)
    if request.method == "POST":
        if is_admin:
            flash("Admins can read reviews but not submit them.", "warning")
        else:
            verdict = request.form.get("verdict") or ""
            notes = (request.form.get("notes") or "").strip()
            tests = (request.form.get("recommended_tests") or "").strip()
            follow = (request.form.get("follow_up_date") or "").strip()
            errors = []
            if verdict not in ("Agree", "Disagree"):
                errors.append("Please choose Agree or Disagree.")
            if not notes:
                errors.append("Please write your remarks.")
            elif len(notes) > 1000:
                errors.append("Remarks must be 1000 characters or fewer.")
            if len(tests) > 300:
                errors.append("Recommended tests must be 300 characters "
                              "or fewer.")
            follow_date = None
            if follow:
                try:
                    follow_date = date.fromisoformat(follow)
                    if follow_date < date.today():
                        errors.append("The follow-up date cannot be in "
                                      "the past.")
                except ValueError:
                    errors.append("Enter the follow-up date in "
                                  "YYYY-MM-DD format.")
            if errors:
                for message in errors:
                    flash(message, "warning")
            elif database.submit_review(review_id, user["id"], verdict,
                                        notes, tests or None, follow or None):
                flash("Review submitted. The patient can now see your "
                      "remarks.", "success")
                return redirect(url_for("doctor_dashboard"))
            else:
                flash("Could not save the review - it may have been "
                      "closed already.", "danger")
    return render_template("review.html", review=review, record=record,
                           risk=risk, bmi=bmi, votes=votes,
                           level_labels=ml_model.LEVEL_LABELS, can_edit=True)


@app.route("/admin/users")
@admin_required
def admin_users():
    users = database.get_all_users()
    counts = database.count_predictions_by_user()
    rows = [{**u, "count": counts.get(u["id"], 0)} for u in users]
    return render_template("users.html", rows=rows,
                           pending_doctors=database.get_pending_doctors())


@app.route("/admin/users/<int:user_id>/approve", methods=["POST"])
@admin_required
def admin_approve_doctor(user_id):
    target = database.get_user_by_id(user_id)
    if not target:
        flash("That user no longer exists.", "warning")
    elif target["role"] != ROLE_DOCTOR:
        flash("Only doctor accounts need approval.", "warning")
    elif target["is_approved"]:
        flash(f"{target['username']} is already approved.", "info")
    else:
        database.approve_doctor(user_id)
        flash(f"Dr. {target['fullname'] or target['username']} has been "
              f"approved and can now sign in.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/role", methods=["POST"])
@admin_required
def admin_change_role(user_id):
    actor = current_user()
    new_role = request.form.get("role", "")
    target = database.get_user_by_id(user_id)
    if new_role not in (ROLE_PATIENT, ROLE_DOCTOR, ROLE_ADMIN):
        flash("Unknown role.", "warning")
    elif not target:
        flash("That user no longer exists.", "warning")
    elif user_id == actor["id"]:
        flash("You cannot change your own role.", "danger")
    elif (target["role"] == ROLE_ADMIN and new_role != ROLE_ADMIN
            and database.count_active_admins() <= 1):
        flash("This is the only admin - promote someone else first.", "danger")
    else:
        database.update_user_role(user_id, new_role)
        flash(f"{target['username']} is now a {new_role}.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def admin_ban(user_id):
    actor = current_user()
    target = database.get_user_by_id(user_id)
    if not target:
        flash("That user no longer exists.", "warning")
    elif user_id == actor["id"]:
        flash("You cannot suspend your own account.", "danger")
    elif target["is_banned"]:
        database.unban_user(user_id)
        flash(f"{target['username']} has been reinstated.", "success")
    elif (target["role"] == ROLE_ADMIN
            and database.count_active_admins() <= 1):
        flash("This is the only admin - promote someone else first.", "danger")
    else:
        database.ban_user(user_id)
        flash(f"{target['username']} has been suspended.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    actor = current_user()
    target = database.get_user_by_id(user_id)
    if not target:
        flash("That user no longer exists.", "warning")
    elif user_id == actor["id"]:
        flash("You cannot delete your own account.", "danger")
    elif (target["role"] == ROLE_ADMIN
            and database.count_active_admins() <= 1):
        flash("This is the only admin - promote someone else first.", "danger")
    else:
        database.delete_user(user_id)
        flash(f"Account '{target['username']}' has been deleted.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/predictions")
@admin_required
def admin_predictions():
    records = database.get_predictions()
    verdict = request.args.get("verdict", "all")
    if verdict == "high":
        records = [r for r in records if r["predicted_class"] == 1]
    elif verdict == "low":
        records = [r for r in records if r["predicted_class"] == 0]
    rows = [{**r, "risk": ml_model.get_risk_level(r["probability"])}
            for r in records]
    return render_template("predictions.html", rows=rows, verdict=verdict)


@app.route("/admin/predictions/<int:pred_id>/delete", methods=["POST"])
@admin_required
def admin_delete_prediction(pred_id):
    database.delete_prediction(pred_id)
    flash(f"Prediction #{pred_id} deleted.", "success")
    return redirect(url_for("admin_predictions"))


@app.route("/admin/models")
@admin_required
def admin_models():
    results = ml_model.get_results()
    models = results.get("models", {})
    rows = [{"name": name, **data} for name, data in models.items()]
    rows.sort(key=lambda r: (-r.get("roc_auc", 0), -r.get("cv_auc", 0)))
    best = results.get("best_model")
    best_row = None
    for r in rows:
        if r["name"] == best:
            best_row = r
    if best_row is None and rows:
        best_row = rows[0]
    return render_template("models.html",
                           rows=rows,
                           best=best,
                           best_row=best_row,
                           rows_used=results.get("rows_used"),
                           trained_at=results.get("trained_at"),
                           importances=ml_model.get_feature_importances(),
                           review_stats=database.get_review_stats())


@app.errorhandler(400)
def bad_request(e):
    return render_template("errors/400.html",
                           message=getattr(e, "description", None)), 400


@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403


@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"Internal error on {request.path}: {e}", exc_info=True)
    return render_template("errors/500.html"), 500
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 56)
    print("  Heart Disease Prediction")
    print("  Running at  : http://127.0.0.1:%d" % port)
    print("  Default user: admin / admin123   (role: Admin)")
    print("  Press CTRL+C to stop")
    print("=" * 56)
    try:
        from waitress import serve
        serve(app, host="0.0.0.0", port=port)
    except ImportError:
        app.run(host="0.0.0.0", port=port, debug=False)
