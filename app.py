import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Guizado & Moda - Sistema Pro", layout="wide")

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
                    st.session_state.logged_in, st.session_state.role = True, "admin"
                elif u == "moda" and p == "moda2026":
                    st.session_state.logged_in, st.session_state.role, st.session_state.tienda_asignada = True, "user", "MODA"
                elif u == "guizado" and p == "guizado2026":
                    st.session_state.logged_in, st.session_state.role, st.session_state.tienda_asignada = True, "user", "GUIZADO"
                else:
                    st.error("Credenciales incorrectas")
                if st.session_state.logged_in:
                    st.rerun()
    st.stop()

# --- 2. CONEXIÓN Y FUNCIONES DE DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        data = conn.read(spreadsheet=url, ttl=0)
        # Limpieza de columnas
        data.columns = [str(c).strip().lower() for c in data.columns]
        # UNIFICACIÓN DE LOCALES: Pasa todo a MAYÚSCULAS y quita espacios
        if 'local' in data.columns:
            data['local'] = data['local'].astype(str).str.strip().str.upper()
        return data
    except Exception as e:
        st.error(f"Error al cargar Inventario: {e}")
        return pd.DataFrame()

def registrar_log(tipo, local, prenda, talla, color, cant):
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        try:
            logs = conn.read(spreadsheet=url, worksheet="historial", ttl=0)
            logs.columns = [str(c).strip().lower() for c in logs.columns]
        except:
            logs = pd.DataFrame(columns=["fecha", "hora", "tipo", "local", "prenda", "talla", "color", "cantidad"])
        
        ahora = datetime.now()
        nueva = pd.DataFrame([{
            "fecha": ahora.strftime("%d/%m/%Y"), "hora": ahora.strftime("%H:%M:%S"),
            "tipo": tipo, "local": local.upper(), "prenda": prenda.upper(),
            "talla": talla.upper(), "color": color.upper(), "cantidad": cant
        }])
        conn.update(spreadsheet=url, worksheet="historial", data=pd.concat([logs, nueva], ignore_index=True))
    except:
        pass

