import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Control Pro Inventario", layout="wide", page_icon="🏢")

# --- FUNCIONES DE PERSISTENCIA ---
FILE_NAME = 'inventario.xlsx'

def cargar_datos():
    if os.path.exists(FILE_NAME):
        try:
            df = pd.read_excel(FILE_NAME)
            # Estandarizar columnas para evitar KeyError
            df.columns = df.columns.str.strip().str.lower()
            return df
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
            return crear_df_vacio()
    else:
        return crear_df_vacio()

def crear_df_vacio():
    return pd.DataFrame(columns=['local', 'producto', 'cantidad', 'ultima_actualizacion'])

def guardar_datos(df):
    df.to_excel(FILE_NAME, index=False)

# --- INICIALIZACIÓN ---
if 'df' not in st.session_state:
    st.session_state.df = cargar_datos()

# --- INTERFAZ ---
st.title("🚀 Sistema Integral de Inventario")

tab1, tab2, tab3 = st.tabs(["📊 Vista General", "🔄 Movimientos", "⚙️ Gestión de Productos"])

# --- TAB 1: VISTA GENERAL ---
with tab1:
    st.subheader("Estado Actual del Stock")
    if not st.session_state.df.empty:
        # Filtros rápidos
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_sede = st.multiselect("Filtrar por Sede:", options=st.session_state.df['local'].unique())
        
        df_display = st.session_state.df
        if filtro_sede:
            df_display = df_display[df_display['local'].isin(filtro_sede)]
        
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Botón para descargar reporte
        csv = df_display.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte CSV", data=csv, file_name="inventario_actual.csv", mime="text/csv")
    else:
        st.info("El inventario está vacío. Ve a la pestaña de Gestión para añadir productos.")

# --- TAB 2: MOVIMIENTOS (TRASLADOS Y AJUSTES) ---
with tab2:
    if not st.session_state.df.empty:
        st.subheader("Registrar Traslado entre Sedes")
        col_t1, col_t2, col_t3 = st.columns(3)
        
        sedes_disponibles = st.session_state.df['local'].unique()
        
        with col_t1:
            origen = st.selectbox("Sede Origen:", sedes_disponibles)
        with col_t2:
            destinos = [s for s in sedes_disponibles if s != origen]
            destino = st.selectbox("Sede Destino:", destinos if destinos else ["No hay otras sedes"])
        with col_t3:
            prods = st.session_state.df[st.session_state.df['local'] == origen]['producto'].unique()
            prod_sel = st.selectbox("Producto a mover:", prods)

        cant_max = st.session_state.df[(st.session_state.df['local'] == origen) & (st.session_state.df['producto'] == prod_sel)]['cantidad'].values[0]
        cantidad = st.number_input(f"Cantidad (Disponible: {cant_max}):", min_value=1, max_value=int(cant_max))

        if st.button("Ejecutar Traslado"):
            # Lógica de resta en origen
            st.session_state.df.loc[(st.session_state.df['local'] == origen) & (st.session_state.df['producto'] == prod_sel), 'cantidad'] -= cantidad
            
            # Lógica de suma o creación en destino
            mask_dest = (st.session_state.df['local'] == destino) & (st.session_state.df['producto'] == prod_sel)
            if mask_dest.any():
                st.session_state.df.loc[mask_dest, 'cantidad'] += cantidad
            else:
                nuevo_registro = pd.DataFrame([{
                    'local': destino, 
                    'producto': prod_sel, 
                    'cantidad': cantidad, 
                    'ultima_actualizacion': datetime.now().strftime("%Y-%m-%d %H:%M")
                }])
                st.session_state.df = pd.concat([st.session_state.df, nuevo_registro], ignore_index=True)
            
            guardar_datos(st.session_state.df)
            st.success("Traslado realizado con éxito.")
            st.rerun()
    else:
        st.warning("No hay datos para realizar movimientos.")

# --- TAB 3: GESTIÓN DE PRODUCTOS ---
with tab3:
    st.subheader("Añadir o Editar Inventario")
    
    with st.form("nuevo_producto"):
        c1, c2, c3 = st.columns(3)
        nueva_sede = c1.text_input("Nombre de la Sede (Ej: Barranco):")
        nuevo_prod = c2.text_input("Nombre del Producto:")
        nueva_cant = c3.number_input("Cantidad Inicial:", min_value=0)
        
        submit = st.form_submit_button("Guardar en Inventario")
        
        if submit:
            if nueva_sede and nuevo_prod:
                # Si el producto ya existe en esa sede, sumamos
                mask = (st.session_state.df['local'] == nueva_sede.strip()) & (st.session_state.df['producto'] == nuevo_prod.strip())
                
                if mask.any():
                    st.session_state.df.loc[mask, 'cantidad'] += nueva_cant
                    st.info("Producto actualizado en la sede existente.")
                else:
                    nuevo_item = pd.DataFrame([{
                        'local': nueva_sede.strip(),
                        'producto': nuevo_prod.strip(),
                        'cantidad': nueva_cant,
                        'ultima_actualizacion': datetime.now().strftime("%Y-%m-%d %H:%M")
                    }])
                    st.session_state.df = pd.concat([st.session_state.df, nuevo_item], ignore_index=True)
                    st.success("Nuevo producto registrado.")
                
                guardar_datos(st.session_state.df)
                st.rerun()
            else:
                st.error("Por favor rellena los campos de Sede y Producto.")

    st.divider()
    if st.button("🗑️ Borrar todo el Inventario (Reset)"):
        st.session_state.df = crear_df_vacio()
        guardar_datos(st.session_state.df)
        st.warning("Se ha reiniciado el inventario.")
        st.rerun()
