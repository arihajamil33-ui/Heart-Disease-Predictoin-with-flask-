import os
import json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
passed = 0
failed = 0
failures = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        failures.append(name)
        print(f"  FAIL  {name}   {detail}")
print("\n[1] FEATURE FUNCTION")
import ml_model
import train_model
check("training imports the SAME function the app uses",
      train_model.compute_derived_features is ml_model.compute_derived_features)
bmi, pp = ml_model.compute_derived_features(170, 70, 120, 80)
check("BMI of 170cm / 70kg is 24.22", bmi == 24.22, f"got {bmi}")
check("Pulse pressure of 120/80 is 40", pp == 40, f"got {pp}")
check("BMI is clipped at the top (70)",
      ml_model.compute_derived_features(100, 200, 120, 80)[0] == 70)
check("BMI is clipped at the bottom (10)",
      ml_model.compute_derived_features(250, 20, 120, 80)[0] == 10)
print("\n[2] INPUT VALIDATION")
good = {"age": "45", "gender": "1", "height": "170", "weight": "70",
        "ap_hi": "120", "ap_lo": "80", "cholesterol": "1", "gluc": "1",
        "smoke": "0", "alco": "0", "active": "1"}
ok, errors = ml_model.validate_input(good)
check("a normal form passes validation", ok, str(errors))
check("no error messages for a good form", errors == [], str(errors))
check("age below 18 is rejected",
      ml_model.validate_input(dict(good, age="15"))[0] is False)
check("systolic below diastolic is rejected",
      ml_model.validate_input(dict(good, ap_hi="80", ap_lo="120"))[0] is False)
check("cholesterol code 7 is rejected",
      ml_model.validate_input(dict(good, cholesterol="7"))[0] is False)
missing = dict(good)
del missing["weight"]
check("a missing field is rejected", ml_model.validate_input(missing)[0] is False)
check("an impossible BMI is rejected",
      ml_model.validate_input(dict(good, height="250", weight="20"))[0] is False)
print("\n[3] MODEL PREDICTION")
ml_model.init()
check("model engine is ready", ml_model.is_ready())
for fname in ["scaler.pkl", "logistic_regression.pkl", "random_forest.pkl",
              "xgboost.pkl", "features.json", "results.json"]:
    check(f"models/{fname} exists",
          os.path.exists(os.path.join(MODELS_DIR, fname)))
results = ml_model.get_results()
check("results.json names a best model",
      results.get("best_model") in ml_model.MODEL_FILES,
      str(results.get("best_model")))
vector, readable = ml_model.prepare_input(good)
check("feature vector has 13 values", len(vector) == 13, f"got {len(vector)}")
with open(os.path.join(MODELS_DIR, "features.json")) as f:
    saved_features = json.load(f)
check("feature order matches models/features.json",
      saved_features == ml_model.FEATURE_ORDER)
healthy = dict(good, age="30", gender="0", height="165", weight="55",
               ap_hi="110", ap_lo="70", cholesterol="1",
               smoke="0", alco="0", active="1")
risky = dict(good, age="65", gender="1", height="170", weight="95",
             ap_hi="160", ap_lo="95", cholesterol="3",
             smoke="1", alco="1", active="0")
low_outcome = ml_model.predict(ml_model.prepare_input(healthy)[0])
high_outcome = ml_model.predict(ml_model.prepare_input(risky)[0])
check("prediction returns a probability",
      0.0 <= low_outcome["probability"] <= 1.0)
check("healthy sample scores LOWER than the risky sample",
      low_outcome["probability"] < high_outcome["probability"],
      f"{low_outcome['probability']:.3f} vs {high_outcome['probability']:.3f}")
check("predicted_class follows the 0.5 threshold",
      high_outcome["predicted_class"] == (1 if high_outcome["probability"] >= 0.5 else 0))
check("all three models produced a vote",
      set(high_outcome["votes"]) == set(ml_model.MODEL_FILES))
