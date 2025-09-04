import streamlit as st
import pandas as pd
import pyproj
import re

# Set konfigurasi halaman Streamlit
st.set_page_config(page_title="Konverter Koordinat Spasial Lengkap", layout="wide")

# --- Bagian 1: Definisi Data dan Fungsi Bantuan ---

# Fungsi untuk mengonversi DMS ke Derajat Desimal (DD)
def dms_to_dd(dms_str):
    """Mengonversi string DMS menjadi derajat desimal."""
    try:
        # Menggunakan regex untuk mengekstrak angka
        parts = re.findall(r"[-+]?\d+\.?\d*", dms_str.replace(",", "."))
        d = float(parts[0])
        m = float(parts[1]) if len(parts) > 1 else 0
        s = float(parts[2]) if len(parts) > 2 else 0

        dd = abs(d) + m/60 + s/3600
        
        # Mengecek arah (N/S, E/W)
        if re.search(r"[S|W]", dms_str, re.IGNORECASE):
            dd *= -1
        return dd
    except (IndexError, ValueError):
        return None

# Fungsi untuk mengonversi Derajat Desimal (DD) ke DMS
def dd_to_dms(dd_val, is_lon=False):
    """Mengonversi derajat desimal menjadi string DMS."""
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
def convert_coordinates(x_coord, y_coord, source_crs, target_crs, source_format, target_format):
    # Parsing input berdasarkan format sumber
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

        # Mengembalikan output sesuai format target
        if target_format == 'DD':
            return x_converted, y_converted
        elif target_format == 'DMS':
            return dd_to_dms(x_converted, is_lon=True), dd_to_dms(y_converted)
        elif target_format == 'UTM':
            # Untuk UTM, tidak perlu diubah formatnya, karena sudah numerik
            return x_converted, y_converted
    except pyproj.exceptions.CRSError:
        return None, None
    except Exception as e:
        st.error(f"Error during conversion: {e}")
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

# --- Bagian 2: Antarmuka Streamlit ---
st.title("🗺️ Konverter Koordinat Spasial Lengkap")
st.write("Konversi leluasa antara format koordinat yang berbeda.")

# Pengaturan Konversi di Sidebar
with st.sidebar:
    st.header("Pengaturan Konversi")
    
    # Pilihan Format
    source_format = st.selectbox("Pilih Format Koordinat Sumber:", formats)
    target_format = st.selectbox("Pilih Format Koordinat Target:", formats)
    
    st.markdown("---")
    
    # Pilihan Sistem Koordinat Sumber
    source_category = st.selectbox("Pilih Kategori Sumber:", list(coordinate_systems.keys()))
    source_cs_name = st.selectbox("Pilih Sistem Koordinat Sumber:", list(coordinate_systems[source_category].keys()))
    source_crs = coordinate_systems[source_category][source_cs_name]

    # Pilihan Sistem Koordinat Target
    target_category = st.selectbox("Pilih Kategori Target:", list(coordinate_systems.keys()))
    target_cs_name = st.selectbox("Pilih Sistem Koordinat Target:", list(coordinate_systems[target_category].keys()))
    target_crs = coordinate_systems[target_category][target_cs_name]

# Input dan Konversi
st.subheader("Masukkan Koordinat Manual")
col1, col2 = st.columns(2)

# Mengatur label input berdasarkan format
x_label = "Koordinat X (Longitude)" if source_format in ['DD', 'DMS'] else "Koordinat X (Easting)"
y_label = "Koordinat Y (Latitude)" if source_format in ['DD', 'DMS'] else "Koordinat Y (Northing)"

with col1:
    x_input = st.text_input(f"Masukkan {x_label}:")
with col2:
    y_input = st.text_input(f"Masukkan {y_label}:")

if st.button("Konversi"):
    if x_input and y_input:
        x_converted, y_converted = convert_coordinates(x_input, y_input, source_crs, target_crs, source_format, target_format)
        
        if x_converted is not None:
            st.success("✅ Konversi Berhasil!")
            st.info(f"Koordinat Asli: **{x_input}, {y_input}**")
            st.info(f"Koordinat Hasil Konversi: **{x_converted}, {y_converted}**")
        else:
            st.error("Terjadi kesalahan. Mohon periksa format input Anda. Contoh format DMS: 6° 55' 38.87\" S")