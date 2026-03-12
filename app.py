import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
from datetime import datetime

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Inventario Guizado & Moda", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Sistema</h2>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                if u == "tienda" and p == "ventas2026":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
    st.stop()

# --- 2. CONEXIÓN Y REGISTRO ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def cargar_datos():
    url = st.secrets["connections"]["gsheets"]["spreadsheet"]
    data = conn.read(spreadsheet=url, ttl=0)
    data.columns = data.columns.str.strip().str.lower()
    return data

def registrar_log(tipo, local, prenda, talla, color, cant):
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        logs = conn.read(spreadsheet=url, worksheet="historial", ttl=0)
        ahora = datetime.now()
        nueva_fila = pd.DataFrame([{
            "fecha": ahora.strftime("%d/%m/%Y"),
            "hora": ahora.strftime("%H:%M:%S"),
            "tipo": tipo,
            "local": local,
            "prenda": prenda,
            "talla": talla,
            "color": color,
            "cantidad": cant
        }])
        logs_actualizados = pd.concat([logs, nueva_fila], ignore_index=True)
        conn.update(spreadsheet=url, worksheet="historial", data=logs_actualizados)
    except Exception as e:
        st.error(f"Error al registrar historial: {e}")

df = cargar_datos()

# --- 3. MENÚ ---
with st.sidebar:
    st.title("🛍️ Panel Control")
    modo = st.radio("Menú:", ["📦 Stock Tiendas", "🚚 Traslados", "🏭 Taller", "📜 Ver Historial"])
    if st.button("🔄 Refrescar Datos"):
        st.cache_data.clear()
        st.rerun()

# --- 4. MODO: STOCK ---
if modo == "📦 Stock Tiendas":
    local_sel = st.selectbox("📍 Local:", sorted(df['local'].unique()))
    df_l = df[df['local'] == local_sel]
    prenda_sel = st.selectbox("👕 Prenda:", sorted(df_l['prenda'].unique()))
    df_p = df_l[df_l['prenda'] == prenda_sel]
    talla_sel = st.radio("📏 Talla:", sorted(df_p['talla'].unique()), horizontal=True)
    
    df_talla = df_p[df_p['talla'] == talla_sel].copy()
    df_talla['prioridad'] = df_talla['stock'].apply(lambda x: 1 if x > 0 else 0)
    df_ord = df_talla.sort_values(by=['prioridad', 'color'], ascending=[False, True])

    for idx, row in df_ord.iterrows():
        c1, c2, c3 = st.columns([3, 1, 1])
        c1.write(f"**{row['color'].upper()}**" if row['stock'] > 0 else f"**{row['color'].upper()}** (AGOTADO)")
        c2.metric("Stock", int(row['stock']))
        adj = c3.number_input("Venta/Ajuste", value=0, key=f"adj_{idx}")
        if st.button("Guardar", key=f"btn_{idx}"):
            df.at[idx, 'stock'] += adj
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            registrar_log("Venta/Ajuste", local_sel, prenda_sel, talla_sel, row['color'], adj)
            st.success("Guardado")
            st.cache_data.clear()
            st.rerun()

# --- 5. MODO: TRASLADOS ---
elif modo == "🚚 Traslados":
    st.header("🚚 Traslado")
    c1, c2 = st.columns(2)
    origen = c1.selectbox("Desde:", sorted(df['local'].unique()))
    destino = c2.selectbox("Hacia:", [l for l in sorted(df['local'].unique()) if l != origen])
    
    df_o = df[(df['local'] == origen) & (df['stock'] > 0)]
    if not df_o.empty:
        p_t = st.selectbox("Prenda:", sorted(df_o['prenda'].unique()))
        t_t = st.selectbox("Talla:", sorted(df_o[df_o['prenda'] == p_t]['talla'].unique()))
        c_t = st.selectbox("Color:", sorted(df_o[(df_o['prenda'] == p_t) & (df_o['talla'] == t_t)]['color'].unique()))
        fila_o = df_o[(df_o['prenda'] == p_t) & (df_o['talla'] == t_t) & (df_o['color'] == c_t)].iloc[0]
        cant = st.number_input("Cantidad:", min_value=1, max_value=int(fila_o['stock']), value=1)
        
        if st.button("🚀 Confirmar Traslado"):
            df.at[fila_o.name, 'stock'] -= cant
            idx_d = df[(df['local'] == destino) & (df['prenda'] == p_t) & (df['talla'] == t_t) & (df['color'] == c_t)].index
            if not idx_d.empty:
                df.at[idx_d[0], 'stock'] += cant
            else:
                nueva = {'local': destino, 'tela': fila_o['tela'], 'prenda': p_t, 'talla': t_t, 'color': c_t, 'stock': cant}
                df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
            
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            registrar_log("Traslado", f"{origen} -> {destino}", p_t, t_t, c_t, cant)
            st.success("Traslado Exitoso")
            st.cache_data.clear()
            st.rerun()

# --- 6. MODO: TALLER ---
elif modo == "🏭 Taller":
    st.header("🏭 Producción")
    with st.form("crear_taller"):
        np = st.text_input("Prenda").upper()
        nta = st.selectbox("Talla", ["ST", "S", "M", "L", "XL"])
        nc = st.text_input("Color").upper()
        ns = st.number_input("Stock", min_value=1)
        if st.form_submit_button("Registrar Producción"):
            nf = {'local': 'Taller', 'prenda': np, 'talla': nta, 'color': nc, 'stock': ns}
            df = pd.concat([df, pd.DataFrame([nf])], ignore_index=True)
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            registrar_log("Producción", "Taller", np, nta, nc, ns)
            st.success("Añadido")
            st.cache_data.clear()
            st.rerun()

# --- 7. MODO: VER HISTORIAL Y DESCARGAR ---
elif modo == "📜 Ver Historial":
    st.header("📜 Registro de Movimientos")
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        h_df = conn.read(spreadsheet=url, worksheet="historial", ttl=0)
        
        # Botón para descargar
        csv = h_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Historial (Excel/CSV)",
            data=csv,
            file_name=f"historial_inventario_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv',
        )
        
        st.dataframe(h_df.sort_index(ascending=False), use_container_width=True)
    except:
        st.warning("Recuerda crear la hoja 'historial' en tu Google Sheet para activar esta función.")
