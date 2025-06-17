import sys
import os
import time
import locale
import psutil
from datetime import datetime
import cv2
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QLabel, QTextEdit, QVBoxLayout, 
    QHBoxLayout, QSizePolicy, QComboBox, QLineEdit
)
from PyQt5.QtGui import QImage, QPixmap, QIcon
from PyQt5.QtCore import QTimer, Qt
from ultralytics import YOLO
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from twilio.rest import Client

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Set locale waktu Indonesia
try:
    locale.setlocale(locale.LC_TIME, 'id_ID.UTF-8')
except:
    locale.setlocale(locale.LC_TIME, '')

# Twilio config (ganti dengan data asli kamu)
TWILIO_SID = 'ACfc8ee62a79cf75df3938842948f1b214'
TWILIO_AUTH_TOKEN = '9110685da319480bc648e0d741d78ac7'
TWILIO_FROM = 'whatsapp:+14155238886'
TWILIO_TO = 'whatsapp:+6285156708175'
twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

def send_whatsapp_image(media_url, message=""):
    try:
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_FROM,
            to=TWILIO_TO,
            media_url=[media_url]
        )
        return "[✓] Notifikasi dikirim via WhatsApp."
    except Exception as e:
        return f"[!] Gagal kirim WhatsApp: {e}"