check("ensemble probability is the average of the votes",
      abs(high_outcome["probability"]
          - sum(high_outcome["votes"].values()) / len(high_outcome["votes"])) < 1e-9)
check("the ensemble name is recorded with the result",
      high_outcome["model_used"].startswith("Ensemble"))
risk = ml_model.get_risk_level(low_outcome["probability"])
check("low probability maps to LOW RISK", risk["label"] == "LOW RISK")
risk = ml_model.get_risk_level(0.9)
check("high probability maps to HIGH RISK", risk["label"] == "HIGH RISK")
print("\n[4] DATABASE")
import database
database.init_db()
hashed = database.hash_password("secret123")
check("the hash never contains the plain password", "secret123" not in hashed)
check("the correct password verifies",
      database.verify_password("secret123", hashed))
check("a wrong password fails",
      not database.verify_password("wrongpass", hashed))
TEST_USER = "test_user_934"
for u in database.get_all_users():
    if u["username"] in (TEST_USER, "web_test_934"):
        database.delete_user(u["id"])
new_id, err = database.register_user(
    TEST_USER, "test1234", database.ROLE_PATIENT, "Test User", "test934@example.com")
check("user registration works", err is None and new_id is not None)
check("a duplicate username is rejected",
      database.register_user(
          TEST_USER, "x1234567", database.ROLE_PATIENT, "Dup", "dup@example.com")[1] == "taken")
user, status = database.validate_login(TEST_USER, "test1234")
check("login with the correct password works",
      status == "ok" and user["username"] == TEST_USER)
check("login never returns the password hash",
      "password_hash" not in (user or {}))
_, status = database.validate_login(TEST_USER, "wrongpass")
check("login with a wrong password fails", status == "invalid")
pred_id = database.add_prediction(new_id, readable, 0, 0.25, "Random Forest")
rows = database.get_predictions(user_id=new_id)
check("a prediction is saved for the user",
      len(rows) == 1 and rows[0]["probability"] == 0.25)
rec = database.get_prediction_by_id(pred_id)
check("a single prediction can be fetched",
      rec is not None and rec["account"] == TEST_USER)
database.delete_prediction(pred_id)
check("the prediction is deleted", database.get_predictions(user_id=new_id) == [])
database.delete_user(new_id)
check("the test user is deleted", database.get_user_by_id(new_id) is None)
print("\n[5] WEB PAGES")
from app import app as flask_app
client = flask_app.test_client()
DEPLOYED_MODEL = ml_model.predict(ml_model.prepare_input(good)[0])["model_used"]


def post(url, data):
    with client.session_transaction() as s:
        s["_csrf_token"] = "test-token"
    return client.post(url, data={**data, "csrf_token": "test-token"})
r = client.get("/")
check("a signed-out visitor is sent to the login page",
      r.status_code == 302 and "/login" in r.headers["Location"])
r = post("/login", {"username": "admin", "password": "wrong"})
check("a wrong password is refused", r.status_code == 200 and b"Invalid" in r.data)
WEB_USER = "web_test_934"
r = post("/register", {"username": WEB_USER, "fullname": "Web Test",
                       "email": "web934@example.com",
                       "password": "web12345", "confirm_password": "web12345"})
check("registration accepts a valid form", r.status_code == 302)
r = post("/login", {"username": WEB_USER, "password": "web12345"})
check("login works after registration", r.status_code == 302)
r = client.get("/dashboard")
check("the dashboard loads", r.status_code == 200)
r = client.get("/diagnosis")
check("the assessment form loads",
      r.status_code == 200 and b"predictForm" in r.data)
r = post("/diagnosis", good)
check("the prediction page returns a result",
      r.status_code == 200 and b"RISK" in r.data.upper())
r = client.get("/history")
check("history lists the new record",
      r.status_code == 200 and DEPLOYED_MODEL.encode() in r.data)
