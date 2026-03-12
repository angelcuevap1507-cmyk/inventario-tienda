import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import re

# 1. CONFIGURACIÓN
st.set_page_config(page_title="Inventario Guizado & Moda", layout="wide")

# --- LOGIN ---
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

# --- 2. CONEXIÓN OPTIMIZADA (PARA EVITAR ERROR 429) ---
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Agregamos st.cache_data para que no lea el Excel en cada clic
    @st.cache_data(ttl=300) # Guarda los datos 5 minutos en memoria
    def cargar_datos():
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        data = conn.read(spreadsheet=url, ttl=0)
        data.columns = data.columns.str.strip().str.lower()
        mapeo = {'precio unidad': 'precio_unitario', 'precio_mayor': 'precio_mayorista'}
        data = data.rename(columns=mapeo)
        for col in ['stock', 'precio_unitario', 'precio_mayorista']:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce').fillna(0)
        return data
    
    df = cargar_datos()
except Exception as e:
    # Si Google bloquea por cuota, mostramos un mensaje amigable
    if "429" in str(e):
        st.error("⚠️ Google está saturado. Espera 1 minuto y refresca la página.")
    else:
        st.error(f"Error de conexión: {e}")
    st.stop()

# --- 3. MENÚ PRINCIPAL ---
with st.sidebar:
    st.title("🛍️ Guizado & Moda")
    modo = st.radio("Menú:", ["📦 Stock Tiendas", "🚚 Traslados Rápidos", "🏭 Gestión Taller"])
    if st.button("🔄 Refrescar Inventario"):
        st.cache_data.clear() # Limpia el caché para traer datos nuevos
        st.rerun()
    if st.button("🚪 Salir"):
        st.session_state.logged_in = False
        st.rerun()

# --- 4. MODO: STOCK (ORDENADO) ---
if modo == "📦 Stock Tiendas":
    local_sel = st.selectbox("📍 Local:", sorted(df['local'].unique()))
    df_local = df[df['local'] == local_sel]
    prenda_sel = st.selectbox("👕 Prenda:", sorted(df_local['prenda'].unique()))
    df_p = df_local[df_local['prenda'] == prenda_sel]
    talla_sel = st.radio("📏 Talla:", sorted(df_p['talla'].unique()), horizontal=True)
    
    # Ordenar: Con stock primero, luego Agotados
    df_talla = df_p[df_p['talla'] == talla_sel].copy()
    df_talla['prioridad'] = df_talla['stock'].apply(lambda x: 1 if x > 0 else 0)
    df_ordenado = df_talla.sort_values(by=['prioridad', 'color'], ascending=[False, True])
    
    for idx, row in df_ordenado.iterrows():
        c1, c2, c3 = st.columns([3, 1, 1])
        color_display = row['color'].upper()
        if row['stock'] <= 0:
            c1.markdown(f"**{color_display}** <span style='color:red;'>(AGOTADO)</span>", unsafe_allow_html=True)
        else:
            c1.write(f"**{color_display}**")
        c2.metric("Stock", int(row['stock']))
        adj = c3.number_input("Ajuste", value=0, key=f"adj_{idx}")
        if st.button("Actualizar", key=f"btn_{idx}"):
            df.at[idx, 'stock'] += adj
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            st.success("Guardado")
            st.cache_data.clear() # Limpiar caché para ver el cambio
            st.rerun()

