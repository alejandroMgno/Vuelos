import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import os
import time

def render():
    st.markdown("<h4 style='letter-spacing:3px; font-weight:300; color:#00d4ff;'>ENTRADA DE NUEVO VUELO</h4>", unsafe_allow_html=True)
    st.info("💡 **Tip de búsqueda:** Da clic en las cajas que tienen la lupa (🔍) y empieza a teclear para filtrar las opciones al instante.")
    
    # --- SISTEMA DE RESETEO ---
    if 'reg_key' not in st.session_state: 
        st.session_state['reg_key'] = 0
    rk = st.session_state['reg_key']

    df = st.session_state.db_vuelos

    # --- PREVENCIÓN DE ERRORES DE COLUMNAS ---
    if 'Motivo' not in df.columns: df['Motivo'] = 'NO ESPECIFICADO'
    if 'Autoriza' not in df.columns: df['Autoriza'] = 'PENDIENTE'

    # --- EXTRACCIÓN DE CATÁLOGOS (Bases de datos en vivo) ---
    pax_conocidos = [str(x).upper().strip() for x in df['Pasajero'].dropna().unique() if str(x).strip()]
    rutas_conocidas = list(set([str(x).upper().strip() for x in df['Origen'].dropna().unique() if str(x).strip()] + 
                               [str(x).upper().strip() for x in df['Destino'].dropna().unique() if str(x).strip()]))
    aero_conocidas = [str(x).upper().strip() for x in df['Aerolinea'].dropna().unique() if str(x).strip() and x != 'N/A']

    # --- SISTEMA DE CANJE (BOLETOS ABIERTOS) ---
    df_abiertos = df[df['Estado'] == 'Abierto (Disponible)']
    id_abierto_seleccionado = None
    pnr_ligado = ""

    with st.container(border=True):
        usar_saldo = st.toggle("🎟️ REUTILIZAR BOLETO ABIERTO (CANJE)", help="Vincula este nuevo vuelo a un saldo a favor anterior.", key=f"tgl_{rk}")
        if usar_saldo:
            if not df_abiertos.empty:
                opciones = df_abiertos.apply(lambda x: f"ID: {x['id']} | Clave_de_Reserva: {x['Clave_de_Reserva']} | {x['Pasajero']} | ${x['Costo']}", axis=1).tolist()
                seleccion = st.selectbox("Selecciona el boleto a canjear:", opciones, key=f"sel_canje_{rk}")
                id_abierto_seleccionado = int(seleccion.split(" | ")[0].replace("ID: ", ""))
                pnr_ligado = seleccion.split(" | ")[1].replace("Clave_de_Reserva: ", "")
                st.success(f"Vinculado exitosamente al boleto: {pnr_ligado}")
            else:
                st.warning("No hay boletos abiertos disponibles.")

    st.markdown("---")
    
    # ==========================================
    # FORMULARIO DE CAPTURA 
    # ==========================================
    
    # FILA 1: Datos del Pasajero
    c1, c2, c3 = st.columns([2, 1, 1])
    
    sel_pax = c1.selectbox("🔍 PASAJERO", ["➕ REGISTRAR NUEVO..."] + sorted(pax_conocidos), key=f"sel_pax_{rk}")
    nom = c1.text_input("ESCRIBE NUEVO PASAJERO", key=f"new_pax_{rk}").upper() if sel_pax == "➕ REGISTRAR NUEVO..." else sel_pax

    pnr = c2.text_input("🎫 Clave_de_Reserva", placeholder="Ej: XJ3K9P", key=f"pnr_{rk}").upper()
    tel = c3.text_input("🟢 WHATSAPP", placeholder="Ej: 528100000000", key=f"tel_{rk}")
    
    # FILA 2: Rutas y Fechas
    c4, c5, c6 = st.columns([2, 2, 1])
    
    sel_ori = c4.selectbox("🔍 ORIGEN", ["➕ NUEVO ORIGEN..."] + sorted(rutas_conocidas), key=f"sel_ori_{rk}")
    ori = c4.text_input("ESCRIBE ORIGEN", key=f"new_ori_{rk}").upper() if sel_ori == "➕ NUEVO ORIGEN..." else sel_ori
    
    sel_des = c5.selectbox("🔍 DESTINO", ["➕ NUEVO DESTINO..."] + sorted(rutas_conocidas), key=f"sel_des_{rk}")
    des = c5.text_input("ESCRIBE DESTINO", key=f"new_des_{rk}").upper() if sel_des == "➕ NUEVO DESTINO..." else sel_des
    
    fec = c6.date_input("📅 FECHA", value=date.today(), key=f"fec_{rk}")
    
    # FILA 3: Operación de Vuelo
    c7, c8, c9, c10 = st.columns([2, 1, 1, 1])
    
    sel_aer = c7.selectbox("🔍 AEROLÍNEA", ["➕ NUEVA AEROLÍNEA..."] + sorted(aero_conocidas), key=f"sel_aer_{rk}")
    aer = c7.text_input("ESCRIBE AEROLÍNEA", key=f"new_aer_{rk}").upper() if sel_aer == "➕ NUEVA AEROLÍNEA..." else sel_aer
    
    nvv = c8.text_input("🔢 NO. VUELO", placeholder="AMX001", key=f"nvv_{rk}").upper()
    pais = c9.selectbox("🌎 PAÍS", ["MÉXICO", "ESTADOS UNIDOS", "ESPAÑA", "COLOMBIA", "ARGENTINA", "CHILE", "PANAMÁ", "OTRO"], key=f"pais_{rk}")
    equ = c10.selectbox("🧳 EQUIPAJE", ["MANO", "DOCUMENTADO", "COMPLETO"], key=f"equ_{rk}")
    
    # FILA 4: Control Corporativo (TEXTO LIBRE)
    st.markdown("---")
    c_mot, c_aut = st.columns(2)
    
    mot = c_mot.text_input("🎯 MOTIVO DEL VIAJE", placeholder="Ej: Reunión Anual / Capacitación", key=f"mot_{rk}").upper()
    aut = c_aut.text_input("👤 QUIÉN AUTORIZA", placeholder="Ej: Director Operativo / RH", key=f"aut_{rk}").upper()

    # FILA 5: Finanzas y Documentos
    st.markdown("---")
    c11, c12, c13, c14 = st.columns([1, 1, 1, 2])
    cos = c11.number_input("💲COSTO (MX)", min_value=0.0, step=0.01, key=f"cos_{rk}")
    ext = c12.selectbox("EXTRAS", ["NO", "SÍ"], key=f"ext_{rk}")
    est = c13.selectbox("ESTADO", ["Activo", "Abierto (Disponible)"], key=f"est_{rk}")
    archivos = c14.file_uploader("📄 DOCUMENTOS", type=['pdf', 'jpg', 'png'], accept_multiple_files=True, key=f"file_{rk}")
    
    # --- BOTÓN DE GUARDADO ---
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 CONFIRMAR Y GUARDAR REGISTRO", use_container_width=True, type="primary"):
        
        # Validación
        if not nom or not nom.strip():
            st.error("❌ ERROR: Debes seleccionar o escribir el nombre del pasajero.")
            return
        if not Clave_de_Reserva or not Clave_de_Reserva.strip():
            st.error("❌ ERROR: El código de reserva (Clave_de_Reserva) es obligatorio.")
            return

        # Manejo de archivos
        rutas_finales = []
        if archivos:
            if not os.path.exists("attachments"): os.makedirs("attachments")
            for archivo in archivos:
                nombre_archivo = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{archivo.name}"
                ruta_final = os.path.join("attachments", nombre_archivo)
                with open(ruta_final, "wb") as f:
                    f.write(archivo.getbuffer())
                rutas_finales.append(ruta_final)
        cadena_soportes = "|".join(rutas_finales)

        # Inserción en SQLite
        try:
            conn = sqlite3.connect('logistics_v2.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO vuelos (
                    Pasajero, Origen, Destino, Estado, Costo, Clave_de_Reserva, 
                    Equipaje, Extra, Fecha, Pais, Soporte, Usuario, Hora, 
                    Telefono, Aerolinea, Boleto_Ligado, No_Vuelo, Motivo, Autoriza
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                nom.strip(), ori.strip(), des.strip(), est, cos, Clave_de_Reserva.strip(), 
                equ, ext, str(fec), pais, cadena_soportes, 
                st.session_state.usuario['nombre'], datetime.now().strftime("%H:%M"), 
                tel.strip(), aer.strip(), pnr_ligado, nvv.strip(),
                mot.strip() if mot else "NO ESPECIFICADO",
                aut.strip() if aut else "PENDIENTE"
            ))
            
            # Actualizar boleto viejo si hubo canje
            if usar_saldo and id_abierto_seleccionado:
                cursor.execute("UPDATE vuelos SET Estado='Canjeado' WHERE id=?", (id_abierto_seleccionado,))
            
            conn.commit()
            st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos WHERE deleted_at IS NULL", conn)
            conn.close()

            st.toast(f"🛫 Registro de '{Clave_de_Reserva}' guardado exitosamente", icon="✅")
            
            # Limpiar formulario
            st.session_state['reg_key'] += 1 
            time.sleep(1) 
            st.rerun()
            
        except Exception as e:
            st.error(f"ERROR AL GUARDAR EN BASE DE DATOS: {e}")