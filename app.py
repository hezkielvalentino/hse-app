# ✅ Versi Real-time Web App dengan Streamlit, mirip PyQt5 asli Anda

import streamlit as st
import cv2
import numpy as np
from ultralytics import YOLO
from twilio.rest import Client
from datetime import datetime
import time
import os
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import tempfile

# --- Konfigurasi Twilio ---
TWILIO_SID = 'ACfc8ee62a79cf75df3938842948f1b214'
TWILIO_AUTH_TOKEN = '9110685da319480bc648e0d741d78ac7'
TWILIO_FROM = 'whatsapp:+14155238886'
TWILIO_TO = 'whatsapp:+6285156708175'
client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

# --- Inisialisasi Google Drive ---
try:
    gauth = GoogleAuth()
    gauth.LocalWebserverAuth()
    drive = GoogleDrive(gauth)
    folder_id = '1q2J3b_Er31OAQE0N74b9Q6fQ29-D6cnI'
except Exception as e:
    drive = None
    st.warning(f"[!] Gagal autentikasi GDrive: {e}")

# --- Load model YOLO ---
model = YOLO("helm_model_best.pt")
class_names = {0: "helmet", 1: "no_helmet"}
last_capture_time = 0
cooldown = 60

st.set_page_config(layout="wide")
st.title("🚧 Deteksi Helm Real-time Web")

# --- Kamera ---
run = st.checkbox("🎥 Mulai Deteksi Kamera")
FRAME_WINDOW = st.image([])
log_box = st.empty()

cap = cv2.VideoCapture(0)

while run:
    ret, frame = cap.read()
    if not ret:
        st.warning("[!] Tidak bisa membaca kamera.")
        break

    results = model(frame, conf=0.7)[0]
    for box in results.boxes:
        conf = box.conf[0]
        if conf < 0.5:
            continue
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        cls_id = int(box.cls[0])
        label = class_names.get(cls_id, "unknown")
        color = (0, 255, 0) if label == "helmet" else (0, 0, 255)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        if label == "no_helmet" and time.time() - last_capture_time > cooldown:
            now = datetime.now()
            timestamp = now.strftime("%Y%m%d-%H%M%S")
            msg_time = now.strftime("%d %B %Y %H:%M:%S")
            filename = f"no_helmet_{timestamp}.jpg"

            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                path = tmp.name
                cv2.imwrite(path, frame)

            try:
                gfile = drive.CreateFile({'title': filename, 'parents': [{'id': folder_id}]})
                gfile.SetContentFile(path)
                gfile.Upload()
                gfile.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
                media_url = f"https://drive.google.com/uc?export=view&id={gfile['id']}"
                client.messages.create(
                    body=f"Pelanggaran APD terdeteksi pada {msg_time}",
                    from_=TWILIO_FROM,
                    to=TWILIO_TO,
                    media_url=[media_url]
                )
                os.remove(path)
                log_box.success(f"[✓] Pelanggaran dikirim: {msg_time}")
            except Exception as e:
                log_box.error(f"[!] Gagal upload/kirim: {e}")

            last_capture_time = time.time()

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    FRAME_WINDOW.image(rgb)

cap.release()
st.write("👁️ Deteksi dihentikan.")
