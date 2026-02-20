import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import io
import os

# --- EXPORTADOR EXCEL ---
def generar_excel_inventario(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario_Activos')
    return output.getvalue()

# --- CONTENIDO DEL MODAL ---
@st.fragment
def contenido_modal(vuelo):
    llave_edicion = f"editando_{vuelo['id']}"
    if llave_edicion not in st.session_state:
        st.session_state[llave_edicion] = False

    st.markdown(f"### {vuelo['Pasajero']}")
    st.markdown(f"<code style='color:#00d4ff;'>PNR: {vuelo['PNR']} // ID_DB: {vuelo['id']}</code>", unsafe_allow_html=True)
    st.divider()

    esta_bloqueado = not st.session_state[llave_edicion]
    
    col1, col2 = st.columns(2)
    with col1:
        nuevo_pax = st.text_input("PASAJERO", value=vuelo['Pasajero'], disabled=esta_bloqueado, key=f"edit_pax_{vuelo['id']}")
        nuevo_pnr = st.text_input("PNR", value=vuelo['PNR'], disabled=esta_bloqueado, key=f"edit_pnr_{vuelo['id']}").upper()
        nuevo_ori = st.text_input("ORIGEN", value=vuelo['Origen'], disabled=esta_bloqueado, key=f"edit_ori_{vuelo['id']}").upper()
    with col2:
        nuevo_costo = st.number_input("VALOR (USD)", value=float(vuelo['Costo']), disabled=esta_bloqueado, key=f"edit_costo_{vuelo['id']}")
        # Convertir fecha de texto a objeto date para el input
        fecha_dt = pd.to_datetime(vuelo['Fecha']).date()
        nueva_fecha = st.date_input("FECHA", value=fecha_dt, disabled=esta_bloqueado, key=f"edit_fecha_{vuelo['id']}")
        nuevo_des = st.text_input("DESTINO", value=vuelo['Destino'], disabled=esta_bloqueado, key=f"edit_des_{vuelo['id']}").upper()

    nuevo_estado = st.selectbox("ESTADO_DEL_SISTEMA", 
                                ["Activo", "Abierto (Disponible)", "Cancelado", "Realizado"], 
                                index=["Activo", "Abierto (Disponible)", "Cancelado", "Realizado"].index(vuelo['Estado']),
                                key=f"edit_est_{vuelo['id']}", disabled=esta_bloqueado)

    # --- ZONA DE ARCHIVOS ---
    st.markdown("---")
    archivo_nuevo = st.file_uploader("Actualizar soporte", type=['pdf', 'jpg', 'png'], key=f"file_{vuelo['id']}", disabled=esta_bloqueado)
    
    st.divider()
    c1, c2, c3 = st.columns(3)

    # 1. Bloqueo/Desbloqueo
    if esta_bloqueado:
        if c1.button("🔓 DESBLOQUEAR", use_container_width=True, key=f"unl_{vuelo['id']}"):
            st.session_state[llave_edicion] = True
            st.rerun()
    else:
        if c1.button("🔒 BLOQUEAR", use_container_width=True, key=f"loc_{vuelo['id']}"):
            st.session_state[llave_edicion] = False
            st.rerun()

    # 2. Función de División (✂️ SPLIT) con SQLITE
    if c2.button("✂️ DIVIDIR", use_container_width=True, key=f"spl_{vuelo['id']}"):
        costo_mitad = vuelo['Costo'] / 2
        conn = sqlite3.connect('logistics_v2.db')
        cursor = conn.cursor()
        
        # Actualizar el actual (IDA)
        cursor.execute("UPDATE vuelos SET Estado='Realizado', Costo=?, Pasajero=? WHERE id=?", 
                       (costo_mitad, f"{vuelo['Pasajero']} (IDA)", vuelo['id']))
        
        # Insertar el nuevo (VUELTA)
        cursor.execute('''INSERT INTO vuelos (Pasajero, Origen, Destino, Estado, Costo, PNR, Equipaje, Extra, Fecha, Soporte, Usuario, Hora)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (f"{vuelo['Pasajero']} (VUELTA)", vuelo['Destino'], vuelo['Origen'], "Abierto (Disponible)", 
                        costo_mitad, vuelo['PNR'], vuelo['Equipaje'], vuelo['Extra'], vuelo['Fecha'], vuelo['Soporte'], 
                        st.session_state.usuario['nombre'], datetime.now().strftime("%H:%M")))
        
        conn.commit()
        conn.close()
        st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos", sqlite3.connect('logistics_v2.db'))
        st.rerun()

    # 3. Guardar cambios en SQLITE
    if c3.button("GUARDAR", type="primary", use_container_width=True, disabled=esta_bloqueado, key=f"sav_{vuelo['id']}"):
        ruta_archivo = vuelo['Soporte']
        if archivo_nuevo:
            if not os.path.exists("attachments"): os.makedirs("attachments")
            ruta_archivo = f"attachments/{vuelo['id']}_{archivo_nuevo.name}"
            with open(ruta_archivo, "wb") as f: f.write(archivo_nuevo.getbuffer())

        conn = sqlite3.connect('logistics_v2.db')
        cursor = conn.cursor()
        cursor.execute('''UPDATE vuelos SET Pasajero=?, PNR=?, Costo=?, Estado=?, Fecha=?, Origen=?, Destino=?, Soporte=? WHERE id=?''',
                       (nuevo_pax, nuevo_pnr, nuevo_costo, nuevo_estado, str(nueva_fecha), nuevo_ori, nuevo_des, ruta_archivo, vuelo['id']))
        conn.commit()
        conn.close()
        
        st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos", sqlite3.connect('logistics_v2.db'))
        st.session_state[llave_edicion] = False
        st.success("SINCRO EXITOSA")
        st.rerun()

@st.dialog("GESTIÓN_DE_ACTIVO")
def modal_gestion(vuelo):
    contenido_modal(vuelo)

def render():
    st.markdown("<h4 style='letter-spacing:2px; font-weight:300;'>📦 INVENTARIO_DE_ACTIVOS</h4>", unsafe_allow_html=True)
    
    # RECARGA DESDE DB PARA MOSTRAR LO NUEVO
    conn = sqlite3.connect('logistics_v2.db')
    df = pd.read_sql_query("SELECT * FROM vuelos", conn)
    conn.close()
    
    # Normalizar fechas para el filtro
    df['Fecha'] = pd.to_datetime(df['Fecha']).dt.date

    # --- PANEL DE FILTROS ---
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 1.5])
        f_ini = c1.date_input("DESDE", value=date(2024, 1, 1), key="inv_f_ini")
        f_fin = c2.date_input("HASTA", value=date(2026, 12, 31), key="inv_f_fin")
        
        df_f = df[(df['Fecha'] >= f_ini) & (df['Fecha'] <= f_fin)].copy()
        
        excel = generar_excel_inventario(df_f)
        c3.markdown("<br>", unsafe_allow_html=True)
        c3.download_button("📊 EXCEL", data=excel, file_name=f"Inventario_{f_ini}.xlsx", key="btn_exp_inv", use_container_width=True)

    busqueda = st.text_input("BUSCAR_ACTIVO", placeholder="PASAJERO / PNR...", key="inv_search").upper()
    
    # --- TABLA ---
    st.markdown("""
        <div style='display:grid; grid-template-columns: 2fr 1fr 1fr 1fr 1fr; padding: 10px; border-bottom: 1px solid #1A1A1A; color: #444; font-size: 10px; letter-spacing: 2px;'>
            <div>PASAJERO / PNR</div><div>FECHA</div><div>RUTA</div><div>ESTADO</div><div>ACCIÓN</div>
        </div>
    """, unsafe_allow_html=True)

    if df_f.empty:
        st.info("No hay registros en este rango.")
    else:
        for _, fila in df_f.iterrows():
            if not busqueda or (busqueda in str(fila['Pasajero']).upper() or busqueda in str(fila['PNR']).upper()):
                color = "#00d4ff" if fila['Estado'] == "Activo" else "#FF3B30" if fila['Estado'] == "Cancelado" else "#4CD964" if fila['Estado'] == "Realizado" else "#FFCC00"
                
                c = st.columns([2, 1, 1, 1, 1])
                c[0].markdown(f"**{fila['Pasajero']}**<br><small>{fila['PNR']}</small>", unsafe_allow_html=True)
                c[1].markdown(f"<div style='margin-top:10px;'>{fila['Fecha']}</div>", unsafe_allow_html=True)
                c[2].markdown(f"<div style='margin-top:10px;'>{fila['Origen']}→{fila['Destino']}</div>", unsafe_allow_html=True)
                c[3].markdown(f"<div style='margin-top:10px; color:{color};'>● {fila['Estado'].upper()}</div>", unsafe_allow_html=True)
                
                if c[4].button("GESTIONAR", key=f"inv_btn_{fila['id']}"):
                    modal_gestion(fila)