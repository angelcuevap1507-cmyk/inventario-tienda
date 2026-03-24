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
                    st.error("Usuario o contraseña incorrectos")
                if st.session_state.logged_in: st.rerun()
    st.stop()

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        # ttl=0 para que siempre traiga datos frescos si hay errores
        data = conn.read(spreadsheet=url, ttl=0)
        if data is None or data.empty:
            st.warning("El archivo de Excel parece estar vacío.")
            return pd.DataFrame()
        data.columns = data.columns.str.strip().str.lower()
        return data
    except Exception as e:
        st.error(f"Error de conexión: {e}")
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
    except: pass

df = cargar_datos()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.title(f"👤 {st.session_state.role.upper()}")
    if st.session_state.tienda_asignada:
        st.info(f"Sede: {st.session_state.tienda_asignada}")
    
    # Definimos opciones según el ROL
    if st.session_state.role == "admin":
        opciones = ["🚨 Alertas Stock", "📦 Stock Global", "🚚 Traslados", "🏭 Taller", "📜 Historial"]
    else:
        opciones = ["📦 Mi Stock", "🚚 Traslados"]
    
    modo = st.radio("Menú:", opciones)
    st.divider()
    if st.button("🔄 Refrescar"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🚪 Salir"):
        st.session_state.logged_in = False
        st.rerun()

# --- 4. LÓGICA DE MÓDULOS ---

# MODULO 1: ALERTAS (Solo Admin)
if modo == "🚨 Alertas Stock":
    st.header("🚨 Reposición Urgente")
    limite = st.slider("Ver productos con stock igual o menor a:", 0, 15, 5)
    
    # Filtrar tiendas (No taller)
    df_alertas = df[(df['local'].str.upper() != "TALLER") & (df['stock'] <= limite)]
    
    if not df_alertas.empty:
        st.error(f"Se encontraron {len(df_alertas)} variantes con stock bajo.")
        st.dataframe(df_alertas[['local', 'prenda', 'talla', 'color', 'stock']].sort_values(by='stock'), width='stretch')
        
        # Generar texto para WhatsApp
        pedido = "PEDIDO REPOSICIÓN:\n"
        for _, r in df_alertas.iterrows():
            pedido += f"- {r['prenda']} {r['color']} T{r['talla']} en {r['local']} (Stock: {int(r['stock'])})\n"
        st.text_area("Copia para WhatsApp:", value=pedido, height=150)
    else:
        st.success("✅ Todo el stock de las tiendas está bien.")

# MODULO 2: STOCK (Mi Stock / Global)
elif "Stock" in modo:
    st.header("📦 Control de Inventario")
    
    # Selección de local (Admin elige, User tiene fijo)
    if st.session_state.role == "admin":
        locales = sorted(df['local'].unique())
        l_sel = st.selectbox("📍 Seleccionar Local:", locales)
    else:
        l_sel = st.session_state.tienda_asignada
        
    df_l = df[df['local'].str.upper() == l_sel.upper()]
    
    if not df_l.empty:
        p_sel = st.selectbox("👕 Prenda:", sorted(df_l['prenda'].unique()))
        df_p = df_l[df_l['prenda'] == p_sel]
        t_sel = st.radio("📏 Talla:", sorted(df_p['talla'].unique()), horizontal=True)
        
        items = df_p[df_p['talla'] == t_sel].sort_values(by=['stock', 'color'], ascending=[False, True])
        
        for idx, row in items.iterrows():
            st.divider()
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            c1.write(f"**{row['color'].upper()}**" if row['stock'] > 0 else f"**{row['color'].upper()}** (AGOTADO)")
            c2.metric("Stock", int(row['stock']))
            
            adj = c3.number_input("Venta (-)", value=0, key=f"adj_{idx}")
            if c3.button("Guardar", key=f"b_{idx}"):
                df.at[idx, 'stock'] += adj
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("Venta", l_sel, p_sel, t_sel, row['color'], adj)
                st.cache_data.clear(); st.rerun()
            
            if st.session_state.role == "admin":
                fix = c4.number_input("Fix", value=int(row['stock']), key=f"f_{idx}")
                if c4.button("Fix", key=f"bf_{idx}"):
                    diff = fix - row['stock']
                    df.at[idx, 'stock'] = fix
                    conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                    registrar_log("FIX", l_sel, p_sel, t_sel, row['color'], diff)
                    st.cache_data.clear(); st.rerun()
    else:
        st.warning(f"No hay datos para {l_sel}")

# MODULO 3: TRASLADOS
elif modo == "🚚 Traslados":
    st.header("🚚 Traslado entre Sedes")
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
                nuevo = {'local':dest.upper(), 'prenda':p, 'talla':t, 'color':c, 'stock':cant}
                df = pd.concat([df, pd.DataFrame([nuevo])], ignore_index=True)
            
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            registrar_log("Traslado", f"{orig}->{dest}", p, t, c, cant)
            st.cache_data.clear(); st.rerun()
    else:
        st.warning("No hay stock disponible para mover.")

# MODULO 4: TALLER (Solo Admin)
elif modo == "🏭 Taller":
    st.header("🏭 Ingreso de Producción")
    t1, t2 = st.tabs(["📥 Reponer", "➕ Nuevo Modelo"])
    with t1:
        dt = df[df['local'].str.upper() == "TALLER"]
        if not dt.empty:
            p = st.selectbox("Modelo:", sorted(dt['prenda'].unique()))
            t = st.selectbox("Talla:", sorted(dt[dt['prenda']==p]['talla'].unique()), key="t1")
            c = st.selectbox("Color:", sorted(dt[(dt['prenda']==p) & (dt['talla']==t)]['color'].unique()), key="c1")
            can = st.number_input("Cantidad:", min_value=1, value=1)
            if st.button("Sumar al Taller"):
                idx = df[(df['local'].str.upper()=="TALLER") & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].index[0]
                df.at[idx, 'stock'] += can
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("Producción", "Taller", p, t, c, can)
                st.cache_data.clear(); st.rerun()
    with t2:
        with st.form("nuevo_p"):
            np = st.text_input("Nombre Prenda").upper()
            nta = st.selectbox("Talla", ["ST", "S", "M", "L", "XL"])
            nc = st.text_input("Color").upper()
            ns = st.number_input("Stock Inicial", min_value=1)
            if st.form_submit_button("Crear en Taller"):
                nf = {'local':'TALLER', 'prenda':np, 'talla':nta, 'color':nc, 'stock':ns}
                df = pd.concat([df, pd.DataFrame([nf])], ignore_index=True)
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                st.cache_data.clear(); st.rerun()

# MODULO 5: HISTORIAL (Solo Admin)
elif modo == "📜 Historial":
    st.header("📜 Historial de Movimientos")
    try:
        h = conn.read(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], worksheet="historial", ttl=0)
        st.dataframe(h.iloc[::-1], width='stretch')
    except:
        st.warning("Aún no hay registros o falta la pestaña 'historial'.")
                if st.session_state.logged_in: st.rerun()
    st.stop()