# --- 5. MODO: TRASLADOS ---
elif modo == "🚚 Traslados Rápidos":
    st.header("🚚 Traslado de Mercadería")
    inst = st.text_input("Escribe o dicta:").lower()
    
    s_orig, s_dest, s_prenda, s_talla, s_color, s_cant = None, None, None, None, None, 1
    if inst:
        for l in df['local'].unique():
            if f"de {l.lower()}" in inst: s_orig = l
            if f"a {l.lower()}" in inst: s_dest = l
        for p in df['prenda'].unique():
            if p.lower() in inst: s_prenda = p
        for t in df['talla'].unique():
            if f"talla {t.lower()}" in inst or f" {t.lower()} " in inst: s_talla = t
        for c in df['color'].unique():
            if c.lower() in inst: s_color = c
        n = re.findall(r'\d+', inst)
        if n: s_cant = int(n[-1])

    c1, c2 = st.columns(2)
    origen = c1.selectbox("Desde:", sorted(df['local'].unique()), index=sorted(df['local'].unique()).index(s_orig) if s_orig in df['local'].unique() else 0)
    destino = c2.selectbox("Hacia:", [l for l in sorted(df['local'].unique()) if l != origen], index=0)
    
    df_o = df[(df['local'] == origen) & (df['stock'] > 0)]
    if not df_o.empty:
        p_t = st.selectbox("Prenda:", sorted(df_o['prenda'].unique()), index=sorted(df_o['prenda'].unique()).index(s_prenda) if s_prenda in df_o['prenda'].unique() else 0)
        df_prenda = df_o[df_o['prenda'] == p_t]
        t_t = st.selectbox("Talla:", sorted(df_prenda['talla'].unique()))
        colores_con_stock = sorted(df_prenda[df_prenda['talla'] == t_t]['color'].unique())
        c_t = st.selectbox("Color disponible:", colores_con_stock)
        
        fila_o = df_prenda[(df_prenda['talla'] == t_t) & (df_prenda['color'] == c_t)].iloc[0]
        stock_actual = int(fila_o['stock'])
        
        st.success(f"Stock: {stock_actual}")
        cant = st.number_input("Cantidad:", min_value=1, max_value=stock_actual, value=min(s_cant, stock_actual))
        
        if st.button("🚀 Confirmar Traslado"):
            df.at[fila_o.name, 'stock'] -= cant
            idx_d = df[(df['local'] == destino) & (df['prenda'] == p_t) & (df['talla'] == t_t) & (df['color'] == c_t)].index
            if not idx_d.empty:
                df.at[idx_d[0], 'stock'] += cant
            else:
                nueva = {'local': destino, 'tela': fila_o['tela'], 'prenda': p_t, 'talla': t_t, 'color': c_t, 'stock': cant, 'precio_unitario': fila_o.get('precio_unitario', 0), 'precio_mayorista': 0}
                df = pd.concat([df, pd.DataFrame([nueva])], ignore_index=True)
            conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
            st.success("Traslado Exitoso")
            st.cache_data.clear()
            st.rerun()

# --- 6. MODO: TALLER ---
else:
    st.header("🏭 Gestión Taller")
    t1, t2 = st.tabs(["📥 Agregar Stock", "➕ Nueva Prenda"])
    with t1:
        df_t = df[df['local'] == "Taller"]
        if not df_t.empty:
            p = st.selectbox("Modelo:", sorted(df_t['prenda'].unique()))
            df_p_t = df_t[df_t['prenda'] == p]
            t = st.selectbox("Talla:", sorted(df_p_t['talla'].unique()))
            c = st.selectbox("Color:", sorted(df_p_t[df_p_t['talla'] == t]['color'].unique()))
            cant_t = st.number_input("Cantidad:", min_value=1, value=12)
            if st.button("Sumar al Taller"):
                idx = df[(df['local'] == "Taller") & (df['prenda'] == p) & (df['talla'] == t) & (df['color'] == c)].index[0]
                df.at[idx, 'stock'] += cant_t
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                st.success("Añadido")
                st.cache_data.clear()
                st.rerun()
    with t2:
        with st.form("crear"):
            c1, c2 = st.columns(2); np = c1.text_input("Prenda").upper(); nt = c2.text_input("Tela", value="General")
            nta = st.selectbox("Talla:", ["ST", "S", "M", "L", "XL"])
            nc = st.text_input("Color").upper()
            ns = st.number_input("Stock", min_value=1); pu = st.number_input("Precio Unidad", min_value=0.0)
            if st.form_submit_button("Crear y Registrar"):
                nf = {'local': 'Taller', 'tela': nt, 'prenda': np, 'talla': nta, 'color': nc, 'stock': ns, 'precio_unitario': pu, 'precio_mayorista': 0}
                df = pd.concat([df, pd.DataFrame([nf])], ignore_index=True)
                conn.update(spreadsheet=st.secrets["connections"]["gsheets"]["spreadsheet"], data=df)
                st.success("Creado")
                st.cache_data.clear()
                st.rerun()
