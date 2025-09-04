import streamlit as st
import pandas as pd
import pyproj
import io
import google.generativeai as genai

# Konfigurasi halaman Streamlit
st.set_page_config(page_title="Konverter Koordinat Spasial", layout="wide")

# --- Bagian 1: Definisi Data dan Fungsi Utama ---
# Struktur data yang lebih efisien untuk sistem koordinat
coordinate_systems = {
    "Global": {
        "WGS 84": "EPSG:4326",
        "ITRF2014": "EPSG:7912",
        "PZ-90.11": "EPSG:7520"
    },
    "UTM (Indonesia)": {
        "WGS 84 / UTM Zona 48N (Indonesia Barat)": "EPSG:32648",
        "WGS 84 / UTM Zona 49N (Indonesia Tengah)": "EPSG:32649",
        "WGS 84 / UTM Zona 50N (Indonesia Timur)": "EPSG:32650",
        "ITRF2014 / UTM Zona 48N (Indonesia Barat)": "EPSG:8052",
        "ITRF2014 / UTM Zona 49N (Indonesia Tengah)": "EPSG:8053",
        "ITRF2014 / UTM Zona 50N (Indonesia Timur)": "EPSG:8054",
        "WGS 84 / UTM Zona 48S": "EPSG:32748",
    }
}

# Fungsi untuk konversi koordinat
def convert_coordinates(x_coord, y_coord, source_crs, target_crs):
    try:
        transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)
        return transformer.transform(x_coord, y_coord)
    except pyproj.exceptions.CRSError as e:
        st.error(f"Terjadi kesalahan pada sistem koordinat: {e}")
        return None, None

# Fungsi untuk memproses permintaan konversi dari teks
def process_gemini_request(prompt, coordinate_systems):
    # Logika sederhana untuk mengekstrak informasi dari prompt
    # Ini adalah bagian paling menantang yang membutuhkan prompt engineering
    # Untuk contoh ini, kita asumsikan formatnya 'x,y dari SOURCE ke TARGET'
    try:
        parts = prompt.lower().replace(",", " ").split(" ")
        x_str = parts[0]
        y_str = parts[1]
        source_name_parts = parts[parts.index("dari") + 1 : parts.index("ke")]
        target_name_parts = parts[parts.index("ke") + 1 :]
        
        source_name = " ".join(source_name_parts).strip()
        target_name = " ".join(target_name_parts).strip()

        # Mencocokkan nama dengan kamus yang ada
        source_crs = None
        for category in coordinate_systems.values():
            for name, crs_code in category.items():
                if source_name in name.lower():
                    source_crs = crs_code
                    break
            if source_crs: break

        target_crs = None
        for category in coordinate_systems.values():
            for name, crs_code in category.items():
                if target_name in name.lower():
                    target_crs = crs_code
                    break
            if target_crs: break

        if not source_crs or not target_crs:
            return "Maaf, saya tidak dapat menemukan sistem koordinat yang Anda maksud."

        x_val = float(x_str)
        y_val = float(y_str)
        
        x_conv, y_conv = convert_coordinates(x_val, y_val, source_crs, target_crs)
        if x_conv is not None:
            return f"Koordinat hasil konversi adalah: X = **{x_conv:.6f}**, Y = **{y_conv:.6f}**"
        else:
            return "Terjadi kesalahan saat konversi. Mohon periksa kembali input Anda."
    except (ValueError, IndexError):
        return "Format permintaan Anda salah. Mohon gunakan format: `x, y dari [sistem_sumber] ke [sistem_target]`"

# --- Bagian 2: Antarmuka Streamlit (Tab) ---
st.title("🗺️ Konverter Koordinat Spasial")
st.write("Aplikasi ini membantu Anda mengkonversi koordinat spasial dari satu sistem ke sistem lainnya.")

tab1, tab2 = st.tabs(["Konverter Manual & CSV", "Chatbot Konversi"])