df = cargar_datos()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.title(f"👤 {st.session_state.role.upper()}")
    opciones = ["🚨 Alertas Stock", "📦 Stock Global", "🚚 Traslados", "🏭 Taller", "📜 Historial"] if st.session_state.role == "admin" else ["📦 Mi Stock", "🚚 Traslados"]
    modo = st.radio("Menú:", opciones)
    if st.button("🔄 Refrescar Datos"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🚪 Salir"):
        st.session_state.logged_in = False
        st.rerun()

# --- 4. MÓDULOS ---

# MÓDULO: STOCK
if "Stock" in modo:
    st.header("📦 Inventario")
    if st.session_state.role == "admin":
        # sorted(df['local'].unique()) ahora devolverá solo "GUIZADO", "MODA" y "TALLER"
        l_sel = st.selectbox("📍 Local:", sorted(df['local'].unique()))
    else:
        l_sel = st.session_state.tienda_asignada
        
    df_l = df[df['local'] == l_sel]
    
    if not df_l.empty:
        p_sel = st.selectbox("👕 Prenda:", sorted(df_l['prenda'].unique()))
        items = df_l[df_l['prenda'] == p_sel].sort_values(by=['talla', 'color'])
        for idx, row in items.iterrows():
            st.divider()
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.write(f"**{row['color'].upper()}** (Talla {row['talla']})")
            c2.metric("Stock", int(row['stock']))
            adj = c3.number_input("Venta", value=0, key=f"adj_{idx}")
            if c3.button("Guardar", key=f"b_{idx}"):
                df.at[idx, 'stock'] += adj
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("Venta", l_sel, p_sel, row['talla'], row['color'], adj)
                st.cache_data.clear(); st.rerun()

# MÓDULO: TRASLADOS
elif modo == "🚚 Traslados":
    st.header("🚚 Traslado Masivo")
    locales_disponibles = sorted(df['local'].unique())
    c1, c2 = st.columns(2)
    orig = c1.selectbox("Desde (Origen):", locales_disponibles)
    dest = c2.selectbox("Hacia (Destino):", [l for l in locales_disponibles if l != orig])
    
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
                cc1.write(f"**{sel['prenda']}** - {sel['color']} (T{sel['talla']})")
                cant_env = cc2.number_input(f"Cantidad", min_value=1, max_value=int(sel['stock']), value=1, key=f"mov_{sel.name}")
                items_a_mover.append({"prenda": sel['prenda'], "talla": sel['talla'], "color": sel['color'], "cantidad": cant_env})
            
            if st.button("🚀 Confirmar Envío"):
                for item in items_a_mover:
                    idx_o = df[(df['local']==orig) & (df['prenda']==item['prenda']) & (df['talla']==item['talla']) & (df['color']==item['color'])].index[0]
                    df.at[idx_o, 'stock'] -= item['cantidad']
                    idx_d = df[(df['local']==dest) & (df['prenda']==item['prenda']) & (df['talla']==item['talla']) & (df['color']==item['color'])].index
                    if not idx_d.empty:
                        df.at[idx_d[0], 'stock'] += item['cantidad']
                    else:
                        df = pd.concat([df, pd.DataFrame([{'local':dest, 'prenda':item['prenda'], 'talla':item['talla'], 'color':item['color'], 'stock':item['cantidad']}])], ignore_index=True)
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                st.success("Traslado exitoso"); st.cache_data.clear(); st.rerun()

# MÓDULO: TALLER (ADMIN)
elif modo == "🏭 Taller":
    st.header("🏭 Producción")
    t1, t2 = st.tabs(["📥 Reponer", "➕ Nuevo Modelo"])
    with t1:
        dt = df[df['local'] == "TALLER"]
        if not dt.empty:
            p = st.selectbox("Modelo:", sorted(dt['prenda'].unique()))
            t = st.selectbox("Talla:", sorted(dt[dt['prenda']==p]['talla'].unique()))
            c = st.selectbox("Color:", sorted(dt[(dt['prenda']==p) & (dt['talla']==t)]['color'].unique()))
            can = st.number_input("Cantidad:", min_value=1, value=1)
            if st.button("Sumar"):
                idx = df[(df['local']=="TALLER") & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].index[0]
                df.at[idx, 'stock'] += can
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                st.cache_data.clear(); st.rerun()
    with t2:
        with st.form("f_masivo"):
            np = st.text_input("Nombre de Prenda").upper()
            nt = st.selectbox("Talla", ["ST", "S", "M", "L", "XL"])
            nuevos = []
            for i in range(10):
                c1, c2 = st.columns([3, 2])
                col = c1.text_input(f"Color {i+1}", key=f"nc_{i}").upper()
                qty = c2.number_input(f"Cantidad {i+1}", min_value=0, value=0, key=f"nq_{i}")
                if col and qty > 0: nuevos.append({'local':'TALLER', 'prenda':np, 'talla':nt, 'color':col, 'stock':qty})
            if st.form_submit_button("🚀 Crear todas"):
                if np and nuevos:
                    df = pd.concat([df, pd.DataFrame(nuevos)], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                    st.cache_data.clear(); st.rerun()

# MÓDULO: ALERTAS / HISTORIAL
elif modo == "🚨 Alertas Stock":
    st.header("🚨 Reposición Urgente")
    limite = st.slider("Stock menor a:", 0, 20, 5)
    df_a = df[(df['local'] != "TALLER") & (df['stock'] <= limite)]
    st.dataframe(df_a[['local', 'prenda', 'talla', 'color', 'stock']].sort_values(by='stock'), use_container_width=True)

elif modo == "📜 Historial":
    st.header("📜 Historial")
    try:
        h = conn.read(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], worksheet="historial", ttl=0)
        st.dataframe(h.iloc[::-1], use_container_width=True)
    except: st.warning("Historial no encontrado.")