all_records = database.get_predictions()
mine = [p for p in all_records if p.get("account") == WEB_USER]
check("the prediction was stored in the database", len(mine) >= 1)
r = client.get(f"/report/{mine[0]['id']}", follow_redirects=True)
check("the old .txt report address redirects to the PDF report",
      r.status_code == 200 and r.data[:4] == b"%PDF")
r = client.get(f"/report-pdf/{mine[0]['id']}")
check("the PDF report downloads (single + ensemble results)",
      r.status_code == 200 and r.data[:4] == b"%PDF")
r = client.get("/admin/users")
check("a patient is blocked from admin pages (403)", r.status_code == 403)
client.get("/logout")
r = post("/login", {"username": "admin", "password": "admin123"})
check("the admin account can sign in", r.status_code == 302)
r = client.get("/admin/users")
check("the admin users page loads", r.status_code == 200)
r = client.get("/admin/predictions")
check("the admin predictions page loads", r.status_code == 200)
r = client.get("/admin/models")
check("the admin model page loads", r.status_code == 200 and b"ROC AUC" in r.data)
fresh_client = flask_app.test_client()
r = fresh_client.post("/login", data={"username": "admin", "password": "admin123"})
check("a POST without a CSRF token is rejected (400)", r.status_code == 400)
for u in database.get_all_users():
    if u["username"] == WEB_USER:
        database.delete_user(u["id"])
check("the web test user is cleaned up", not database.username_exists(WEB_USER))
print("\n[6] DOCTOR REVIEW")
from datetime import date, timedelta


def cpost(c, url, data):
    with c.session_transaction() as s:
        s["_csrf_token"] = "test-token"
    return c.post(url, data={**data, "csrf_token": "test-token"})


def user_by_name(username):
    for u in database.get_all_users():
        if u["username"] == username:
            return u
    return None
DOC1, DOC2 = "doc_amir_934", "doc_sara_934"
PAT2, PAT3 = "pat_bilal_934", "pat_sara_934"
TADMIN, EVIL = "test_admin_934", "evil_934"
for uname in (DOC1, DOC2, PAT2, PAT3, TADMIN, EVIL):
    victim = user_by_name(uname)
    if victim:
        database.delete_user(victim["id"])
client.get("/logout")
_, err = database.register_user(TADMIN, "admin123", database.ROLE_ADMIN,
                                "Test Admin", "tadmin934@example.com")
check("the test admin account is created", err is None)
r = post("/register", {"register_as": "Doctor", "username": DOC1,
                       "fullname": "Dr Amir", "email": "amir934@example.com",
                       "specialization": "Cardiology", "license_no": "PMC-111",
                       "password": "doc12345", "confirm_password": "doc12345"})
check("doctor registration is accepted", r.status_code == 302)
doc1 = user_by_name(DOC1)
check("a new doctor has the Doctor role and is unapproved",
      doc1 and doc1["role"] == database.ROLE_DOCTOR
      and not doc1["is_approved"])
r = post("/register", {"register_as": "Admin", "username": EVIL,
                       "fullname": "Evil User", "email": "evil934@example.com",
                       "password": "evil12345", "confirm_password": "evil12345"})
evil = user_by_name(EVIL)
check("posting register_as=Admin still creates only a Patient",
      evil and evil["role"] == database.ROLE_PATIENT)
r = post("/register", {"register_as": "Doctor", "username": "doc_bad_934",
                       "fullname": "Dr Bad", "email": "bad934@example.com",
                       "specialization": "", "license_no": "",
                       "password": "bad12345", "confirm_password": "bad12345"})
check("a doctor form without specialization/license is rejected",
      r.status_code == 200 and not user_by_name("doc_bad_934"))
r = post("/login", {"username": DOC1, "password": "doc12345"})
check("an unapproved doctor cannot sign in",
      r.status_code == 200 and b"waiting for admin approval" in r.data)
