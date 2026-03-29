import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO FUTURISTA
st.set_page_config(page_title="GM - SISTEMA PRO", layout="wide", page_icon="🚀")

# Inyección de CSS para diseño estético
st.markdown("""
    <style>
    /* Fondo general */
    .stApp {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        color: #e0e0e0;
    }
    
    /* Títulos con brillo */
    h1, h2, h3 {
        color: #00f2fe !important;
        text-shadow: 0px 0px 10px rgba(0, 242, 254, 0.5);
        font-family: 'Segoe UI', sans-serif;
    }

    /* Tarjetas de productos (Glassmorphism) */
    div[data-testid="stVerticalBlock"] > div {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px;
        padding: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
    }

    /* Botones Estilo Neón */
    .stButton > button {
        background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
        color: #1a1a1a;
        border: none;
        border-radius: 20px;
        font-weight: bold;
        transition: 0.3s;
        box-shadow: 0px 4px 15px rgba(0, 242, 254, 0.3);
    }
    
    .stButton > button:hover {
        transform: scale(1.05);
        box-shadow: 0px 0px 20px rgba(0, 242, 254, 0.6);
        color: white;
    }

    /* Sidebar futurista */
    [data-testid="stSidebar"] {
        background-color: rgba(10, 10, 20, 0.9) !important;
        border-right: 1px solid #4facfe;
    }

    /* Inputs y selectboxes */
    .stTextInput > div > div > input, .stSelectbox > div > div {
        background-color: rgba(255, 255, 255, 0.05) !important;
        color: white !important;
        border: 1px solid #4facfe !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- ESTADO DE SESIÓN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.tienda_asignada = None

# --- LOGIN ESTÉTICO ---
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align: center;'>⚡ GUIZADO & MODA <br><span style='font-size: 20px; color: white;'>SISTEMA DE CONTROL PRO</span></h1>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            u = st.text_input("👤 Usuario").lower().strip()
            p = st.text_input("🔑 Contraseña", type="password").strip()
            if st.form_submit_button("INGRESAR AL SISTEMA"):
                if u == "lachi" and p == "admin2026":
                    st.session_state.logged_in, st.session_state.role = True, "admin"
                elif u == "moda" and p == "moda2026":
                    st.session_state.logged_in, st.session_state.role, st.session_state.tienda_asignada = True, "user", "MODA"
                elif u == "guizado" and p == "guizado2026":
                    st.session_state.logged_in, st.session_state.role, st.session_state.tienda_asignada = True, "user", "GUIZADO"
                else:
                    st.error("Acceso denegado")
                if st.session_state.logged_in: st.rerun()
    st.stop()

# --- 2. CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        data = conn.read(spreadsheet=url, ttl=0)
        data.columns = [str(c).strip().lower() for c in data.columns]
        if 'local' in data.columns:
            data['local'] = data['local'].astype(str).str.strip().str.upper()
        return data
    except: return pd.DataFrame()

def registrar_log(tipo, local, prenda, talla, color, cant):
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        try: logs = conn.read(spreadsheet=url, worksheet="historial", ttl=0)
        except: logs = pd.DataFrame(columns=["fecha", "hora", "tipo", "local", "prenda", "talla", "color", "cantidad"])
        ahora = datetime.now()
        nueva = pd.DataFrame([{"fecha": ahora.strftime("%d/%m/%Y"), "hora": ahora.strftime("%H:%M:%S"), "tipo": tipo, "local": local, "prenda": prenda, "talla": talla, "color": color, "cantidad": cant}])
        conn.update(spreadsheet=url, worksheet="historial", data=pd.concat([logs, nueva], ignore_index=True))
    except: pass

df = cargar_datos()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"### ✨ BIENVENIDO\n**{st.session_state.role.upper()}**")
    opciones = ["🚨 Alertas Stock", "📦 Stock Global", "🚚 Traslados", "🏭 Taller", "📜 Historial"] if st.session_state.role == "admin" else ["📦 Mi Stock", "🚚 Traslados"]
    modo = st.radio("MENÚ DE NAVEGACIÓN", opciones)
    st.write("---")
    if st.button("🔄 ACTUALIZAR"):
        st.cache_data.clear(); st.rerun()
    if st.button("🚪 SALIR"):
        st.session_state.logged_in = False; st.rerun()

# --- 4. MÓDULOS ---

if modo == "🚨 Alertas Stock":
    st.header("🚀 Reposición Urgente")
    limite = st.slider("Filtro de Stock Crítico", 0, 20, 5)
    df_a = df[(df['local'] != "TALLER") & (df['stock'] <= limite)]
    st.dataframe(df_a[['local', 'prenda', 'talla', 'color', 'stock']].sort_values(by='stock'), use_container_width=True)

elif "Stock" in modo:
    st.header("📦 Inventario Pro")
    l_sel = st.session_state.tienda_asignada if st.session_state.role == "user" else st.selectbox("📍 Seleccione Sede", sorted(df['local'].unique()))
    df_l = df[df['local'] == l_sel]
    
    if not df_l.empty:
        p_sel = st.selectbox("👕 Prenda", sorted(df_l['prenda'].unique()))
        items = df_l[df_l['prenda'] == p_sel].sort_values(by=['talla', 'color'])
        for idx, row in items.iterrows():
            with st.container():
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.markdown(f"#### {row['color'].upper()}\n**Talla:** {row['talla']}")
                c2.metric("EXISTENCIAS", int(row['stock']), delta_color="normal")
                adj = c3.number_input("Venta", value=0, key=f"adj_{idx}")
                if c3.button("REGISTRAR", key=f"b_{idx}"):
                    df.at[idx, 'stock'] += adj
                    conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                    registrar_log("Venta", l_sel, p_sel, row['talla'], row['color'], adj)
                    st.cache_data.clear(); st.rerun()

elif modo == "🚚 Traslados":
    st.header("🚚 Traslado Masivo de Mercadería")
    locales = sorted(df['local'].unique())
    col1, col2 = st.columns(2)
    orig = col1.selectbox("ORIGEN", locales)
    dest = col2.selectbox("DESTINO", [l for l in locales if l != orig])
    
    df_o = df[df['local'] == orig].copy()
    if not df_o.empty:
        df_o['Seleccionar'] = False
        edited_df = st.data_editor(
            df_o[['Seleccionar', 'prenda', 'talla', 'color', 'stock']],
            column_config={"Seleccionar": st.column_config.CheckboxColumn(default=False)},
            disabled=["prenda", "talla", "color", "stock"],
            hide_index=True, use_container_width=True
        )
        seleccionados = edited_df[edited_df['Seleccionar'] == True]
        if not seleccionados.empty:
            items_a_mover = []
            for _, sel in seleccionados.iterrows():
                cc1, cc2 = st.columns([3, 1])
                cc1.write(f"📦 {sel['prenda']} - {sel['color']} (T{sel['talla']})")
                cant_env = cc2.number_input(f"Cant", min_value=1, max_value=int(sel['stock']), value=1, key=f"mov_{sel.name}")
                items_a_mover.append({"prenda": sel['prenda'], "talla": sel['talla'], "color": sel['color'], "cantidad": cant_env})
            
            if st.button("🚀 INICIAR TRASLADO"):
                for item in items_a_mover:
                    idx_o = df[(df['local']==orig) & (df['prenda']==item['prenda']) & (df['talla']==item['talla']) & (df['color']==item['color'])].index[0]
                    df.at[idx_o, 'stock'] -= item['cantidad']
                    idx_d = df[(df['local']==dest) & (df['prenda']==item['prenda']) & (df['talla']==item['talla']) & (df['color']==item['color'])].index
                    if not idx_d.empty:
                        df.at[idx_d[0], 'stock'] += item['cantidad']
                    else:
                        df = pd.concat([df, pd.DataFrame([{'local':dest, 'prenda':item['prenda'], 'talla':item['talla'], 'color':item['color'], 'stock':item['cantidad']}])], ignore_index=True)
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                st.success("Traslado Completado"); st.cache_data.clear(); st.rerun()

elif modo == "🏭 Taller":
    st.header("🏭 Centro de Producción")
    t1, t2 = st.tabs(["📥 REPONER STOCK", "➕ NUEVA COLECCIÓN"])
    with t1:
        dt = df[df['local'] == "TALLER"]
        if not dt.empty:
            p = st.selectbox("Modelo", sorted(dt['prenda'].unique()))
            t = st.selectbox("Talla", sorted(dt[dt['prenda']==p]['talla'].unique()))
            c = st.selectbox("Color", sorted(dt[(dt['prenda']==p) & (dt['talla']==t)]['color'].unique()))
            can = st.number_input("Cantidad", min_value=1, value=1)
            if st.button("SUMAR AL TALLER"):
                idx = df[(df['local']=="TALLER") & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].index[0]
                df.at[idx, 'stock'] += can
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                st.cache_data.clear(); st.rerun()
    with t2:
        with st.form("f_masivo"):
            np = st.text_input("Nombre de la Prenda").upper()
            nt = st.selectbox("Talla General", ["ST", "S", "M", "L", "XL"])
            st.write("🎨 **Distribución de Colores**")
            nuevos = []
            for i in range(8):
                c1, c2 = st.columns([3, 2])
                col = c1.text_input(f"Color {i+1}", key=f"nc_{i}").upper()
                qty = c2.number_input(f"Cantidad", min_value=0, value=0, key=f"nq_{i}")
                if col and qty > 0: nuevos.append({'local':'TALLER', 'prenda':np, 'talla':nt, 'color':col, 'stock':qty})
            if st.form_submit_button("🚀 CREAR COLECCIÓN"):
                if np and nuevos:
                    df = pd.concat([df, pd.DataFrame(nuevos)], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                    st.success("Colección creada correctamente"); st.cache_data.clear(); st.rerun()

elif modo == "📜 Historial":
    st.header("📜 Auditoría de Movimientos")
    try:
        h = conn.read(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], worksheet="historial", ttl=0)
        st.dataframe(h.iloc[::-1], use_container_width=True)
    except: st.warning("No se encontró el registro histórico.")
