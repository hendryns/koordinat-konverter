import streamlit as st
import pandas as pd
import pyproj
import re
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os

# --- Bagian 1: Inisialisasi Firebase ---
def initialize_firebase():
    """Menginisialisasi Firebase Admin SDK."""
    try:
        # Untuk deployment Streamlit, gunakan secret yang didefinisikan
        if "FIREBASE_CREDENTIALS" in st.secrets:
            creds_json = st.secrets["FIREBASE_CREDENTIALS"]
            creds_dict = json.loads(creds_json)
            cred = credentials.Certificate(creds_dict)
        # Untuk pengembangan lokal, gunakan file JSON
        elif os.path.exists("firebase_credentials.json"):
            cred = credentials.Certificate("firebase_credentials.json")
        else:
            st.error("Firebase credentials not found. Please add 'firebase_credentials.json' or set it in Streamlit secrets.")
            return None, None

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        return db, True
    except Exception as e:
        st.error(f"Error initializing Firebase: {e}")
        return None, False

db, firebase_initialized = initialize_firebase()

# --- Bagian 2: Definisi Data dan Fungsi Bantuan ---

# Fungsi untuk mengonversi DMS ke Derajat Desimal (DD)
def dms_to_dd(dms_str):
    """Mengonversi string DMS menjadi derajat desimal."""
    try:
        parts = re.findall(r"[-+]?\d+\.?\d*", dms_str.replace(",", "."))
        d = float(parts[0])
        m = float(parts[1]) if len(parts) > 1 else 0
        s = float(parts[2]) if len(parts) > 2 else 0

        dd = abs(d) + m/60 + s/3600
        
        if re.search(r"[S|W]", dms_str, re.IGNORECASE):
            dd *= -1
        return dd
    except (IndexError, ValueError):
        return None

# Fungsi untuk mengonversi Derajat Desimal (DD) ke DMS
def dd_to_dms(dd_val, is_lon=False):
    """Mengonversi derajat desimal menjadi string DMS."""
    if dd_val is None:
        return None
    degrees = int(dd_val)
    minutes_float = (abs(dd_val) - abs(degrees)) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    
    if is_lon:
        direction = 'E' if dd_val >= 0 else 'W'
    else:
        direction = 'N' if dd_val >= 0 else 'S'
    
    return f"{abs(degrees)}° {minutes}' {seconds:.2f}\" {direction}"

# Fungsi utama untuk konversi
def convert_coordinates(x_coord, y_coord, source_crs, target_crs, source_format):
    """Mengonversi koordinat dari satu CRS dan format ke yang lain."""
    x_dd, y_dd = None, None
    if source_format == 'DD':
        try:
            x_dd = float(x_coord)
            y_dd = float(y_coord)
        except ValueError:
            return None, None
    elif source_format == 'DMS':
        x_dd = dms_to_dd(x_coord)
        y_dd = dms_to_dd(y_coord)
        if x_dd is None or y_dd is None:
            return None, None
    elif source_format == 'UTM':
        try:
            x_dd = float(x_coord)
            y_dd = float(y_coord)
        except ValueError:
            return None, None
    
    try:
        transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)
        x_converted, y_converted = transformer.transform(x_dd, y_dd)
        return x_converted, y_converted
    except pyproj.exceptions.CRSError:
        return None, None
    except Exception:
        return None, None

# Daftar sistem dan format koordinat
coordinate_systems = {
    "Global": {
        "WGS 84": "EPSG:4326",
        "ITRF2014": "EPSG:7912",
    },
    "UTM (Indonesia)": {
        "WGS 84 / UTM Zona 48N (Indonesia Barat)": "EPSG:32648",
        "WGS 84 / UTM Zona 49N (Indonesia Tengah)": "EPSG:32649",
        "WGS 84 / UTM Zona 50N (Indonesia Timur)": "EPSG:32650",
        "WGS 84 / UTM Zona 48S": "EPSG:32748",
    }
}

formats = ["DD", "DMS", "UTM"]

# --- Bagian 3: Antarmuka Streamlit ---
st.set_page_config(page_title="Konverter Koordinat Spasial Lengkap", layout="wide")
st.title("🗺️ Konverter Koordinat Spasial Lengkap")

# Pilihan tabs
tab1, tab2 = st.tabs(["Konversi Manual", "Chatbot Konversi"])

# --- Tab 1: Konversi Manual ---
with tab1:
    st.write("Konversi leluasa antara format koordinat yang berbeda.")

    with st.sidebar:
        st.header("Pengaturan Konversi Manual")
        
        source_format = st.selectbox("Pilih Format Koordinat Sumber:", formats, key="manual_source_format")
        target_format = st.selectbox("Pilih Format Koordinat Target:", formats, key="manual_target_format")
        
        st.markdown("---")
        
        source_category = st.selectbox("Pilih Kategori Sumber:", list(coordinate_systems.keys()), key="manual_source_cat")
        source_cs_name = st.selectbox("Pilih Sistem Koordinat Sumber:", list(coordinate_systems[source_category].keys()), key="manual_source_cs")
        source_crs = coordinate_systems[source_category][source_cs_name]

        target_category = st.selectbox("Pilih Kategori Target:", list(coordinate_systems.keys()), key="manual_target_cat")
        target_cs_name = st.selectbox("Pilih Sistem Koordinat Target:", list(coordinate_systems[target_category].keys()), key="manual_target_cs")
        target_crs = coordinate_systems[target_category][target_cs_name]

    st.subheader("Masukkan Koordinat Manual")
    col1, col2 = st.columns(2)

    x_label = "Koordinat X (Longitude)" if source_format in ['DD', 'DMS'] else "Koordinat X (Easting)"
    y_label = "Koordinat Y (Latitude)" if source_format in ['DD', 'DMS'] else "Koordinat Y (Northing)"

    with col1:
        x_input = st.text_input(f"Masukkan {x_label}:", key="manual_x")
    with col2:
        y_input = st.text_input(f"Masukkan {y_label}:", key="manual_y")

    if st.button("Konversi", key="manual_button"):
        if x_input and y_input:
            x_converted, y_converted = convert_coordinates(x_input, y_input, source_crs, target_crs, source_format)
            
            if x_converted is not None:
                # Mengembalikan output sesuai format target
                if target_format == 'DD':
                    x_out, y_out = x_converted, y_converted
                elif target_format == 'DMS':
                    x_out, y_out = dd_to_dms(x_converted, is_lon=True), dd_to_dms(y_converted)
                elif target_format == 'UTM':
                    x_out, y_out = x_converted, y_converted

                st.success("✅ Konversi Berhasil!")
                st.info(f"Koordinat Asli: **{x_input}, {y_input}** ({source_cs_name})")
                st.info(f"Koordinat Hasil Konversi: **{x_out}, {y_out}** ({target_cs_name})")
            else:
                st.error("Terjadi kesalahan. Mohon periksa format input Anda. Contoh format DMS: 6° 55' 38.87\" S")

