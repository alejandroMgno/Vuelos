import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import io
import os
import urllib.parse
import re

# --- DIÁLOGO DE SEGURIDAD PARA ACCIONES RÁPIDAS ---
@st.dialog("🔐 AUTORIZACIÓN REQUERIDA")
def dialog_cambiar_estado(id_vuelo, nuevo_estado):
    st.markdown(f"Se cambiará el estado de este activo a: **{nuevo_estado}**")
    clave = st.text_input("Ingresa la clave de administrador para continuar:", type="password")
    
    if st.button("CONFIRMAR ACCIÓN", type="primary", use_container_width=True):
        if clave == "ADMIN123":  # <-- CONTRASEÑA MAESTRA AQUÍ
            conn = sqlite3.connect('logistics_v2.db')
            cursor = conn.cursor()
            cursor.execute("UPDATE vuelos SET Estado=? WHERE id=?", (nuevo_estado, id_vuelo))
            conn.commit()
            st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos WHERE deleted_at IS NULL", conn)
            conn.close()
            st.rerun()
        else:
            st.error("❌ Clave incorrecta. Operación denegada.")

# --- EXPORTADOR EXCEL ---
def generar_excel_inventario(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario_Activos')
    return output.getvalue()

# --- CONTENIDO DEL MODAL GESTIÓN ---
@st.dialog("GESTIÓN DE ACTIVO")
def modal_gestion(vuelo):
    llave_edicion = f"editando_{vuelo['id']}"
    if llave_edicion not in st.session_state:
        st.session_state[llave_edicion] = False

    st.markdown(f"### {vuelo['Pasajero']}")
    st.markdown(f"<code style='color:#00d4ff;'>Clave_de_Reserva: {vuelo['Clave_de_Reserva']} // ID_DB: {vuelo['id']}</code>", unsafe_allow_html=True)
    
    # Indicador de Canje
    boleto_ligado = vuelo.get('Boleto_Ligado', '')
    if pd.notna(boleto_ligado) and boleto_ligado != "":
        st.info(f"🔄 **ACTIVO PROVENIENTE DE CANJE:** Reutilizó el saldo del Clave_de_Reserva original **{boleto_ligado}**.")
    
    st.divider()
    esta_bloqueado = not st.session_state[llave_edicion]
    
    col1, col2 = st.columns(2)
    with col1:
        nuevo_pax = st.text_input("PASAJERO", value=vuelo['Pasajero'], disabled=esta_bloqueado, key=f"edit_pax_{vuelo['id']}")
        nuevo_pnr = st.text_input("Clave_de_Reserva", value=vuelo['Clave_de_Reserva'], disabled=esta_bloqueado, key=f"edit_pnr_{vuelo['id']}").upper()
        nuevo_ori = st.text_input("ORIGEN", value=vuelo['Origen'], disabled=esta_bloqueado, key=f"edit_ori_{vuelo['id']}").upper()
        nuevo_pais = st.text_input("PAIS", value=vuelo.get('Pais', 'N/A'), disabled=esta_bloqueado, key=f"edit_pais_{vuelo['id']}").upper()
        nuevo_aer = st.text_input("AEROLÍNEA", value=vuelo.get('Aerolinea', 'N/A'), disabled=esta_bloqueado, key=f"edit_aer_{vuelo['id']}").upper()
        nuevo_motivo = st.text_input("MOTIVO VIAJE", value=vuelo.get('Motivo', 'NO ESPECIFICADO'), disabled=esta_bloqueado, key=f"edit_mot_{vuelo['id']}").upper()
    
    with col2:
        nuevo_tel = st.text_input("WHATSAPP PASAJERO 🟢", value=vuelo.get('Telefono', ''), disabled=esta_bloqueado, key=f"edit_tel_{vuelo['id']}")
        nuevo_costo = st.number_input("VALOR (MX)", value=float(vuelo['Costo']), disabled=esta_bloqueado, key=f"edit_costo_{vuelo['id']}")
        fecha_dt = pd.to_datetime(vuelo['Fecha']).date()
        nueva_fecha = st.date_input("FECHA", value=fecha_dt, disabled=esta_bloqueado, key=f"edit_fecha_{vuelo['id']}")
        nuevo_des = st.text_input("DESTINO", value=vuelo['Destino'], disabled=esta_bloqueado, key=f"edit_des_{vuelo['id']}").upper()
        nuevo_nvv = st.text_input("NO. VUELO", value=vuelo.get('No_Vuelo', 'S/N'), disabled=esta_bloqueado, key=f"edit_nvv_{vuelo['id']}").upper()
        nuevo_aut = st.text_input("AUTORIZÓ", value=vuelo.get('Autoriza', 'PENDIENTE'), disabled=esta_bloqueado, key=f"edit_aut_{vuelo['id']}").upper()

    estados_posibles = ["Activo", "Abierto (Disponible)", "Cancelado", "Realizado", "Canjeado"]
    estado_actual = vuelo['Estado']
    if estado_actual not in estados_posibles: estados_posibles.append(estado_actual)

    nuevo_estado = st.selectbox("ESTADO DEL SISTEMA", estados_posibles, index=estados_posibles.index(estado_actual), key=f"edit_est_{vuelo['id']}", disabled=esta_bloqueado)

    # --- ZONA DE DOCUMENTOS ---
    st.markdown("---")
    st.markdown("#### 📎 PORTAFOLIO DE DOCUMENTOS")
    
    archivos_actuales = str(vuelo['Soporte']).split('|') if vuelo['Soporte'] else []
    archivos_validos = [f for f in archivos_actuales if os.path.exists(f)]
    
    if archivos_validos:
        cols_galeria = st.columns(4)
        for idx, ruta in enumerate(archivos_validos):
            with cols_galeria[idx % 4]:
                with st.container(border=True):
                    nombre_arch = os.path.basename(ruta)
                    ext = nombre_arch.split('.')[-1].lower()
                    if ext in ['jpg', 'jpeg', 'png']: st.image(ruta, use_container_width=True)
                    else: st.markdown(f"<div style='text-align:center; font-size:40px;'>📄</div>", unsafe_allow_html=True)
                    st.caption(nombre_arch[:15] + "...")
                    with open(ruta, "rb") as file:
                        st.download_button("⬇️", data=file, file_name=nombre_arch, key=f"dl_{vuelo['id']}_{idx}", use_container_width=True)
    else:
        st.info("No hay documentos adjuntos a este registro.")

    archivos_nuevos = st.file_uploader("Agregar documentos", type=['pdf', 'jpg', 'png'], accept_multiple_files=True, key=f"file_{vuelo['id']}", disabled=esta_bloqueado)
    
    # --- LÓGICA DE WHATSAPP ---
    if archivos_validos and nuevo_tel:
        tel_limpio = re.sub(r'\D', '', nuevo_tel)
        aerolinea_txt = f" por {nuevo_aer}" if nuevo_aer != "N/A" and nuevo_aer != "" else ""
        vuelo_txt = f" (Vuelo: {nuevo_nvv})" if nuevo_nvv != "S/N" else ""
        mensaje_wa = f"¡Hola {nuevo_pax}! ✈️\n\nTu gestión de viaje ha sido procesada con éxito.\n*Ruta:* {nuevo_ori} ➔ {nuevo_des}{aerolinea_txt}{vuelo_txt}\n*Clave_de_Reserva:* {nuevo_pnr}\n\nPor este medio te comparto tus documentos de viaje (Pase de abordar/Comprobantes). ¡Excelente viaje!"
        mensaje_codificado = urllib.parse.quote(mensaje_wa)
        url_whatsapp = f"https://wa.me/{tel_limpio}?text={mensaje_codificado}"
        
        st.markdown(f"""
            <a href="{url_whatsapp}" target="_blank" style="display: block; width: 100%; text-align: center; background-color: #25D366; color: white; padding: 10px; border-radius: 4px; text-decoration: none; font-weight: bold; margin-bottom: 10px;">
                🟢 ABRIR CHAT EN WHATSAPP
            </a>
        """, unsafe_allow_html=True)

    st.divider()
    
    c1, c2, c3, c4 = st.columns(4)

    def accionar_bloqueo(): st.session_state[llave_edicion] = False
    def accionar_desbloqueo():
        if st.session_state.get(f"pass_input_{vuelo['id']}", "") == "ADMIN123": 
            st.session_state[llave_edicion] = True
            st.session_state[f"err_pass_{vuelo['id']}"] = False
        else:
            st.session_state[f"err_pass_{vuelo['id']}"] = True

    if esta_bloqueado:
        menu_pass = c1.popover("🔓 EDITAR", use_container_width=True)
        menu_pass.text_input("Clave Admin", type="password", key=f"pass_input_{vuelo['id']}")
        menu_pass.button("Desbloquear", on_click=accionar_desbloqueo, use_container_width=True, key=f"btn_verify_{vuelo['id']}")
        if st.session_state.get(f"err_pass_{vuelo['id']}", False): menu_pass.error("❌ Clave incorrecta")
    else:
        c1.button("🔒 CANCELAR", on_click=accionar_bloqueo, use_container_width=True, key=f"loc_{vuelo['id']}")

    if c2.button("✂️ DIVIDIR", use_container_width=True, disabled=esta_bloqueado, key=f"spl_{vuelo['id']}"):
        costo_mitad = vuelo['Costo'] / 2
        conn = sqlite3.connect('logistics_v2.db')
        cursor = conn.cursor()
        cursor.execute("UPDATE vuelos SET Estado='Realizado', Costo=?, Pasajero=? WHERE id=?", (costo_mitad, f"{vuelo['Pasajero']} (IDA)", vuelo['id']))
        cursor.execute('''INSERT INTO vuelos (Pasajero, Origen, Destino, Estado, Costo, Clave_de_Reserva, Equipaje, Extra, Fecha, Soporte, Usuario, Hora, Pais, Telefono, Aerolinea, Boleto_Ligado, No_Vuelo, Motivo, Autoriza)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                       (f"{vuelo['Pasajero']} (VUELTA)", vuelo['Destino'], vuelo['Origen'], "Abierto (Disponible)", costo_mitad, vuelo['Clave_de_Reserva'], vuelo['Equipaje'], vuelo['Extra'], str(fecha_dt), vuelo['Soporte'], st.session_state.usuario['nombre'], datetime.now().strftime("%H:%M"), vuelo.get('Pais', 'N/A'), vuelo.get('Telefono', ''), vuelo.get('Aerolinea', 'N/A'), "", vuelo.get('No_Vuelo', 'S/N'), vuelo.get('Motivo', 'NO ESPECIFICADO'), vuelo.get('Autoriza', 'PENDIENTE')))
        conn.commit()
        st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos WHERE deleted_at IS NULL", conn)
        conn.close()
        st.rerun()

    if c3.button("🗑️ ELIMINAR", use_container_width=True, disabled=esta_bloqueado, key=f"del_{vuelo['id']}"):
        conn = sqlite3.connect('logistics_v2.db')
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("UPDATE vuelos SET deleted_at=? WHERE id=?", (timestamp, vuelo['id']))
        conn.commit()
        st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos WHERE deleted_at IS NULL", conn)
        conn.close()
        st.session_state[llave_edicion] = False
        st.rerun()

    if c4.button("GUARDAR", type="primary", use_container_width=True, disabled=esta_bloqueado, key=f"sav_{vuelo['id']}"):
        rutas_finales = archivos_validos.copy()
        if archivos_nuevos:
            if not os.path.exists("attachments"): os.makedirs("attachments")
            for archivo in archivos_nuevos:
                ruta_nueva = f"attachments/{vuelo['id']}_{archivo.name}"
                with open(ruta_nueva, "wb") as f: f.write(archivo.getbuffer())
                rutas_finales.append(ruta_nueva)
                
        cadena_soportes = "|".join(rutas_finales)

        conn = sqlite3.connect('logistics_v2.db')
        cursor = conn.cursor()
        cursor.execute('''UPDATE vuelos SET 
            Pasajero=?, Clave_de_Reserva=?, Costo=?, Estado=?, Fecha=?, Origen=?, Destino=?, 
            Soporte=?, Pais=?, Telefono=?, Aerolinea=?, No_Vuelo=?, Motivo=?, Autoriza=?
            WHERE id=?''',
            (nuevo_pax, nuevo_pnr, nuevo_costo, nuevo_estado, str(nueva_fecha), 
             nuevo_ori, nuevo_des, cadena_soportes, nuevo_pais, nuevo_tel, 
             nuevo_aer, nuevo_nvv, nuevo_motivo, nuevo_aut, vuelo['id']))
        conn.commit()
        
        st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos WHERE deleted_at IS NULL", conn)
        conn.close()
        st.session_state[llave_edicion] = False
        st.rerun()

def render():
    st.markdown("<h4 style='letter-spacing:2px; font-weight:300;'>INVENTARIO DE VUELOS</h4>", unsafe_allow_html=True)
    
    df = st.session_state.db_vuelos.copy()
    df['Fecha_DT'] = pd.to_datetime(df['Fecha']).dt.date

    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 2, 1.5])
        f_ini = c1.date_input("DESDE", value=date(2024, 1, 1), key="inv_f_ini")
        f_fin = c2.date_input("HASTA", value=date(2026, 12, 31), key="inv_f_fin")
        df_f = df[(df['Fecha_DT'] >= f_ini) & (df['Fecha_DT'] <= f_fin)].copy()
        
        excel = generar_excel_inventario(df_f.drop(columns=['Fecha_DT']))
        c3.markdown("<br>", unsafe_allow_html=True)
        c3.download_button("📊 EXCEL", data=excel, file_name=f"Inventario_{f_ini}.xlsx", key="btn_exp_inv", use_container_width=True)

    busqueda = st.text_input("BUSCAR ACTIVO", placeholder="PASAJERO / Clave_de_Reserva / AEROLÍNEA / NO. VUELO...", key="inv_search").upper()
    
    st.markdown("""
        <div style='display:grid; grid-template-columns: 2fr 1fr 1fr 1.2fr 1fr 1.8fr; padding: 10px; border-bottom: 1px solid #1A1A1A; color: #444; font-size: 10px; letter-spacing: 2px;'>
            <div>PASAJERO / Clave_de_Reserva</div><div>FECHA</div><div>RUTA</div><div>AEROLÍNEA</div><div>ESTADO</div><div>ACCIÓN</div>
        </div>
    """, unsafe_allow_html=True)

    if df_f.empty:
        st.info("No hay registros en este rango.")
    else:
        for _, fila in df_f.iterrows():
            aerolinea_str = str(fila.get('Aerolinea', 'N/A'))
            nvv_str = str(fila.get('No_Vuelo', 'S/N'))
            
            # Búsqueda ampliada (ahora busca también por número de vuelo)
            busqueda_condicion = not busqueda or (
                busqueda in str(fila['Pasajero']).upper() or 
                busqueda in str(fila['Clave_de_Reserva']).upper() or 
                busqueda in aerolinea_str.upper() or
                busqueda in nvv_str.upper()
            )
            
            if busqueda_condicion:
                if fila['Estado'] == "Activo": color = "#00d4ff"
                elif fila['Estado'] == "Cancelado": color = "#FF3B30"
                elif fila['Estado'] == "Realizado": color = "#4CD964"
                elif fila['Estado'] == "Canjeado": color = "#888888"
                else: color = "#FFCC00" 
                
                boleto_ligado_str = str(fila.get('Boleto_Ligado', ''))
                etiqueta_canje = f"<br><span style='background-color:#332b00; color:#FFCC00; font-size:9px; padding:2px 4px; border-radius:3px;'>🔄 CANJE: {boleto_ligado_str}</span>" if boleto_ligado_str and boleto_ligado_str not in ["nan", "None", ""] else ""
                
                c = st.columns([2, 1, 1, 1.2, 1, 1.8])
                c[0].markdown(f"**{fila['Pasajero']}**<br><small>{fila['Clave_de_Reserva']}</small>{etiqueta_canje}", unsafe_allow_html=True)
                c[1].markdown(f"<div style='margin-top:10px;'>{fila['Fecha']}</div>", unsafe_allow_html=True)
                c[2].markdown(f"<div style='margin-top:10px;'>{fila['Origen']}→{fila['Destino']}</div>", unsafe_allow_html=True)
                
                aerolinea_display = aerolinea_str if aerolinea_str != "N/A" else "-"
                vuelo_display = f"<br><small>{nvv_str}</small>" if nvv_str != "S/N" else ""
                c[3].markdown(f"<div style='margin-top:2px; font-weight:600;'>{aerolinea_display}{vuelo_display}</div>", unsafe_allow_html=True)
                
                c[4].markdown(f"<div style='margin-top:10px; color:{color};'>● {fila['Estado'].upper()}</div>", unsafe_allow_html=True)
                
                # Botonera
                b_gest, b_real, b_canc, b_abri = c[5].columns([2.5, 1, 1, 1])
                
                if b_gest.button("GESTIONAR", key=f"inv_btn_{fila['id']}"):
                    modal_gestion(fila)
                    
                if b_real.button("✅", key=f"btn_real_{fila['id']}", help="Marcar como Realizado"):
                    dialog_cambiar_estado(fila['id'], "Realizado")
                    
                if b_canc.button("❌", key=f"btn_canc_{fila['id']}", help="Marcar como Cancelado"):
                    dialog_cambiar_estado(fila['id'], "Cancelado")
                    
                if b_abri.button("🔓", key=f"btn_abri_{fila['id']}", help="Marcar como Abierto (Disponible)"):
                    dialog_cambiar_estado(fila['id'], "Abierto (Disponible)")