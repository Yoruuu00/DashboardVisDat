import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import geopandas as gpd

st.set_page_config(
    page_title="Dashboard Titik Api Indonesia (MODIS 2019–2024)",
    layout="wide"
)

st.title("🔥 Dashboard Titik Api Indonesia (MODIS 2019–2024)")

intro_md = """
### Selamat datang di Dashboard Analisis Titik Api (Hotspot) di Indonesia 🔥

Dalam kurun waktu **2019 hingga 2024**, Indonesia menunjukkan dinamika kemunculan titik api yang dipengaruhi oleh faktor meteorologi, tutupan lahan, dan aktivitas manusia. Titik api (*hotspot*) adalah indikasi suhu permukaan yang tinggi dan berpotensi menjadi sumber kebakaran lahan jika tidak segera ditangani. Fenomena ini berdampak pada kualitas udara, kesehatan publik, serta kegiatan ekonomi—dan kerap menunjukkan pola musiman yang berulang pada wilayah tertentu. 

Dashboard ini menggabungkan analisis spasial dan temporal untuk membantu pengguna:
 - 🔎 Menganalisis tren hotspot secara tahunan, 
 - 📍 Mengidentifikasi provinsi/area dengan intensitas tertinggi, 
 - 📈 Mengamati pola musiman dan variasi antar tahun, 
 - 🧠 Mendukung pengambilan keputusan berbasis data untuk mitigasi risiko. 
 
**Sumber data:** NASA FIRMS (MODIS).
"""

@st.cache_data
def load_and_clean(path="MODIS_Indonesia_2019_2024_FINAL_CLEANED.csv", geojson_path="gadm41_IDN_1.json"):
    
    try:
        df = pd.read_csv(path)
    except Exception as e:
        raise FileNotFoundError(f"Gagal membuka file CSV '{path}': {e}")

   
    if 'date' in df.columns:
       
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df = df.dropna(subset=['date'])
        
        
        df['month_name'] = df['date'].dt.strftime('%b')
        
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            
    else:
        st.error("Kolom 'date' tidak ditemukan di CSV! Pastikan file CSV sudah benar.")
        st.stop()
        
 
    for col in ['brightness', 'frp', 'confidence', 'latitude', 'longitude', 'year']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    required = []
    if 'latitude' in df.columns and 'longitude' in df.columns:
        required += ['latitude', 'longitude']
    if 'brightness' in df.columns:
        required += ['brightness']
    if required:
        df = df.dropna(subset=required)

    try:
        prov = gpd.read_file(geojson_path)
        prov = prov.to_crs("EPSG:4326")
        if 'longitude' in df.columns and 'latitude' in df.columns:
            gdf_points = gpd.GeoDataFrame(
                df.copy(),
                geometry=gpd.points_from_xy(df['longitude'], df['latitude']),
                crs="EPSG:4326"
            )
            name_col = None
            for candidate in ['NAME_1', 'name_1', 'provinsi', 'province', 'NAME']:
                if candidate in prov.columns:
                    name_col = candidate
                    break
            if name_col is None:
                prov['__name__'] = prov.index.astype(str)
                name_col = '__name__'

            joined = gpd.sjoin(gdf_points, prov[[name_col, 'geometry']], how="left", predicate="within")
            if name_col in joined.columns:
                df['province'] = joined[name_col].fillna('Unknown').values
            else:
                df['province'] = 'Unknown'
        else:
            df['province'] = 'Unknown'
    except Exception as e:
        st.warning(f"GeoJSON load/spatial join gagal atau tidak ditemukan: {e}")
        df['province'] = df.get('province', pd.Series(['Unknown'] * len(df))).values

    unknown_count = (df['province'] == 'Unknown').sum()
    if unknown_count > 0:
        pass 
    df = df[df['province'] != 'Unknown'].copy()

    island_map = {
        'Sumatera': ['aceh','sumatera','riau','jambi','bengkulu','lampung','bangka','sumatera utara','sumatera barat','sumatera selatan','kepulauan riau'],
        'Kalimantan': ['kalimantan'],
        'Jawa': ['jawa','banten','jakarta','yogyakarta'],
        'Sulawesi': ['sulawesi','gorontalo'],
        'Papua': ['papua'],
        'Bali_Nusa': ['bali','nusa tenggara','ntb','ntt', 'timor'], 
        'Maluku': ['maluku']
    }

    def map_island(prov):
        if pd.isna(prov) or prov == 'Unknown': 
            return 'Unknown'
        prov_low = str(prov).lower()
        for key, kws in island_map.items():
            for kw in kws:
                if kw in prov_low:
                    if key == 'Bali_Nusa':
                        if 'bali' in prov_low:
                            return 'Bali'
                        else:
                            return 'Nusa Tenggara' 
                    return key
        return 'Other'

    df['island'] = df['province'].apply(map_island)

    other_count = (df['island'] == 'Other').sum()
    if other_count > 0:
        pass
    df = df[df['island'] != 'Other'].copy()

    if 'frp' in df.columns:
        df['frp'] = df['frp'].fillna(df['frp'].median(skipna=True))
    else:
        df['frp'] = 0.0

    if 'brightness' not in df.columns:
        df['brightness'] = 0.0

    raw_fsi = df['frp'] * df['brightness']
    if raw_fsi.max() != raw_fsi.min():
        df['fsi'] = 100 * (raw_fsi - raw_fsi.min()) / (raw_fsi.max() - raw_fsi.min())
    else:
        df['fsi'] = 0.0

    df.columns = [c.lower() for c in df.columns]

    return df