# --- 2. CONEXIÓN ---
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
    except: st.error("Error en historial.")

df = cargar_datos()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.title(f"👤 {st.session_state.role.upper()}")
    opciones = ["📦 Mi Stock", "🚚 Traslados"]
    if st.session_state.role == "admin":
        opciones = ["📦 Stock Global", "🚚 Traslados", "🏭 Taller", "📜 Historial", "🚨 Alertas Stock"]
    modo = st.radio("Menú:", opciones)
    st.divider()
    if st.button("🔄 Refrescar"):
        st.cache_data.clear()
        st.rerun()
    if st.button("🚪 Salir"):
        st.session_state.logged_in = False
        st.rerun()

# --- 4. LÓGICA DE MÓDULOS (CORREGIDA) ---

# IMPORTANTE: Cambiamos el orden para que "Alertas Stock" no se confunda con "Stock Global"
if modo == "🚨 Alertas Stock":
    st.header("🚨 Reposición Urgente (Stock Bajo)")
    
    # Slider para definir qué es stock bajo
    limite = st.slider("Mostrar productos con stock menor o igual a:", 0, 15, 5)
    
    # Filtrar: Quitamos el Taller y filtramos por el límite
    df_alertas = df[(df['local'].str.upper() != "TALLER") & (df['stock'] <= limite)]
    
    if not df_alertas.empty:
        st.error(f"⚠️ Se encontraron {len(df_alertas)} variantes para reponer.")
        
        # Mostrar tabla limpia
        st.dataframe(
            df_alertas[['local', 'prenda', 'talla', 'color', 'stock']].sort_values(by='stock'),
            width='stretch'
        )
        
        # Generar lista para copiar a WhatsApp
        texto_ws = "REPOSICIÓN GUIZADO & MODA:\n"
        for _, r in df_alertas.iterrows():
            texto_ws += f"- {r['prenda']} {r['color']} T{r['talla']} en {r['local']} (Quedan: {int(r['stock'])})\n"
        
        st.text_area("Copia esto para pedir al taller:", value=texto_ws, height=200)
    else:
        st.success("✅ ¡Todo bien! No hay productos por debajo del límite en las tiendas.")

elif "Stock" in modo:
    # AQUÍ VA TU CÓDIGO DE INVENTARIO NORMAL (EL QUE TIENE LOS BOTONES FIX Y GUARDAR)
    st.header(f"📦 Inventario {st.session_state.tienda_asignada if st.session_state.role == 'user' else 'Global'}")
    
