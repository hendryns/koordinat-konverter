import streamlit as st
import pandas as pd
import pyproj
import re
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import os
import google.generativeai as genai

# --- Bagian 1: Inisialisasi Firebase dan Gemini API ---
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

def initialize_gemini():
    """Menginisialisasi Gemini API."""
    try:
        if "gemini_api_key" in st.secrets:
            genai.configure(api_key=st.secrets["gemini_api_key"])
            return True
        else:
            st.error("Gemini API key not found. Please add 'gemini_api_key' to Streamlit secrets.")
            return False
    except Exception as e:
        st.error(f"Error initializing Gemini API: {e}")
        return False

gemini_initialized = initialize_gemini()
chat_model = genai.GenerativeModel('gemini-1.5-flash')

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
                if not gemini_initialized:
                    st.warning("Gemini API tidak dapat diinisialisasi. Fitur chatbot tidak aktif.")
                else:
                    try:
                        # Minta Gemini untuk mengekstrak informasi yang dibutuhkan
                        response = chat_model.generate_content(
                            f"Identifikasi dan ekstrak koordinat, format asal (DD, DMS, atau UTM), dan format target (DD, DMS, atau UTM) dari teks berikut. Balas dalam format JSON. Jika CRS target adalah UTM, sertakan zona (misalnya, 'UTM Zona 49N'). Jika tidak dapat diekstrak, beri tahu saya. Teks: '{prompt}'"
                        )
                        data = json.loads(response.text.replace('```json\n', '').replace('\n```', ''))

                        x_input = data.get('x_coord')
                        y_input = data.get('y_coord')
                        source_format = data.get('source_format')
                        target_format = data.get('target_format')
                        target_cs_name = data.get('target_cs_name')

                        if x_input and y_input and source_format and target_format:
                            # Tentukan CRS dari nama yang diekstrak oleh Gemini
                            source_crs = "EPSG:4326"
                            target_crs = "EPSG:4326"
                            if "UTM" in target_cs_name:
                                if "48N" in target_cs_name: target_crs = "EPSG:32648"
                                elif "49N" in target_cs_name: target_crs = "EPSG:32649"
                                elif "50N" in target_cs_name: target_crs = "EPSG:32650"
                                elif "48S" in target_cs_name: target_crs = "EPSG:32748"
                            
                            x_converted, y_converted = convert_coordinates(x_input, y_input, source_crs, target_crs, source_format)

                            if x_converted is not None:
                                x_out, y_out = x_converted, y_converted
                                if target_format == 'DMS':
                                    x_out, y_out = dd_to_dms(x_converted, is_lon=True), dd_to_dms(y_converted)

                                response_text = f"Tentu, koordinat hasil konversi Anda adalah: `{x_out}, {y_out}`."
                                st.markdown(response_text)
                                st.session_state.messages.append({"role": "assistant", "content": response_text})

                                # Simpan ke Firestore
                                if firebase_initialized:
                                    try:
                                        doc_ref = db.collection('konversi_chatbot').document()
                                        doc_ref.set({
                                            'user_query': prompt,
                                            'original_coords': f"{x_input}, {y_input}",
                                            'converted_coords': f"{x_out}, {y_out}",
                                            'timestamp': datetime.utcnow(),
                                            'source_crs': source_crs,
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
                            response_text = "Maaf, saya tidak memahami permintaan Anda. Mohon gunakan format seperti 'konversi [koordinat X], [koordinat Y] ke [CRS target]'."
                            st.markdown(response_text)
                            st.session_state.messages.append({"role": "assistant", "content": response_text})
                    except Exception as e:
                        response_text = f"Terjadi kesalahan saat memproses permintaan: {e}. Mohon coba lagi."
                        st.markdown(response_text)
                        st.session_state.messages.append({"role": "assistant", "content": response_text})