try:
    df = load_and_clean()
except FileNotFoundError as e:
    st.error(str(e))
    st.stop()


with st.expander("📚 Pendahuluan", expanded=True):
    col1, col2 = st.columns([2.5, 1.2])
    with col1:
        st.markdown(intro_md)
    with col2:
        st.image("titik_api.jpg", caption="Ilustrasi Titik Api di Riau (sumber: ANTARA)", use_column_width=True)
    st.markdown("---")

with st.expander("🧹 Data Mentah & Proses Cleaning", expanded=False):
    st.markdown("""
**Ringkasan proses cleaning yang diterapkan (otomatis):**
1. Konversi tanggal (`date`) ke datetime, ekstraksi `month_name`, dan format ulang ke YYYY-MM-DD.
2. Konversi kolom numerik (brightness, frp, confidence, latitude, longitude, year). 
3. Buang baris tanpa koordinat / brightness (tidak layak dipetakan). 
4. Spatial join ke batas provinsi bila geojson tersedia. 
5. Menambahkan kolom `island` dan `fsi` (Fire Severity Index).
6. **Menghapus baris 'Unknown' (di luar poligon) dan 'Other' (pulau tidak terpetakan).**
    """)
    st.markdown("**100 baris pertama (setelah cleaning):**")
    st.dataframe(df.head(100), use_container_width=True)

with st.expander("📎 Penjelasan Istilah Teknis", expanded=False):
    st.markdown("""
**🔸 Brightness** Indikator panas radiasi permukaan yang terdeteksi satelit. Nilai lebih tinggi → sumber panas kuat(suhu).

**🔸 FRP (Fire Radiative Power)** Daya radiasi panas dari kebakaran — mengindikasikan intensitas pembakaran(nilai rata-rata dari intensitas kebakaran).

**🔸 Confidence** Tingkat keyakinan bahwa titik adalah hotspot (biasanya Low/Nominal/High / atau persen).

**🔸 FSI (Fire Severity Index)** Skor normalisasi `frp * brightness` pada skala 0–100, untuk peringkat relatif(indeks kekeringan).

**🔸 Hotspot** Titik panas yang terdeteksi satelit; perlu dimonitor/ditindaklanjuti.
    """)

st.markdown("---")

st.markdown("""
### 🎯 Rekomendasi (ringkasan)
- Perkuat patroli pada periode puncak & provinsi kontributor utama. 
- Fokus mitigasi (water-bombing, pos pantau) pada pulau/provinsi ber-FSI tinggi. 
- Kampanye larangan pembakaran lahan sebelum musim kering/puncak hotspot.
""")

st.sidebar.header("🔍 Filter Data (mempengaruhi semua grafik)")
if 'year' in df.columns and not df['year'].isna().all():
    tahun_min, tahun_max = int(df['year'].min()), int(df['year'].max())
else:
    tahun_min, tahun_max = 2019, 2024
tahun_range = st.sidebar.slider("Pilih rentang tahun:", tahun_min, tahun_max, (tahun_min, tahun_max))

confidence_min = st.sidebar.slider("Batas minimum Confidence (%)", 0, 100, 80)

pulau_list = sorted(df['island'].dropna().unique())
pulau_selected = st.sidebar.multiselect("Pilih Pulau:", pulau_list, default=pulau_list)

bulan_list = ['All'] + list(df['month_name'].dropna().unique())
bulan_selected = st.sidebar.selectbox("Pilih Bulan:", bulan_list, index=0)

filtered = df.copy()

if 'year' in filtered.columns:
    filtered = filtered[filtered['year'].between(tahun_range[0], tahun_range[1])]

