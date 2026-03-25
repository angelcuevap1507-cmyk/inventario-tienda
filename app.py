import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import plotly.express as px

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Guizado & Moda - Sistema Pro", layout="wide")

# --- ESTADO DE SESIÓN ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.tienda_asignada = None

# --- LOGIN ---
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso Guizado & Moda</h2>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            u = st.text_input("Usuario").lower().strip()
            p = st.text_input("Contraseña", type="password").strip()
            if st.form_submit_button("Entrar"):
                if u == "lachi" and p == "admin2026":
                    st.session_state.logged_in = True
                    st.session_state.role = "admin"
                elif u == "moda" and p == "moda2026":
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.tienda_asignada = "MODA"
                elif u == "guizado" and p == "guizado2026":
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.session_state.tienda_asignada = "GUIZADO"
                else:
                    st.error("Credenciales incorrectas")
                
                if st.session_state.logged_in:
                    st.rerun()
    st.stop()

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        data = conn.read(spreadsheet=url, ttl=0)
        if data is None or data.empty:
            return pd.DataFrame()
        data.columns = data.columns.str.strip().str.lower()
        return data
    except:
        return pd.DataFrame()

def registrar_log(tipo, local, prenda, talla, color, cant):
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        try:
            logs = conn.read(spreadsheet=url, worksheet="historial", ttl=0)
        except:
            logs = pd.DataFrame(columns=["fecha", "hora", "tipo", "local", "prenda", "talla", "color", "cantidad"])
        ahora = datetime.now()
        nueva_fila = pd.DataFrame([{
            "fecha": ahora.strftime("%d/%m/%Y"), "hora": ahora.strftime("%H:%M:%S"),
            "tipo": tipo, "local": local, "prenda": prenda, 
            "talla": talla, "color": color, "cantidad": cant
        }])
        conn.update(spreadsheet=url, worksheet="historial", data=pd.concat([logs, nueva_fila], ignore_index=True))
    except:
        pass

