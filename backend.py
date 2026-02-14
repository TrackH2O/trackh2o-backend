from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import json, os, re, random, smtplib
from twilio.rest import Client
from flask import send_from_directory
from datetime import datetime
import tensorflow as tf
import numpy as np




app = Flask(__name__)
CORS(app)
model = tf.keras.models.load_model("water_waste_model_fixed.h5")

uploads_db = "uploads_db.json"
REPORT_FILE = "reports.json"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_images")
UPLOAD_FILE = os.path.join(BASE_DIR, "uploads.json")
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


# --------------------------------------------------------------
# FILE STORAGE
# --------------------------------------------------------------
PROFILES_FILE = "profiles.json"
USERS_FILE = "users.json"

# Create profiles.json if not exists
if not os.path.exists(PROFILES_FILE):
    with open(PROFILES_FILE, "w") as f:
        json.dump([], f)

# Create users.json if not exists
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        json.dump([], f)

# --------------------------------------------------------------
# Load & Save Functions
# --------------------------------------------------------------
def load_users():
    with open(USERS_FILE, "r") as f:
        data = json.load(f)
    return data.get("users", [])
def save_users(users_list):
    with open(USERS_FILE, "w") as f:
        json.dump({"users": users_list}, f, indent=4)


# --------------------------------------------------------------
# Validations
# --------------------------------------------------------------
def valid_username(u):
    return bool(re.match(r'^[A-Za-z0-9_.-]{3,50}$', u))

def valid_password(pw):
    return len(pw) >= 8

# --------------------------------------------------------------
# OTP SMS (Twilio)
# --------------------------------------------------------------
TWILIO_SID = 'ACdb70431781bafd027faa563ec67f0352'
TWILIO_AUTH_TOKEN = '003706503b6770f78239a6d4a19d5f95'
TWILIO_PHONE = '+18777804236'

client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

def send_sms(phone_number, otp):
    try:
        message = client.messages.create(
            body=f"Your OTP is {otp}",
            from_=TWILIO_PHONE,
            to=phone_number
        )
        print(f"SMS sent: {message.sid}")
        return True
    except Exception as e:
        print(f"SMS Error: {e}")
        return False

# --------------------------------------------------------------
# OTP EMAIL Setup
# --------------------------------------------------------------
EMAIL_ADDRESS = 'sihhackara@gmail.com'
EMAIL_PASSWORD = 'wnax xnkk zzez ahbb'

def send_email(to_email, otp):
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

        message = f"Subject: Your OTP\n\nYour OTP is: {otp}"
        server.sendmail(EMAIL_ADDRESS, to_email, message)
        server.quit()

        print(f"Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Email Error: {e}")
        return False

# --------------------------------------------------------------
# ROUTES
# --------------------------------------------------------------
@app.route("/")
def index():
    return "TRACK H2O BACKEND RUNNING OK"

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    
    input_data = np.array(data['input'])
    input_data = input_data.reshape(1, -1)

    prediction = model.predict(input_data)

    result = float(prediction[0][0])

    return jsonify({
        "prediction": result
    })

# --------------------------------------------------------------
# 1️⃣ CREATE USER ACCOUNT (WITH JSON STORAGE)
# --------------------------------------------------------------
@app.route('/create-account', methods=['POST'])
def create_account():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not valid_username(username):
        return jsonify({'message': 'Invalid username.'}), 400

    if not valid_password(password):
        return jsonify({'message': 'Password must be at least 8 characters.'}), 400

    users = load_users()

    # Check if username exists
    for user in users:
        if user.get("username") == username:
            return jsonify({'message': 'Username already exists.'}), 409

    pw_hash = generate_password_hash(password)

    users.append({
        "username": username,
        "password": pw_hash
    })

    save_users(users)

    return jsonify({'message': 'Account created successfully.'}), 201

# --------------------------------------------------------------
# 2️⃣ LOGIN USER (Check JSON Stored Password)
# --------------------------------------------------------------
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    users = load_users()  # Load JSON database (list of dicts)

    # Search for user by username
    user_found = None
    for user in users:
        if user.get("username") == username:
            user_found = user
            break

    if not user_found:
        return jsonify({"status": "error", "message": "User not found"}), 400

    # Check password
    if check_password_hash(user_found.get("password"), password):
        return jsonify({"status": "success", "message": "Login successful"}), 200
    else:
        return jsonify({"status": "error", "message": "Incorrect password"}), 400

# --------------------------------------------------------------
# 3️⃣ SEND OTP
# --------------------------------------------------------------
otp_store = {}  # email/phone : otp

