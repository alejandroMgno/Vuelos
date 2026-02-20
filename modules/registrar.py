import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import os

def render():
    st.markdown("<h4 style='letter-spacing:3px; font-weight:300;'>ENTRADA_DE_NUEVO_VUELO</h4>", unsafe_allow_html=True)
    
    with st.form("formulario_entrada", clear_on_submit=True):
        # Fila 1: Datos Personales y Financieros
        c1, c2, c3 = st.columns(3)
        nom = c1.text_input("NOMBRE_COMPLETO", placeholder="NOMBRE DEL PASAJERO").upper()
        pnr = c2.text_input("CÓDIGO_RESERVA_PNR", placeholder="EJ: XJ3K9P").upper()
        cos = c3.number_input("VALOR_DEL_COSTO (USD)", min_value=0.0, step=0.01)
        
        # Fila 2: Ruta y Fecha
        c4, c5, c6 = st.columns(3)
        ori = c4.text_input("ORIGEN_IATA", placeholder="EJ: MEX").upper()
        des = c5.text_input("DESTINO_IATA", placeholder="EJ: MAD").upper()
        fec = c6.date_input("FECHA_DEL_VUELO", value=date.today())
        
        # Fila 3: País y Detalles Logísticos
        c7, c8, c9 = st.columns(3)
        pais = c7.selectbox("PAÍS_DE_OPERACIÓN", [
            "MÉXICO", "ESTADOS UNIDOS", "ESPAÑA", "COLOMBIA", 
            "ARGENTINA", "CHILE", "PANAMÁ", "OTRO"
        ])
        equ = c8.selectbox("TIPO_DE_EQUIPAJE", ["MANO", "DOCUMENTADO", "COMPLETO"])
        ext = c9.selectbox("SERVICIOS_EXTRAS", ["NO", "SÍ"])
        
        # Fila 4: Estado Inicial y Soporte Digital
        st.markdown("---")
        col_file1, col_file2 = st.columns([1, 2])
        est = col_file1.selectbox("ESTADO_INICIAL_DEL_ACTIVO", ["Activo", "Abierto (Disponible)"])
        
        archivo = col_file2.file_uploader("📄 SUBIR_SOPORTE_DIGITAL (PDF, JPG, PNG)", type=['pdf', 'jpg', 'png'])
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.form_submit_button("CONFIRMAR_Y_GUARDAR_DATOS", use_container_width=True):
            if nom and pnr:
                # 1. Manejo físico del archivo
                ruta_final = ""
                if archivo is not None:
                    if not os.path.exists("attachments"):
                        os.makedirs("attachments")
                    
                    # Generamos un nombre único usando timestamp para evitar duplicados
                    nombre_archivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{archivo.name}"
                    ruta_final = os.path.join("attachments", nombre_archivo)
                    
                    with open(ruta_final, "wb") as f:
                        f.write(archivo.getbuffer())

                # 2. GUARDADO EN SQLITE (Persistencia Real)
                try:
                    conn = sqlite3.connect('logistics_v2.db')
                    cursor = conn.cursor()
                    
                    cursor.execute('''
                        INSERT INTO vuelos (
                            Pasajero, Origen, Destino, Estado, Costo, PNR, 
                            Equipaje, Extra, Fecha, Pais, Soporte, Usuario, Hora
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        nom, ori, des, est, cos, pnr, 
                        equ, ext, str(fec), pais, ruta_final, 
                        st.session_state.usuario['nombre'], 
                        datetime.now().strftime("%H:%M")
                    ))
                    
                    conn.commit()
                    nuevo_id = cursor.lastrowid # Obtenemos el ID generado por SQLite
                    conn.close()

                    # 3. ACTUALIZAR SESSION STATE (Sincronización con Inventario)
                    # Esto garantiza que al cambiar de pestaña el nuevo registro ya esté ahí
                    conn = sqlite3.connect('logistics_v2.db')
                    st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos", conn)
                    conn.close()

                    # 4. Feedback al usuario
                    st.success(f"ÉXITO: ACTIVO REGISTRADO EN BASE DE DATOS BAJO EL ID {nuevo_id}")
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"ERROR AL GUARDAR EN BASE DE DATOS: {e}")
            else:
                st.error("ERROR CRÍTICO: El NOMBRE y el PNR son campos obligatorios.")