admin_c = flask_app.test_client()
r = cpost(admin_c, "/login", {"username": TADMIN, "password": "admin123"})
check("the test admin can sign in", r.status_code == 302)
r = cpost(admin_c, f"/admin/users/{doc1['id']}/approve", {})
check("admin approval succeeds", r.status_code == 302)
check("doctor 1 is now approved",
      database.get_user_by_id(doc1["id"])["is_approved"] == 1)
r = post("/register", {"register_as": "Doctor", "username": DOC2,
                       "fullname": "Dr Sara", "email": "sara934@example.com",
                       "specialization": "Medicine", "license_no": "PMC-222",
                       "password": "doc22345", "confirm_password": "doc22345"})
doc2 = user_by_name(DOC2)
database.approve_doctor(doc2["id"])
r = post("/login", {"username": DOC1, "password": "doc12345"})
check("the approved doctor can sign in", r.status_code == 302)
r = client.get("/doctor")
check("the doctor dashboard loads",
      r.status_code == 200 and b"Pending pool" in r.data)
r = client.get("/diagnosis")
check("a doctor is blocked from the assessment form (redirect)",
      r.status_code == 302 and "/doctor" in r.headers["Location"])
r = client.get("/admin/users")
check("a doctor is blocked from admin pages (403)", r.status_code == 403)
pat_c = flask_app.test_client()
r = cpost(pat_c, "/register",
          {"username": PAT2, "fullname": "Bilal Ahmed",
           "email": "bilal934@example.com",
           "password": "pat12345", "confirm_password": "pat12345"})
check("patient 2 registration works", r.status_code == 302)
r = cpost(pat_c, "/login", {"username": PAT2, "password": "pat12345"})
check("patient 2 can sign in", r.status_code == 302)
r = cpost(pat_c, "/diagnosis", good)
check("patient 2 gets a prediction result",
      r.status_code == 200 and b"RISK" in r.data.upper())
pred = [p for p in database.get_predictions()
        if p.get("account") == PAT2][0]
r = cpost(pat_c, f"/review/request/{pred['id']}", {})
check("the review request is accepted", r.status_code == 302)
review = database.get_review_for_prediction(pred["id"])
check("the review starts as Pending with no doctor",
      review and review["status"] == "Pending"
      and review["doctor_id"] is None)
r = cpost(pat_c, f"/review/request/{pred['id']}", {})
check("a second request for the same prediction is refused",
      r.status_code == 302
      and database.get_review_for_prediction(pred["id"])["id"] == review["id"])
pat3_c = flask_app.test_client()
cpost(pat3_c, "/register", {"username": PAT3, "fullname": "Sara Patient",
                            "email": "saraP934@example.com",
                            "password": "pat52345", "confirm_password": "pat52345"})
cpost(pat3_c, "/login", {"username": PAT3, "password": "pat52345"})
r = cpost(pat3_c, f"/review/request/{pred['id']}", {})
check("a patient cannot request a review for someone else (403)",
      r.status_code == 403)
r = post(f"/review/request/{pred['id']}", {})
check("a doctor cannot request reviews (403)", r.status_code == 403)
r = cpost(admin_c, f"/review/request/{pred['id']}", {})
check("an admin cannot request reviews (403)", r.status_code == 403)
r = post(f"/doctor/claim/{review['id']}", {})
check("doctor 1 claims the review", r.status_code == 302)
claimed = database.get_review_by_id(review["id"])
check("the claim marks it In Review with doctor 1",
      claimed["status"] == "In Review"
      and claimed["doctor_id"] == doc1["id"])
doc2_c = flask_app.test_client()
cpost(doc2_c, "/login", {"username": DOC2, "password": "doc22345"})
r = cpost(doc2_c, f"/doctor/claim/{review['id']}", {})
check("doctor 2 cannot claim the same review",
      r.status_code == 302
      and database.get_review_by_id(review["id"])["doctor_id"] == doc1["id"])
check("claim_review() is atomic at the database layer too",
      database.claim_review(review["id"], doc2["id"]) is False)
