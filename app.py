import streamlit as st
import cv2
import numpy as np
from PIL import Image
from ultralytics import YOLO

# Load model
model = YOLO("helm_model_best.pt")

st.title("Deteksi Helm APD dengan YOLOv8")
st.markdown("Upload gambar untuk deteksi helm atau tanpa helm")

uploaded_file = st.file_uploader("Upload Gambar", type=["jpg", "jpeg", "png"])
if uploaded_file is not None:
    img = Image.open(uploaded_file).convert("RGB")
    img_np = np.array(img)

    st.image(img_np, caption="Gambar Asli", use_column_width=True)

    # Deteksi
    results = model.predict(img_np)[0]
    result_img = results.plot()

    st.image(result_img, caption="Hasil Deteksi", use_column_width=True)