# --- 5. MODO: TRASLADOS ---
elif "Traslado" in modo:
    st.header("🚚 Traslados")
    orig = st.session_state.tienda_asignada if st.session_state.role == "user" else st.selectbox("Desde:", sorted(df['local'].unique()))
    dest = st.selectbox("Hacia:", [l for l in sorted(df['local'].unique()) if l != orig])
    df_o = df[(df['local'].str.upper() == orig.upper()) & (df['stock'] > 0)]
    if not df_o.empty:
        p = st.selectbox("Prenda:", sorted(df_o['prenda'].unique()))
        t = st.selectbox("Talla:", sorted(df_o[df_o['prenda']==p]['talla'].unique()))
        c = st.selectbox("Color:", sorted(df_o[(df_o['prenda']==p) & (df_o['talla']==t)]['color'].unique()))
        fila_o = df[(df['local'].str.upper()==orig.upper()) & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].iloc[0]
        cant = st.number_input("Cantidad:", min_value=1, max_value=int(fila_o['stock']), value=1)
        if st.button("Confirmar Traslado"):
            df.at[fila_o.name, 'stock'] -= cant
            idx_d = df[(df['local'].str.upper()==dest.upper()) & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].index
            if not idx_d.empty: df.at[idx_d[0], 'stock'] += cant
            else: df = pd.concat([df, pd.DataFrame([{'local':dest.upper(),'prenda':p,'talla':t,'color':c,'stock':cant}])], ignore_index=True)
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            registrar_log("Traslado", f"{orig}->{dest}", p, t, c, cant)
            st.cache_data.clear(); st.rerun()

# --- 6. MODO: TALLER (ADMIN) ---
elif modo == "🏭 Taller":
    st.header("🏭 Taller")
    t1, t2 = st.tabs(["Reponer", "Nuevo"])
    with t1:
        dt = df[df['local'].str.upper() == "TALLER"]
        if not dt.empty:
            p = st.selectbox("Modelo:", sorted(dt['prenda'].unique()))
            t = st.selectbox("Talla:", sorted(dt[dt['prenda']==p]['talla'].unique()), key="t1")
            c = st.selectbox("Color:", sorted(dt[(dt['prenda']==p) & (dt['talla']==t)]['color'].unique()), key="c1")
            can = st.number_input("Cantidad:", min_value=1, value=1)
            if st.button("Sumar"):
                idx = df[(df['local'].str.upper()=="TALLER") & (df['prenda']==p) & (df['talla']==t) & (df['color']==c)].index[0]
                df.at[idx, 'stock'] += can
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("Producción", "Taller", p, t, c, can)
                st.cache_data.clear(); st.rerun()
    with t2:
        es_n = st.checkbox("¿Nuevo modelo?")
        with st.form("f_n"):
            np = st.text_input("Nombre").upper() if es_n else st.selectbox("Modelo:", sorted(df['prenda'].unique()))
            nta = st.selectbox("Talla", ["ST", "S", "M", "L", "XL"])
            nc = st.text_input("Color").upper(); ns = st.number_input("Stock", min_value=1)
            if st.form_submit_button("Crear"):
                df = pd.concat([df, pd.DataFrame([{'local':'TALLER','prenda':np,'talla':nta,'color':nc,'stock':ns}])], ignore_index=True)
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                registrar_log("Nuevo", "Taller", np, nta, nc, ns)
                st.cache_data.clear(); st.rerun()

# --- 7. MODO: HISTORIAL (ADMIN) ---
elif modo == "📜 Historial":
    st.header("📊 Historial")
    h = conn.read(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], worksheet="historial", ttl=0)
    h['fecha_dt'] = pd.to_datetime(h['fecha'], format='%d/%m/%Y')
    r = st.date_input("Días:", [datetime.now(), datetime.now()])
    if len(r)==2:
        hf = h[(h['fecha_dt'].dt.date >= r[0]) & (h['fecha_dt'].dt.date <= r[1])]
        st.plotly_chart(px.bar(hf[hf['tipo']=="Venta"].groupby('prenda')['cantidad'].sum().abs().reset_index(), x='prenda', y='cantidad'), width='stretch')
        st.dataframe(hf.sort_values(by=['fecha_dt','hora'], ascending=False), width='stretch')

# --- 8. MODO: ALERTAS (ADMIN) ---
elif modo == "🚨 Alertas Stock":
    st.header("🚨 Reposición Urgente")
    
    # Esto define qué tan "vacío" debe estar algo para que sea alerta
    limite = st.sidebar.slider("Ver productos con menos de:", 1, 20, 5)
    
    # Filtramos: Solo tiendas (no Taller) y solo lo que esté debajo del límite
    df_alertas = df[(df['local'].str.upper() != "TALLER") & (df['stock'] <= limite)]
    
    if not df_alertas.empty:
        st.error(f"⚠️ Tienes {len(df_alertas)} productos que necesitan reposición inmediata.")
        
        # Agrupamos para que sea más fácil de leer que el inventario normal
        resumen_alertas = df_alertas[['local', 'prenda', 'talla', 'color', 'stock']].sort_values(by='stock')
        
        # Mostramos una tabla limpia, sin botones de "Venta" o "Fix", solo para lectura
        st.dataframe(resumen_alertas, width='stretch')
        
        # Botón extra: Copiar lista para WhatsApp
        texto_pedido = "Lista de Reposición Guizado & Moda:\n"
        for _, row in resumen_alertas.iterrows():
            texto_pedido += f"- {row['prenda']} ({row['color']} Talla {row['talla']}) en {row['local']}: Quedan {int(row['stock'])}\n"
        
        st.text_area("Copia esto para mandarlo al Taller:", valor=texto_pedido, height=150)
    else:
        st.success("✅ ¡Excelente! Todas tus tiendas tienen stock suficiente por ahora.")
