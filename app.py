import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re
from datetime import datetime
import plotly.express as px

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Guizado & Moda - Sistema Pro", layout="wide")

# --- LOGIN SISTEMA ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None

if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso Guizado & Moda</h2>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 1, 1])
    with col2:
        with st.form("login"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                if u == "lachi" and p == "admin2026":
                    st.session_state.logged_in = True
                    st.session_state.role = "admin"
                    st.rerun()
                elif u == "tienda" and p == "ventas2026":
                    st.session_state.logged_in = True
                    st.session_state.role = "user"
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
    st.stop()

# --- 2. CONEXIÓN Y FUNCIONES ---
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
        # Intenta leer el historial, si no existe o falla, crea un DF vacío
        try:
            logs = conn.read(spreadsheet=url, worksheet="historial", ttl=0)
        except:
            logs = pd.DataFrame(columns=["fecha", "hora", "tipo", "local", "prenda", "talla", "color", "cantidad"])
        
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
        logs_updated = pd.concat([logs, nueva_fila], ignore_index=True)
        conn.update(spreadsheet=url, worksheet="historial", data=logs_updated)
    except Exception as e:
        st.error(f"Error al grabar historial: {e}")

df = cargar_datos()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.title(f"👤 {st.session_state.role.upper()}")
    opciones = ["📦 Stock Tiendas", "🚚 Traslados"]
    if st.session_state.role == "admin":
        opciones += ["🏭 Taller", "📜 Historial y Filtros", "🚨 Alertas Stock"]
    
    modo = st.radio("Menú:", opciones)
    
    st.divider()
    if st.button("🔄 Refrescar Inventario"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🚪 Salir"):
        st.session_state.logged_in = False
        st.rerun()

# --- 4. MODO: STOCK ---
if modo == "📦 Stock Tiendas":
    st.header("📦 Inventario de Tiendas")
    local_sel = st.selectbox("📍 Selecciona Local:", sorted(df['local'].unique()))
    df_l = df[df['local'] == local_sel]
    prenda_sel = st.selectbox("👕 Selecciona Prenda:", sorted(df_l['prenda'].unique()))
    df_p = df_l[df_l['prenda'] == prenda_sel]
    talla_sel = st.radio("📏 Talla:", sorted(df_p['talla'].unique()), horizontal=True)
    
    # Ordenamiento: Con stock (A-Z) primero, Agotados (A-Z) después
    df_talla = df_p[df_p['talla'] == talla_sel].copy()
    df_talla['prioridad'] = df_talla['stock'].apply(lambda x: 1 if x > 0 else 0)
    df_ord = df_talla.sort_values(by=['prioridad', 'color'], ascending=[False, True])

    for idx, row in df_ord.iterrows():
        st.divider()
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        
        color_txt = row['color'].upper()
        if row['stock'] <= 0:
            c1.markdown(f"**{color_txt}** <br><span style='color:red; font-size:12px;'>AGOTADO</span>", unsafe_allow_html=True)
        else:
            c1.write(f"**{color_txt}**")
            
        c2.metric("Stock Actual", int(row['stock']))
        
        # Ajuste rápido (Venta/Ingreso)
        adj = c3.number_input("Venta/Ajuste (+/-)", value=0, key=f"adj_{idx}")
        if c3.button("Guardar", key=f"btn_v_{idx}"):
            df.at[idx, 'stock'] += adj
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            registrar_log("Venta/Ajuste", local_sel, prenda_sel, talla_sel, row['color'], adj)
            st.cache_data.clear()
            st.rerun()
            
        # Corrección Manual (Solo Admin)
        if st.session_state.role == "admin":
            fix = c4.number_input("Corregir a:", value=int(row['stock']), key=f"fix_{idx}")
            if c4.button("Fix Total", key=f"btn_f_{idx}"):
                diff = fix - row['stock']
                df.at[idx, 'stock'] = fix
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("CORRECCIÓN MANUAL", local_sel, prenda_sel, talla_sel, row['color'], diff)
                st.cache_data.clear()
                st.rerun()

# --- 5. MODO: TRASLADOS ---
elif modo == "🚚 Traslados":
    st.header("🚚 Traslado de Mercadería")
    c1, c2 = st.columns(2)
    orig = c1.selectbox("Desde:", sorted(df['local'].unique()))
    dest = c2.selectbox("Hacia:", [l for l in sorted(df['local'].unique()) if l != orig])
    
    # Solo mostrar colores que tengan stock en el origen
    df_o = df[(df['local'] == orig) & (df['stock'] > 0)]
    
    if not df_o.empty:
        p_t = st.selectbox("Prenda:", sorted(df_o['prenda'].unique()))
        df_p_o = df_o[df_o['prenda'] == p_t]
        t_t = st.selectbox("Talla:", sorted(df_p_o['talla'].unique()))
        c_t = st.selectbox("Color disponible:", sorted(df_p_o[df_p_o['talla'] == t_t]['color'].unique()))
        
        fila_o = df_p_o[(df_p_o['talla'] == t_t) & (df_p_o['color'] == c_t)].iloc[0]
        max_t = int(fila_o['stock'])
        
        st.info(f"Stock disponible en {orig}: {max_t}")
        cant = st.number_input("Cantidad a trasladar:", min_value=1, max_value=max_t, value=1)
        
        if st.button("🚀 Confirmar Traslado"):
            df.at[fila_o.name, 'stock'] -= cant
            # Buscar en destino
            idx_dest = df[(df['local'] == dest) & (df['prenda'] == p_t) & (df['talla'] == t_t) & (df['color'] == c_t)].index
            if not idx_dest.empty:
                df.at[idx_dest[0], 'stock'] += cant
            else:
                nueva = {'local': dest, 'prenda': p_t, 'talla': t_t, 'color': c_t, 'stock': cant}
                df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
            
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            registrar_log("Traslado", f"{orig} -> {dest}", p_t, t_t, c_t, cant)
            st.success("Traslado completado.")
            st.cache_data.clear()
            st.rerun()
    else:
        st.warning(f"No hay stock disponible en {orig} para trasladar.")

# --- 6. MODO: TALLER (ADMIN) ---
elif modo == "🏭 Taller":
    st.header("🏭 Gestión de Producción")
    t1, t2 = st.tabs(["📥 Reponer Stock (Existente)", "➕ Nueva Prenda/Color"])
    
    with t1:
        df_tall = df[df['local'] == "Taller"]
        if not df_tall.empty:
            p_ex = st.selectbox("Modelo:", sorted(df_tall['prenda'].unique()))
            df_p_ex = df_tall[df_tall['prenda'] == p_ex]
            t_ex = st.selectbox("Talla:", sorted(df_p_ex['talla'].unique()), key="tex")
            c_ex = st.selectbox("Color:", sorted(df_p_ex[df_p_ex['talla'] == t_ex]['color'].unique()), key="cex")
            cant_r = st.number_input("Cantidad producida:", min_value=1, value=1, key="crep")
            if st.button("📥 Sumar a Taller"):
                idx = df[(df['local']=="Taller") & (df['prenda']==p_ex) & (df['talla']==t_ex) & (df['color']==c_ex)].index[0]
                df.at[idx, 'stock'] += cant_r
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("Producción", "Taller", p_ex, t_ex, c_ex, cant_r)
                st.cache_data.clear()
                st.rerun()
    
    with t2:
        es_nuevo_mod = st.checkbox("¿Es un modelo totalmente nuevo?")
        modelos = sorted(df['prenda'].unique())
        with st.form("form_taller"):
            np = st.text_input("Nombre de Prenda").upper() if es_nuevo_mod else st.selectbox("Modelo:", modelos)
            nta = st.selectbox("Talla", ["ST", "S", "M", "L", "XL"])
            nc = st.text_input("Nuevo Color").upper()
            ns = st.number_input("Stock Inicial", min_value=1)
            if st.form_submit_button("➕ Crear y Registrar"):
                # Verificar duplicado
                if not df[(df['local']=='Taller') & (df['prenda']==np) & (df['talla']==nta) & (df['color']==nc)].empty:
                    st.error("Ya existe. Usa 'Reponer Stock'.")
                else:
                    nf = {'local': 'Taller', 'prenda': np, 'talla': nta, 'color': nc, 'stock': ns}
                    df = pd.concat([df, pd.DataFrame([nf])], ignore_index=True)
                    conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                    registrar_log("Nuevo Ingreso", "Taller", np, nta, nc, ns)
                    st.cache_data.clear()
                    st.rerun()

# --- 7. MODO: HISTORIAL (ADMIN) ---
elif modo == "📜 Historial y Filtros":
    st.header("📊 Análisis de Movimientos")
    h_df = conn.read(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], worksheet="historial", ttl=0)
    h_df['fecha_dt'] = pd.to_datetime(h_df['fecha'], format='%d/%m/%Y')
    
    c1, c2 = st.columns(2)
    rango = c1.date_input("Filtrar Días:", [datetime.now(), datetime.now()])
    loc_fil = c2.selectbox("Local:", ["TODOS"] + sorted(h_df['local'].unique().tolist()))
    
    if len(rango) == 2:
        h_f = h_df[(h_df['fecha_dt'].dt.date >= rango[0]) & (h_df['fecha_dt'].dt.date <= rango[1])]
        if loc_fil != "TODOS": h_f = h_f[h_f['local'] == loc_fil]
        
        # Gráfico
        if not h_f.empty:
            vtas = h_f[h_f['tipo'] == "Venta/Ajuste"]
            if not vtas.empty:
                st.plotly_chart(px.bar(vtas.groupby('prenda')['cantidad'].sum().abs().reset_index(), 
                                       x='prenda', y='cantidad', title="Modelos más pedidos"), use_container_width=True)
        
        csv = h_f.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte CSV", csv, "reporte.csv", "text/csv")
        st.dataframe(h_f.sort_values(by=['fecha_dt', 'hora'], ascending=False), use_container_width=True)

# --- 8. MODO: ALERTAS (ADMIN) ---
elif modo == "🚨 Alertas Stock":
    st.header("🚨 Reposición Urgente")
    limite = st.slider("Avisar si el stock es menor a:", 1, 10, 3)
    criticos = df[(df['stock'] <= limite) & (df['local'] != "Taller")]
    if not criticos.empty:
        st.warning(f"Se encontraron {len(criticos)} variantes con stock crítico.")
        st.table(criticos[['local', 'prenda', 'talla', 'color', 'stock']])
    else:
        st.success("¡Todo el stock está bien!")