with tab1:
    st.header("Konverter Koordinat")
    
    # Sidebar untuk pilihan sistem koordinat
    with st.sidebar:
        st.header("Pengaturan Konversi")
        
        source_category = st.selectbox(
            "Pilih Kategori Sumber:",
            list(coordinate_systems.keys())
        )
        source_cs_name = st.selectbox(
            "Pilih Sistem Koordinat Sumber:",
            list(coordinate_systems[source_category].keys())
        )
        source_crs = coordinate_systems[source_category][source_cs_name]
        
        st.markdown("---")
        
        target_category = st.selectbox(
            "Pilih Kategori Target:",
            list(coordinate_systems.keys())
        )
        target_cs_name = st.selectbox(
            "Pilih Sistem Koordinat Target:",
            list(coordinate_systems[target_category].keys())
        )
        target_crs = coordinate_systems[target_category][target_cs_name]

    # Tab untuk metode input
    input_tab1, input_tab2 = st.tabs(["Input Manual", "Unggah CSV"])

    with input_tab1:
        col1, col2 = st.columns(2)
        with col1:
            x_input = st.text_input("Masukkan koordinat X:")
        with col2:
            y_input = st.text_input("Masukkan koordinat Y:")
        
        if st.button("Konversi"):
            if x_input and y_input:
                try:
                    x_val = float(x_input)
                    y_val = float(y_input)
                    x_converted, y_converted = convert_coordinates(x_val, y_val, source_crs, target_crs)
                    if x_converted is not None:
                        st.success("✅ Konversi Berhasil!")
                        st.info(f"Koordinat Asli: X = **{x_val}**, Y = **{y_val}**")
                        st.info(f"Koordinat Hasil: X = **{x_converted:.6f}**, Y = **{y_converted:.6f}**")
                except ValueError:
                    st.error("Input harus berupa angka.")

    with input_tab2:
        uploaded_file = st.file_uploader("Pilih file CSV", type="csv")
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                if 'x' in df.columns and 'y' in df.columns:
                    st.success("File CSV berhasil diunggah.")
                    st.write("Data Asli:")
                    st.dataframe(df)
                    df_converted = df.copy()
                    df_converted['x_converted'], df_converted['y_converted'] = zip(*df_converted.apply(
                        lambda row: convert_coordinates(row['x'], row['y'], source_crs, target_crs),
                        axis=1
                    ))
                    st.write("Data Hasil Konversi:")
                    st.dataframe(df_converted)
                    csv_output = df_converted.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Unduh Hasil Konversi (CSV)",
                        data=csv_output,
                        file_name='converted_coordinates.csv',
                        mime='text/csv',
                    )
                else:
                    st.error("File CSV harus memiliki kolom **'x'** dan **'y'**.")
            except Exception as e:
                st.error(f"Terjadi kesalahan saat membaca file: {e}")

with tab2:
    st.header("🤖 Chatbot Konversi (Gemini API)")
    st.write("Silakan berikan instruksi konversi Anda. Contoh: `Konversi 107.619044, -6.917464 dari wgs 84 ke utm zona 48n.`")

    # Ambil API key dari Streamlit secrets
    try:
        genai_api_key = st.secrets["gemini_api_key"]
        genai.configure(api_key=genai_api_key)
    except KeyError:
        st.error("API Key Gemini tidak ditemukan. Harap tambahkan `gemini_api_key` di Streamlit secrets.")
        st.stop()

    model = genai.GenerativeModel('gemini-2.5-flash')
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Tulis permintaan Anda..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Memproses permintaan..."):
                # Coba proses permintaan dengan fungsi lokal terlebih dahulu
                response_text = process_gemini_request(prompt, coordinate_systems)
                
                # Jika tidak berhasil diproses, kirim ke Gemini API
                if "Maaf, saya tidak dapat menemukan" in response_text or "Format permintaan Anda salah" in response_text:
                    gemini_response = model.generate_content(f"Tolong bantu konversi koordinat spasial. Formatnya: 'x, y dari [sistem_sumber] ke [sistem_target]'. Berikut permintaan pengguna: {prompt}")
                    response_text = gemini_response.text
                
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})