class HelmetApp(QWidget):
    def __init__(self):
        super().__init__()

        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")

        icon_path = os.path.join(base_path, "hse.ico")
        self.setWindowTitle("HSE App")
        self.setWindowIcon(QIcon(icon_path))

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.camera_selector = QComboBox()
        self.camera_selector.addItem("Webcam Internal (0)", 0)
        self.camera_selector.addItem("USB/External Cam (1)", 1)
        self.camera_selector.addItem("IP Camera (masukkan URL)", "ip")

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("http://192.168.x.x:8080/video")
        self.ip_input.setVisible(False)

        self.start_button = QPushButton("Mulai Deteksi")
        self.stop_button = QPushButton("Berhenti")
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)

        self.camera_selector.currentIndexChanged.connect(self.toggle_ip_input)

        hbox = QHBoxLayout()
        hbox.addWidget(self.camera_selector)
        hbox.addWidget(self.ip_input)
        hbox.addWidget(self.start_button)
        hbox.addWidget(self.stop_button)

        vbox = QVBoxLayout()
        vbox.addWidget(self.image_label, stretch=1)
        vbox.addLayout(hbox)
        vbox.addWidget(self.log_text)
        self.setLayout(vbox)

        self.start_button.clicked.connect(self.start_detection)
        self.stop_button.clicked.connect(self.stop_detection)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.cap = None

        # Mencari folder simpan di drive yang tersedia
        relative_folder = os.path.join("hse-app", "pelanggaran-apd")
        self.save_folder = None
        for part in psutil.disk_partitions(all=False):
            mount = part.mountpoint
            try:
                test_path = os.path.join(mount, relative_folder)
                os.makedirs(test_path, exist_ok=True)
                self.save_folder = test_path
                self.log(f"[i] Folder simpan digunakan di: {self.save_folder}")
                break
            except Exception as e:
                self.log(f"[!] Tidak bisa gunakan drive {mount}: {e}")

        # Jika tidak dapat, fallback ke folder user
        if not self.save_folder:
            fallback = os.path.join(os.path.expanduser("~"), relative_folder)
            try:
                os.makedirs(fallback, exist_ok=True)
                self.save_folder = fallback
                self.log(f"[i] Folder simpan fallback digunakan di: {self.save_folder}")
            except Exception as e:
                self.log(f"[!] Gagal buat folder fallback: {e}")
                raise RuntimeError("Tidak ada folder yang bisa digunakan untuk menyimpan data.")

        # Ganti working directory ke folder simpan
        try:
            os.chdir(self.save_folder)
            self.log(f"[i] Working directory diubah ke: {os.getcwd()}")
        except Exception as e:
            self.log(f"[!] Gagal ubah working directory: {e}")

        model_path = os.path.join(base_path, "helm_model_best.pt")
        if not os.path.isfile(model_path):
            self.log(f"[!] File model '{model_path}' tidak ditemukan.")
            raise FileNotFoundError(f"Model file '{model_path}' tidak ditemukan.")
        self.model = YOLO(model_path)
        self.log(f"[✓] Model '{model_path}' berhasil dimuat.")

        self.class_names = {0: "helmet", 1: "no_helmet"}
        self.last_capture_time = 0
        self.cooldown = 60

        self.drive = self.init_drive()
        self.folder_id = '1q2J3b_Er31OAQE0N74b9Q6fQ29-D6cnI'

    def toggle_ip_input(self, index):
        selected = self.camera_selector.currentData()
        self.ip_input.setVisible(selected == "ip")

    def init_drive(self):
        gauth = GoogleAuth()
        client_secrets_file = "D:/hse-app/client_secrets.json"
        gauth.LoadClientConfigFile(client_secrets_file)
        gauth.LocalWebserverAuth()
        return GoogleDrive(gauth)

    def start_detection(self):
        selected = self.camera_selector.currentData()
        if selected == "ip":
            ip_url = self.ip_input.text()
            if not ip_url:
                self.log("[!] Masukkan URL IP Camera terlebih dahulu.")
                return
            self.cap = cv2.VideoCapture(ip_url)
        else:
            self.cap = cv2.VideoCapture(int(selected))

        if not self.cap.isOpened():
            self.log("[!] Gagal membuka kamera.")
            return

        self.timer.start(30)
        self.log("Deteksi dimulai.")

    def stop_detection(self):
        if self.cap:
            self.cap.release()
            self.cap = None
        self.timer.stop()
        self.image_label.clear()
        self.log("Deteksi dihentikan.")

    def update_frame(self):
        if not self.cap:
            return
        ret, frame = self.cap.read()
        if not ret:
            return

        results = self.model(frame, conf=0.7)[0]
        for box in results.boxes:
            conf = box.conf[0]
            if conf < 0.5:
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cls_id = int(box.cls[0])
            label = self.class_names.get(cls_id, "unknown")
            color = (0, 255, 0) if label == "helmet" else (0, 0, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame, f"{label} {conf:.2f}", (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            if label == "no_helmet" and time.time() - self.last_capture_time > self.cooldown:
                now = datetime.now()
                timestamp_readable = now.strftime("%d %B %Y %H:%M:%S")
                timestamp_filename = now.strftime("%Y%m%d-%H%M%S")
                filename = f"no_helmet_{timestamp_filename}.jpg"

                self.log(f"Menyimpan gambar ke: {os.path.join(self.save_folder, filename)}")
                cv2.imwrite(filename, frame)
                cv2.waitKey(1)
                time.sleep(0.2)

                try:
                    gfile = self.drive.CreateFile({'title': filename, 'parents': [{'id': self.folder_id}]})
                    gfile.SetContentFile(filename)
                    gfile.Upload()
                    gfile.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
                    media_url = f"https://drive.google.com/uc?export=view&id={gfile['id']}"

                    try:
                        self.log(f"Menghapus file lokal: {filename}")
                        os.remove(filename)
                        self.log(f"[✓] File '{filename}' berhasil dihapus.")
                    except Exception as e:
                        self.log(f"[!] Gagal menghapus file lokal: {e}")

                    log_msg = f"Pelanggaran APD terdeteksi pada {timestamp_readable}"
                    self.log(log_msg)
                    self.log(send_whatsapp_image(media_url, log_msg))

                except Exception as e:
                    self.log(f"[!] Gagal upload atau kirim: {e}")

                self.last_capture_time = time.time()

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled_pixmap)

    def log(self, message):
        self.log_text.append(message)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    base_path = os.path.abspath(".")
    icon_path = os.path.join(base_path, "hse.ico")
    app.setWindowIcon(QIcon(icon_path))

    window = HelmetApp()
    window.resize(800, 600)
    window.show()
    sys.exit(app.exec_())