@app.route('/send-otp', methods=['POST'])
def send_otp_route():
    data = request.json
    email = data.get('email')
    phone = data.get('phone')

    if not email and not phone:
        return jsonify({"status": "error", "message": "Email or phone required"}), 400

    otp = str(random.randint(100000, 999999))
    success = False

    if email:
        otp_store[email] = otp
        success = send_email(email, otp)

    if phone:
        otp_store[phone] = otp
        success = send_sms(phone, otp)

    if success:
        return jsonify({"status": "success", "message": "OTP sent!"})
    else:
        return jsonify({"status": "error", "message": "OTP sending failed"}), 500

# --------------------------------------------------------------
# 4️⃣ VERIFY OTP
# --------------------------------------------------------------
@app.route('/verify-otp', methods=['POST'])
def verify_otp_route():
    data = request.json
    email = data.get('email')
    phone = data.get('phone')
    otp = data.get('otp')

    if not otp:
        return jsonify({"status": "error", "message": "OTP required"}), 400

    if email and otp_store.get(email) == otp:
        del otp_store[email]
        return jsonify({"status": "success", "message": "OTP verified!"})

    if phone and otp_store.get(phone) == otp:
        del otp_store[phone]
        return jsonify({"status": "success", "message": "OTP verified!"})

    return jsonify({"status": "error", "message": "Invalid OTP"}), 400

# --------------------------------------------------------------
# 5️⃣ SAVE PROFILE
# --------------------------------------------------------------
@app.route("/create_profile", methods=["POST"])
def create_profile():
    try:
        data = request.get_json()

        with open(PROFILES_FILE, "r") as f:
            profiles = json.load(f)

        profiles.append(data)

        with open(PROFILES_FILE, "w") as f:
            json.dump(profiles, f, indent=4)

        return jsonify({"message": "Profile Saved"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
from datetime import datetime
from flask import send_from_directory


@app.route("/upload", methods=["POST"])
def upload():
    uploaded_by = request.form.get("uploaded_by", "")
    mobile = request.form.get("mobile", "")
    description = request.form.get("description", "")
    status = "Pending"

    # -------- Save Image --------
    image_file = request.files.get("image")
    image_name = ""
    image_path = ""

    if image_file:
        image_name = image_file.filename
        image_path = os.path.join(UPLOAD_FOLDER, image_name)
        image_file.save(image_path)

    # -------- Load old data --------
    if os.path.exists(UPLOAD_FILE):
        items = json.load(open(UPLOAD_FILE))
    else:
        items = []

    # -------- Create entry --------
    new_entry = {
        "id": len(items) + 1,
        "uploaded_by": uploaded_by,
        "mobile": mobile,
        "description": description,
        "image": image_name,
        "image_path": image_path,
        "status": status,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    items.append(new_entry)
    json.dump(items, open(UPLOAD_FILE, "w"), indent=4)

    return jsonify({"status": "saved"})





# Serve image files
@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route("/get-data", methods=["GET"])
def get_data():
    try:
        if not os.path.exists(UPLOAD_FILE):
            return jsonify([])

        with open(UPLOAD_FILE, "r") as f:
            data = json.load(f)

        return jsonify(data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



def load_uploads():
    try:
        with open("uploads.json", "r") as f:
            return json.load(f)
    except:
        return []

def save_uploads(data):
    with open("uploads.json", "w") as f:
        json.dump(data, f, indent=4)





# --------------------------------------------------------------
# 6️⃣ VIEW PROFILES (OPTIONAL)
# --------------------------------------------------------------
@app.route("/view_profiles", methods=["GET"])
def view_profiles():
    with open(PROFILES_FILE, "r") as f:
        profiles = json.load(f)
    return jsonify(profiles)

@app.route("/update-status", methods=["POST"])
def update_status():
    data = request.json
    # Save to database or file
    monitoring = load_monitoring_data()
    for item in monitoring:
        if item["id"] == data["id"]:
            item["status"] = data["status"]
    save_monitoring_data(monitoring)
    return jsonify({"success": True})
def load_monitoring_data():
    if not os.path.exists(UPLOAD_FILE):
        return []
    with open(UPLOAD_FILE, "r") as f:
        return json.load(f)

def save_monitoring_data(data):
    with open(UPLOAD_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_reports():
    if not os.path.exists(REPORT_FILE):
        return []
    try:
        with open(REPORT_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []

def save_reports(data):
    with open(REPORT_FILE, "w") as f:
        json.dump(data, f, indent=4)

def clear_reports():
    save_reports([])  # overwrite with empty list
    return jsonify({"success": True, "message": "All reports cleared."})

# backend.py
# This file is ONLY for Kivy storage (no Flask server here)
class Backend:
    def __init__(self):
        self.uploads = []

backend = Backend()

# --------------------------------------------------------------
# RUN SERVER
# --------------------------------------------------------------
if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