if 'confidence' in filtered.columns:
    filtered = filtered[filtered['confidence'] >= confidence_min]


if 'island' in filtered.columns:
    filtered = filtered[filtered['island'].isin(pulau_selected)]

if 'month_name' in filtered.columns and bulan_selected != 'All':
    filtered = filtered[filtered['month_name'] == bulan_selected]


if filtered.empty:
    st.warning("⚠️ Tidak ada data cocok dengan filter. Coba ubah pilihan filter.")
    st.stop()


col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("🔥 Total Titik Panas", f"{len(filtered):,}")
col2.metric("📅 Tahun Awal", int(filtered['year'].min()) if 'year' in filtered.columns else "N/A")
col3.metric("📅 Tahun Akhir", int(filtered['year'].max()) if 'year' in filtered.columns else "N/A")
col4.metric("☀️ Avg Brightness", f"{filtered['brightness'].mean():.1f}")
col5.metric("📈 Avg FSI", f"{filtered['fsi'].mean():.1f}")


st.markdown("## 📆 Tren Jumlah Titik Panas per Tahun")
if 'year' in filtered.columns:
   
    trend = filtered.groupby("year").size().reset_index(name="Jumlah Titik Panas").sort_values("year")
    trend['YoY_pct'] = trend['Jumlah Titik Panas'].pct_change().fillna(0) * 100

  
    col_tren1, col_tren2 = st.columns(2)

    with col_tren1:
        st.markdown("#### Jumlah Total Titik Panas")
        fig_trend_line = px.line(
            trend, 
            x="year", 
            y="Jumlah Titik Panas", 
            title="Tren Jumlah Hotspot (2019-2024)",
            markers=True, 
            color_discrete_sequence=["#E25822"] # Warna oranye
        )
        fig_trend_line.update_layout(template="plotly_white", yaxis_title="Jumlah Titik Panas")
        st.plotly_chart(fig_trend_line, use_container_width=True)

    with col_tren2:
        st.markdown("#### Pertumbuhan")
        fig_trend_bar = px.bar(
            trend, 
            x="year", 
            y="YoY_pct", 
            title="Laju Pertumbuhan Hotspot (YoY)",
            color_discrete_sequence=['rgba(37,99,235,0.6)'] 
        )
        fig_trend_bar.update_layout(template="plotly_white", yaxis_title="Perubahan (%)")
        st.plotly_chart(fig_trend_bar, use_container_width=True)
   
        
else:
    st.info("Data tidak memiliki kolom `year` untuk menampilkan tren.")

st.markdown("## 🌍 Peta Sebaran (sample)")
if {'latitude', 'longitude'}.issubset(filtered.columns):
    map_sample = filtered.sample(min(len(filtered), 4000), random_state=42)
    fig_map = px.scatter_mapbox(
        map_sample,
        lat="latitude", lon="longitude",
        color="brightness", size="frp" if 'frp' in map_sample.columns else None,
        hover_data=["date", "province", "island", "confidence", "fsi"], # Menggunakan 'date'
        color_continuous_scale="OrRd",
        zoom=3, height=600
    )
    fig_map.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)
else:
    st.info("Kolom latitude/longitude tidak tersedia untuk menampilkan peta.")


st.markdown("## 🥧 Komposisi Titik Panas per Pulau & Provinsi")
colA, colB = st.columns(2)
with colA:
    pie_island = filtered['island'].value_counts().reset_index()
    pie_island.columns = ['island', 'count']
    fig_pie = px.pie(pie_island, names='island', values='count', hole=0.35, title='Distribusi per Pulau')
    st.plotly_chart(fig_pie, use_container_width=True)
with colB:
    top_prov = filtered['province'].value_counts().head(8).reset_index()
    top_prov.columns = ['province', 'count']
    fig_donut = px.pie(top_prov, names='province', values='count', hole=0.5, title='Top 8 Provinsi')
    st.plotly_chart(fig_donut, use_container_width=True)


st.subheader("Brightness Distribution")
fig_hist = px.histogram(filtered, x='brightness', nbins=30, title='Distribusi Brightness (Count)', marginal=None)
fig_hist.update_layout(template="plotly_white", xaxis_title="Brightness", yaxis_title="Count")
st.plotly_chart(fig_hist, use_container_width=True)


