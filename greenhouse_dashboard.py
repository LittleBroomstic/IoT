import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os

st.set_page_config(page_title="Szklarnia Monitor", layout="wide")
st.title("Monitor Szklarni - Dashboard")

# ================== KONFIGURACJA ==================
DATA_FILES = {
    "Temperatura": "temp.csv",
    "Wilgotność": "humid.csv",
    "Oświetlenie": "light.csv"
}

THRESHOLDS = {
    "Temperatura": (20, 30),
    "Wilgotność": (45, 65),
    "Oświetlenie": (7, 9999)
}

# ================== WCZYTYWANIE DANYCH ==================
def load_data():
    data = {}
    for name, file in DATA_FILES.items():
        if os.path.exists(file):
            try:
                df = pd.read_csv(file, sep=';')
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['payload'] = pd.to_numeric(df['payload'], errors='coerce')
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
                data[name] = df
            except Exception as e:
                st.error(f"Błąd wczytywania {file}: {e}")
                data[name] = pd.DataFrame()
        else:
            st.warning(f"Brak pliku: {file}")
            data[name] = pd.DataFrame()
    return data

data = load_data()

all_nodes = set()

for df in data.values():
    if not df.empty and 'node_id' in df.columns:
        all_nodes.update(df['node_id'].dropna().unique())

all_nodes = sorted(map(int, all_nodes))

# ================== FILTRY ==================
col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    hours = st.slider("Pokaż dane z ostatnich (godzin)", 1, 72, 24)
with col2:
    selected_nodes = st.multiselect(
    "Wybierz node'y",
    options=all_nodes,
    default=all_nodes
    )
with col3:
    if st.button("Odśwież dane"):
        st.rerun()

# ================== ZAKŁADKI ==================
tab1, tab2, tab3, tab4 = st.tabs(["Temperatura", "Wilgotność", "Oświetlenie", "Wszystko naraz"])

for tab, metric in zip([tab1, tab2, tab3], ["Temperatura", "Wilgotność", "Oświetlenie"]):
    with tab:
        df = data.get(metric, pd.DataFrame())
        if df.empty:
            st.warning(f"Brak danych dla {metric}")
            continue

        # Filtr z fallbackiem - jeśli nic nie ma w okresie, pokaż ostatnie dane
        cutoff = datetime.now() - timedelta(hours=hours)
        df_filtered = df[df['timestamp'] >= cutoff]

        if df_filtered.empty:
            st.info(f"Brak danych z ostatnich {hours}h — pokazuję wszystkie dostępne dane")
            df_filtered = df.copy()

        df_filtered = df_filtered[df_filtered['node_id'].isin(selected_nodes)]

        if df_filtered.empty:
            st.info("Brak danych dla wybranych node'ów")
            continue

        fig = px.line(df_filtered, x='timestamp', y='payload', color='node_id',
                      title=f"{metric} w czasie", markers=True, height=500)

        min_val, max_val = THRESHOLDS[metric]
        fig.add_hline(y=max_val, line_dash="dash", line_color="red", annotation_text=f"Max: {max_val}")
        fig.add_hline(y=min_val, line_dash="dash", line_color="orange", annotation_text=f"Min: {min_val}")

        st.plotly_chart(fig, width='stretch')

        st.subheader("Statystyki")
        stats = df_filtered.groupby('node_id')['payload'].agg(['mean', 'min', 'max', 'count']).round(2)
        st.dataframe(stats, width='stretch')

# ================== WIDOK ZŁOŻONY ==================
with tab4:
    st.subheader("Wszystkie parametry")
    for metric in ["Temperatura", "Wilgotność", "Oświetlenie"]:
        df = data.get(metric, pd.DataFrame())
        if not df.empty:
            cutoff = datetime.now() - timedelta(hours=hours)
            df_f = df[df['timestamp'] >= cutoff]
            if df_f.empty:
                df_f = df.copy()
            df_f = df_f[df_f['node_id'].isin(selected_nodes)]
            if not df_f.empty:
                fig = px.line(df_f, x='timestamp', y='payload', color='node_id',
                              title=metric, height=350)
                st.plotly_chart(fig, width='stretch')

# ================== OSTATNIE ODCZYTY ==================
st.subheader("Ostatnie odczyty")
last_rows = []
for name, df in data.items():
    if not df.empty and not df['timestamp'].empty:
        latest = df.loc[df['timestamp'].idxmax()]
        value = latest['payload']
        last_rows.append({
            "Parametr": name,
            "Node": int(latest['node_id']),
            "Wartość": round(float(value), 2) if pd.notna(value) else "nan",
            "Czas": latest['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
        })

if last_rows:
    st.dataframe(pd.DataFrame(last_rows), width='stretch', hide_index=True)

st.caption("Dashboard działa lokalnie")
