# Heart Disease Prediction

A Flask web application that estimates cardiovascular risk from health
measurements using an ensemble of three machine learning models, with
role based access for Patients, Doctors and Admins.

## Features

- Risk assessment from 11 health inputs (age, BP, cholesterol, smoking, ...)
- Ensemble prediction: Logistic Regression + Random Forest + XGBoost,
  averaged into one probability with every model's individual vote shown
- Three roles: Patients run their own assessments, Doctors review and
  confirm or question the AI verdict with remarks, Admins manage users
  and view system wide statistics
- Doctor review workflow: patient requests a review, a doctor claims it
  from an anonymised pool (atomic claim, no double claiming), submits a
  verdict (Agree / Disagree), remarks, recommended tests and a follow-up
  date. New doctor sign-ups need admin approval before they can log in
- Downloadable one-page PDF report, generated with the Python standard
  library only (works fully offline), including the doctor's review
- AI vs Doctor agreement statistics on the admin model page
- CSRF protection on every form, PBKDF2 hashed passwords, parameterised
  SQL and server side validation on all inputs

## Tech stack

Python 3.13, Flask 3, SQLite, scikit-learn, XGBoost, pandas, plain
HTML/CSS/JavaScript (no front-end frameworks).

## Getting started

```bash
pip install -r requirements.txt
python train_model.py
python app.py
```

Then open http://127.0.0.1:5000

On first run the app creates `heart_disease.db` and seeds one admin
account:

- username: `admin`
- password: `admin123`

## Project structure

```
app.py             all web routes
database.py        SQLite layer (users, predictions, reviews)
ml_model.py        loads saved models, validates input, predicts
train_model.py     trains the models from data/heart.csv and saves them
test_project.py    self-contained test suite (python test_project.py)
templates/         Jinja2 pages
static/            styles, scripts and icon images
models/            saved scaler and trained models (created by training)
data/heart.csv     the training dataset
docs/              architecture and ML pipeline notes
```