st.markdown("## ⚡ Rata-rata FRP, Brightness, FSI per Tahun")
if 'year' in filtered.columns:
    mean_stats = filtered.groupby("year")[["frp", "brightness", "fsi"]].mean().reset_index()
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(x=mean_stats["year"], y=mean_stats["frp"], name="Avg FRP"))
    fig_bar.add_trace(go.Bar(x=mean_stats["year"], y=mean_stats["brightness"], name="Avg Brightness"))
    fig_bar.add_trace(go.Bar(x=mean_stats["year"], y=mean_stats["fsi"], name="Avg FSI"))
    fig_bar.update_layout(barmode="group", template="plotly_white", title="Rata-rata per Tahun")
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("Tidak ada data `year` untuk menghitung rata-rata per tahun.")


# ==========================
# GRAFIK: HUBUNGAN ANTAR VARIABEL (SCATTER PLOTS - PENGGANTI HEATMAP)
# ==========================
st.markdown("## 🔎 Hubungan Antar Variabel")
col_scatter1, col_scatter2 = st.columns(2) 

with col_scatter1:
    st.markdown("#### Brightness vs. FRP")
   
    if {'brightness', 'frp'}.issubset(filtered.columns):
        scatter_sample = filtered.sample(min(len(filtered), 2000), random_state=42) 
        
        fig_scatter_bf = px.scatter(
            scatter_sample, 
            x="brightness", 
            y="frp", 
            title="Brightness vs FRP",
            opacity=0.5, 
            hover_data=['date', 'province'] 
        )
        fig_scatter_bf.update_layout(template="plotly_white")
        st.plotly_chart(fig_scatter_bf, use_container_width=True)
    else:
        st.info("Kolom brightness/frp tidak tersedia.")

with col_scatter2:
    st.markdown("#### Brightness vs. FSI")
     
    if {'brightness', 'fsi'}.issubset(filtered.columns):
         
        scatter_sample_fsi = filtered.sample(min(len(filtered), 2000), random_state=43) 

        fig_scatter_bs = px.scatter(
            scatter_sample_fsi, 
            x="brightness", 
            y="fsi", 
            title="Brightness vs FSI",
            opacity=0.5,
            hover_data=['date', 'province'] 
        )
        fig_scatter_bs.update_layout(template="plotly_white")
        st.plotly_chart(fig_scatter_bs, use_container_width=True)
    else:
        st.info("Kolom brightness/fsi tidak tersedia.")


st.markdown("## 🚨 Top 10 Titik (FSI tertinggi)")
if 'fsi' in filtered.columns:
    top_fsi = filtered.sort_values('fsi', ascending=False).head(10)
    st.table(top_fsi[['date','province','island','latitude','longitude','brightness','frp','confidence','fsi']].reset_index(drop=True)) # Menggunakan 'date'
else:
    st.info("Kolom FSI tidak tersedia.")

st.markdown("## 🧠 Insight & Rekomendasi")
if 'year' in filtered.columns and not filtered.empty:
    trend_sorted = filtered.groupby("year").size().reset_index(name="Jumlah Titik Panas").sort_values('Jumlah Titik Panas', ascending=False)
    year_max = int(trend_sorted.iloc[0]['year']) if not trend_sorted.empty else "-"
    total_terbanyak = int(trend_sorted.iloc[0]['Jumlah Titik Panas']) if not trend_sorted.empty else 0
else:
    year_max = "-"
    total_terbanyak = 0

mean_conf = filtered['confidence'].mean() if 'confidence' in filtered.columns else 0.0
st.success(f"📌 Tahun {year_max} memiliki jumlah titik panas tertinggi: **{total_terbanyak:,}** (filter saat ini). Rata-rata confidence = {mean_conf:.1f}%.")

fsi_by_island = filtered.groupby('island')['fsi'].mean().sort_values(ascending=False) if 'fsi' in filtered.columns else pd.Series()
top_island = fsi_by_island.index[0] if not fsi_by_island.empty else "N/A"
st.success(f"📌 Pulau dengan rata-rata FSI tertinggi: **{top_island}**")

peak_month = filtered['month_name'].value_counts().index[0] if ('month_name' in filtered.columns and not filtered['month_name'].empty) else "N/A"
st.success(f"📌 Bulan puncak hotspot (filter saat ini): **{peak_month}**")

st.info("- Tingkatkan patroli & deteksi dini pada tahun/bulan puncak.ke model prediktif yang fokus pada area dan waktu berisiko tinggi.\n- Mengembangkan standar operasional prosedur (SOP) respon yang memprioritaskan penanganan berdasarkan tingkat keparahan titik api (FSI), bukan hanya berdasarkan jumlah laporan (frekuensi). \n- Fokuskan mitigasi (water-bombing, pos pantau) di provinsi/pulau prioritas.")

st.caption("📡 Data: NASA FIRMS (MODIS) | Visualisasi: Streamlit + Plotly")