df = cargar_datos()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.title(f"👤 {st.session_state.role.upper()}")
    if st.session_state.role == "admin":
        opciones = ["🚨 Alertas Stock", "📦 Stock Global", "🚚 Traslados", "🏭 Taller", "📜 Historial"]
    else:
        opciones = ["📦 Mi Stock", "🚚 Traslados"]
    modo = st.radio("Menú:", opciones)
    if st.button("🔄 Refrescar"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🚪 Salir"):
        st.session_state.logged_in = False
        st.rerun()

# --- 4. MÓDULOS ---

# MODULO: ALERTAS
if modo == "🚨 Alertas Stock":
    st.header("🚨 Reposición Urgente")
    limite = st.slider("Ver productos con stock igual o menor a:", 0, 15, 5)
    df_alertas = df[(df['local'].str.upper() != "TALLER") & (df['stock'] <= limite)]
    if not df_alertas.empty:
        st.error(f"Se encontraron {len(df_alertas)} variantes bajas.")
        st.dataframe(df_alertas[['local', 'prenda', 'talla', 'color', 'stock']].sort_values(by='stock'), width='stretch')
    else:
        st.success("✅ Stock en tiendas está en niveles óptimos.")

# MODULO: STOCK
elif "Stock" in modo:
    st.header("📦 Inventario Actual")
    l_sel = st.session_state.tienda_asignada if st.session_state.role == "user" else st.selectbox("📍 Local:", sorted(df['local'].unique()))
    df_l = df[df['local'].str.upper() == l_sel.upper()]
    if not df_l.empty:
        p_sel = st.selectbox("👕 Prenda:", sorted(df_l['prenda'].unique()))
        df_p = df_l[df_l['prenda'] == p_sel]
        t_sel = st.radio("📏 Talla:", sorted(df_p['talla'].unique()), horizontal=True)
        items = df_p[df_p['talla'] == t_sel].sort_values(by='color')
        for idx, row in items.iterrows():
            st.divider()
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            c1.write(f"**{row['color'].upper()}**")
            c2.metric("Stock", int(row['stock']))
            adj = c3.number_input("Venta", value=0, key=f"adj_{idx}")
            if c3.button("Guardar", key=f"b_{idx}"):
                df.at[idx, 'stock'] += adj
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("Venta", l_sel, p_sel, t_sel, row['color'], adj)
                st.cache_data.clear()
                st.rerun()
            if st.session_state.role == "admin":
                fix = c4.number_input("Fix", value=int(row['stock']), key=f"f_{idx}")
                if c4.button("Fix", key=f"bf_{idx}"):
                    df.at[idx, 'stock'] = fix
                    conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                    st.cache_data.clear()
                    st.rerun()

# MODULO: TRASLADOS
elif modo == "🚚 Traslados":
    st.header("🚚 Envío de Mercadería")
    orig = st.session_state.tienda_asignada if st.session_state.role == "user" else st.selectbox("Desde:", sorted(df['local'].unique()))
    dest = st.selectbox("Hacia:", [l for l in sorted(df['local'].unique()) if l != orig])
    df_o = df[(df['local'].str.upper() == orig.upper()) & (df['stock'] > 0)]
    if not df_o.empty:
        p = st.selectbox("Prenda:", sorted(df_o['prenda'].unique()))
        t = st.selectbox("Talla:", sorted(df_o[df_o['prenda']==p]['talla'].unique()))
        c = st.selectbox("Color:", sorted(df_o[(df_o['prenda']==p) & (df_o['talla']==t)]['color'].unique()))
        f_o = df[(df['local'].str.upper()==orig.upper()) & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].iloc[0]
        cant = st.number_input("Cantidad:", min_value=1, max_value=int(f_o['stock']), value=1)
        if st.button("Confirmar Traslado"):
            df.at[f_o.name, 'stock'] -= cant
            idx_d = df[(df['local'].str.upper()==dest.upper()) & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].index
            if not idx_d.empty:
                df.at[idx_d[0], 'stock'] += cant
            else:
                df = pd.concat([df, pd.DataFrame([{'local':dest.upper(), 'prenda':p, 'talla':t, 'color':c, 'stock':cant}])], ignore_index=True)
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            registrar_log("Traslado", f"{orig}->{dest}", p, t, c, cant)
            st.cache_data.clear()
            st.rerun()

# MODULO: TALLER (CARGA MASIVA)
elif modo == "🏭 Taller":
    st.header("🏭 Producción y Colecciones")
    t1, t2 = st.tabs(["📥 Reponer Existentes", "➕ Nuevo Modelo (Carga Masiva)"])
    
    with t1:
        dt = df[df['local'].str.upper() == "TALLER"]
        if not dt.empty:
            p = st.selectbox("Modelo:", sorted(dt['prenda'].unique()))
            t = st.selectbox("Talla:", sorted(dt[dt['prenda']==p]['talla'].unique()), key="t1")
            c = st.selectbox("Color:", sorted(dt[(dt['prenda']==p) & (dt['talla']==t)]['color'].unique()), key="c1")
            can = st.number_input("Cant:", min_value=1, value=1)
            if st.button("Sumar"):
                idx = df[(df['local'].str.upper()=="TALLER") & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].index[0]
                df.at[idx, 'stock'] += can
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("Producción", "Taller", p, t, c, can)
                st.cache_data.clear()
                st.rerun()

    with t2:
        st.subheader("📝 Registro Rápido de Colores")
        with st.form("form_masivo"):
            col_p, col_t = st.columns(2)
            n_prenda = col_p.text_input("Nombre de Prenda").upper()
            n_talla = col_t.selectbox("Talla", ["ST", "S", "M", "L", "XL"])
            
            st.write("🎨 **Colores y Cantidades**")
            data_nuevos = []
            for i in range(10): # 10 filas para llenar rápido
                c1, c2 = st.columns([3, 2])
                col_name = c1.text_input(f"Color {i+1}", key=f"c_{i}", label_visibility="collapsed").upper()
                col_qty = c2.number_input(f"Cant {i+1}", min_value=0, value=0, key=f"q_{i}", label_visibility="collapsed")
                if col_name and col_qty > 0:
                    data_nuevos.append({'local': 'TALLER', 'prenda': n_prenda, 'talla': n_talla, 'color': col_name, 'stock': col_qty})
            
            if st.form_submit_button("🚀 Crear todas las prendas"):
                if n_prenda and data_nuevos:
                    df = pd.concat([df, pd.DataFrame(data_nuevos)], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                    for item in data_nuevos:
                        registrar_log("Nuevo", "Taller", item['prenda'], item['talla'], item['color'], item['stock'])
                    st.success(f"✅ {len(data_nuevos)} variantes creadas.")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Falta nombre o colores.")

# MODULO: HISTORIAL
elif modo == "📜 Historial":
    st.header("📜 Auditoría")
    try:
        h = conn.read(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], worksheet="historial", ttl=0)
        st.dataframe(h.iloc[::-1], width='stretch')
    except:
        st.warning("No hay datos en el historial.")
        
