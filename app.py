import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Inventario General Tiendas", layout="wide")

# --- FUNCIÓN DE LOGIN ---
def login():
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Inventario</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        with st.form("login"):
            usuario = st.text_input("Usuario")
            clave = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                # Credenciales generales
                if usuario == "tienda" and clave == "ventas2026":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")

# Verificar sesión
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login()
    st.stop()

# --- INICIO DE LA APLICACIÓN (POST-LOGIN) ---

# 2. CONEXIÓN AL EXCEL
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
    
    # LIMPIEZA DE DATOS
    df.columns = df.columns.str.strip().str.lower()
    df = df.dropna(subset=['local', 'tela', 'prenda'])
    
    # Convertimos todo a texto para evitar errores de búsqueda
    for col in ['local', 'tela', 'prenda', 'talla', 'color']:
        df[col] = df[col].astype(str)
    
except Exception as e:
    st.error(f"Error al conectar con el Excel: {e}")
    st.stop()

# --- BARRA LATERAL: NAVEGACIÓN ---
with st.sidebar:
    st.title("🛍️ Menú Inventario")
    
    # 1. Selección de Local
    opcion_local = st.selectbox("📍 Selecciona Local:", sorted(df['local'].unique()))
    
    st.divider()
    
    # 2. Selección de Tela
    df_local = df[df['local'] == opcion_local]
    opcion_tela = st.selectbox("🧶 Tipo de Tela:", sorted(df_local['tela'].unique()))
    
    st.divider()
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.logged_in = False
        st.rerun()

# --- PANTALLA PRINCIPAL ---
st.header(f"📍 Local: {opcion_local}")
# AQUÍ ESTABA EL ERROR (SE CORRIGE LA COMILLA):
st.info(f"Categoría: Tela {opcion_tela}")

# 3. Selección de Prenda
df_prenda_list = df_local[df_local['tela'] == opcion_tela]
opcion_prenda = st.selectbox("👕 Selecciona Prenda:", sorted(df_prenda_list['prenda'].unique()))

# 4. Selección de Talla (Horizontal)
st.write("### 📏 Selecciona la Talla:")
df_final = df_prenda_list[df_prenda_list['prenda'] == opcion_prenda]
opcion_talla = st.radio("Tallas", sorted(df_final['talla'].unique()), horizontal=True, label_visibility="collapsed")

st.divider()

# 5. RESULTADOS
st.subheader(f"Stock en {opcion_prenda} - Talla {opcion_talla}")
df_colores = df_final[df_final['talla'] == opcion_talla]

if not df_colores.empty:
    cols = st.columns(4)
    for i, (index, row) in enumerate(df_colores.iterrows()):
        with cols[i % 4]:
            # Limpiamos el valor de stock para que sea un número entero
            try:
                cantidad = int(float(row['stock']))
            except:
                cantidad = 0
                
            st.markdown(f"""
            <div style="background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #e6e9ef; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); margin-bottom: 10px;">
                <h4 style="margin:0; color: #31333F;">{row['color'].upper()}</h4>
                <h1 style="margin:10px 0; color: #ff4b4b;">{cantidad}</h1>
                <p style="margin:0; font-size: 14px; font-weight: bold;">Unidad: S/ {row['precio_unidad']}</p>
                <p style="margin:0; font-size: 12px; color: gray;">Mayor: S/ {row['precio_mayor']}</p>
            </div>
            """, unsafe_allow_html=True)
else:
    st.warning("No hay stock disponible para esta combinación.")

# Botón para actualizar
st.sidebar.divider()
if st.sidebar.button("🔄 Sincronizar Excel"):
    st.cache_data.clear()
    st.rerun()