# --- Tab 2: Chatbot Konversi ---
with tab2:
    st.header("Chatbot Konversi Koordinat")
    st.write("Silakan ketik permintaan konversi Anda. Contoh: 'konversi -6.9248, 107.6186 ke UTM' atau 'konversi 6° 55' 38.87\" S, 107° 38' 11.23\" E ke UTM 49N'.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Tampilkan riwayat percakapan
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Tangani input pengguna baru
    if prompt := st.chat_input("Apa yang ingin Anda konversi?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Memproses..."):
                # Logika ekstraksi dari prompt
                # Ini adalah simulasi dari respons Gemini API.
                # Dalam implementasi nyata, Anda akan mengirim prompt ke Gemini API
                # dan memproses respons yang diterima.
                match = re.search(r"konversi\s+([-+]?\d+\.?\d*|[-+]?\d+°\s*\d+'\s*\d+\.?\d*\"?\s*[NSEW]?)\s*,\s*([-+]?\d+\.?\d*|[-+]?\d+°\s*\d+'\s*\d+\.?\d*\"?\s*[NSEW]?)\s*(?:dari\s+([\w\s\/]+))?\s*ke\s+([\w\s\/]+)", prompt, re.IGNORECASE)
                
                if match:
                    x_input, y_input, source_cs_name, target_cs_name = match.groups()
                    
                    # Logika penentuan format dan CRS
                    source_format = "DD"
                    if "°" in x_input:
                        source_format = "DMS"
                    
                    # Asumsi default jika tidak ada CRS sumber yang disebutkan
                    source_crs = "EPSG:4326" # WGS 84
                    if source_cs_name and "ITRF" in source_cs_name:
                        source_crs = "EPSG:7912"
                    
                    # Penentuan CRS target
                    target_crs = None
                    if "UTM 48N" in target_cs_name: target_crs = "EPSG:32648"
                    elif "UTM 49N" in target_cs_name: target_crs = "EPSG:32649"
                    elif "UTM 50N" in target_cs_name: target_crs = "EPSG:32650"
                    elif "UTM 48S" in target_cs_name: target_crs = "EPSG:32748"
                    elif "WGS 84" in target_cs_name: target_crs = "EPSG:4326"
                    elif "ITRF" in target_cs_name: target_crs = "EPSG:7912"
                    
                    if target_crs:
                        x_converted, y_converted = convert_coordinates(x_input, y_input, source_crs, target_crs, source_format)

                        if x_converted is not None:
                            # Penentuan format output
                            target_format_out = "DD"
                            if "°" not in str(x_converted) and "UTM" in target_cs_name:
                                target_format_out = "UTM"
                            elif "°" not in str(x_converted) and "WGS" in target_cs_name:
                                target_format_out = "DD"
                            
                            # Mengonversi format output jika perlu
                            if target_format_out == "DMS":
                                x_out, y_out = dd_to_dms(x_converted, is_lon=True), dd_to_dms(y_converted)
                            else:
                                x_out, y_out = x_converted, y_converted

                            response_text = f"Tentu, koordinat hasil konversi Anda adalah: `{x_out}, {y_out}`."
                            st.markdown(response_text)
                            st.session_state.messages.append({"role": "assistant", "content": response_text})

                            # Simpan ke Firestore
                            if firebase_initialized:
                                try:
                                    doc_ref = db.collection('konversi').document()
                                    doc_ref.set({
                                        'user_query': prompt,
                                        'original_coords': f"{x_input}, {y_input}",
                                        'converted_coords': f"{x_out}, {y_out}",
                                        'timestamp': datetime.utcnow(),
                                        'source_crs': coordinate_systems[source_category][source_cs_name] if source_cs_name else source_crs,
                                        'target_crs': target_crs
                                    })
                                    st.toast("✅ Konversi disimpan ke database!")
                                except Exception as e:
                                    st.error(f"Gagal menyimpan ke database: {e}")
                            
                        else:
                            response_text = "Maaf, saya tidak dapat melakukan konversi dengan format tersebut. Bisakah Anda coba lagi?"
                            st.markdown(response_text)
                            st.session_state.messages.append({"role": "assistant", "content": response_text})
                    else:
                        response_text = "Maaf, sistem koordinat target tidak dikenali."
                        st.markdown(response_text)
                        st.session_state.messages.append({"role": "assistant", "content": response_text})

                else:
                    response_text = "Maaf, saya tidak memahami permintaan Anda. Mohon gunakan format seperti 'konversi [koordinat X], [koordinat Y] ke [CRS target]'."
                    st.markdown(response_text)
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