r = pat_c.get("/doctor")
check("a patient cannot open the doctor dashboard (403)",
      r.status_code == 403)
r = cpost(pat_c, f"/doctor/review/{review['id']}", {})
check("a patient cannot open a doctor review (403)", r.status_code == 403)
r = cpost(doc2_c, f"/doctor/review/{review['id']}", {})
check("a doctor who did not claim the review gets 403",
      r.status_code == 403)
r = client.get(f"/doctor/review/{review['id']}")
check("the claimed review opens with the form and model votes",
      r.status_code == 200 and b"Your verdict" in r.data
      and b"Model votes" in r.data)
r = post(f"/doctor/review/{review['id']}",
         {"verdict": "", "notes": ""})
check("an empty verdict form is rejected", r.status_code == 200)
r = post(f"/doctor/review/{review['id']}",
         {"verdict": "Agree", "notes": "Please describe your symptoms.",
          "follow_up_date": "2001-01-01"})
check("a follow-up date in the past is rejected", r.status_code == 200)
check("rejected submissions change nothing",
      database.get_review_by_id(review["id"])["status"] == "In Review")
follow = (date.today() + timedelta(days=14)).isoformat()
stats_before = database.get_review_stats()
r = post(f"/doctor/review/{review['id']}",
         {"verdict": "Agree", "notes": "Monitor BP twice daily and reduce salt.",
          "recommended_tests": "Lipid profile, ECG", "follow_up_date": follow})
check("a valid review is submitted", r.status_code == 302)
saved = database.get_review_by_id(review["id"])
check("the review is stored as Reviewed with all fields",
      saved["status"] == "Reviewed" and saved["verdict"] == "Agree"
      and saved["recommended_tests"] == "Lipid profile, ECG"
      and saved["follow_up_date"] == follow)
r = post(f"/doctor/review/{review['id']}",
         {"verdict": "Disagree", "notes": "Changed my mind."})
check("a reviewed record can never be edited again",
      r.status_code == 200
      and database.get_review_by_id(review["id"])["verdict"] == "Agree")
r = cpost(pat_c, "/history", {})
r = pat_c.get("/history")
check("the history page shows the Reviewed badge",
      r.status_code == 200 and b"Reviewed" in r.data)
r = pat_c.get(f"/review/{review['id']}")
check("the patient can open the review remarks",
      r.status_code == 200 and b"reduce salt" in r.data)
r = pat3_c.get(f"/review/{review['id']}")
check("another patient cannot open Bilal's review (403)",
      r.status_code == 403)
r = pat_c.get(f"/report-pdf/{pred['id']}")
check("the PDF contains the doctor review section",
      r.status_code == 200 and r.data[:4] == b"%PDF"
      and b"Doctor review" in r.data and b"reduce salt" in r.data)
r = admin_c.get("/admin/models")
check("the model page shows the AI vs Doctor agreement",
      r.status_code == 200 and b"AI vs Doctor agreement" in r.data)
stats = database.get_review_stats()
stats_expected = round(100.0 * (stats_before["agree"] + 1)
                       / (stats_before["reviewed"] + 1), 1)
check("the agreement statistics are correct",
      stats["reviewed"] == stats_before["reviewed"] + 1
      and stats["agree"] == stats_before["agree"] + 1
      and stats["agreement"] == stats_expected)
for uname in (DOC1, DOC2, PAT2, PAT3, TADMIN, EVIL):
    victim = user_by_name(uname)
    if victim:
        database.delete_user(victim["id"])
check("all doctor-review test accounts are cleaned up",
      not any(user_by_name(u) for u in (DOC1, DOC2, PAT2, PAT3, TADMIN, EVIL)))
print("\n" + "=" * 60)
print(f"  {passed} passed, {failed} failed")
if failures:
    print("  Failed checks:")
    for name in failures:
        print(f"    - {name}")
print("=" * 60)
