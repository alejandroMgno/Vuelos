import streamlit as st
import pandas as pd
from datetime import datetime, date
import sqlite3
import os
import time
import pdfplumber
import google.generativeai as genai
import json
import PyPDF2
from io import BytesIO

# --- FUNCIONES TÉCNICAS (IA Y PDF) ---
def obtener_config(clave):
    try:
        conn = sqlite3.connect('logistics_v2.db')
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else ""
    except: return ""

def extraer_texto_pdf(archivos):
    texto_total = ""
    for archivo in archivos:
        try:
            with pdfplumber.open(archivo) as pdf:
                for pagina in pdf.pages:
                    texto_total += (pagina.extract_text() or "") + "\n"
        except: pass
    return texto_total

def unir_archivos_en_pdf(lista_archivos):
    merger = PyPDF2.PdfMerger()
    for archivo in lista_archivos:
        archivo.seek(0)
        merger.append(archivo)
    output = BytesIO()
    merger.write(output)
    merger.close()
    return output.getvalue()

def procesar_con_ia(texto):
    try:
        api_key = st.secrets.get("GEMINI_API_KEY") or obtener_config("gemini_api_key")
        if not api_key: return None
        genai.configure(api_key=api_key)
        
        # Selección dinámica de modelo para evitar Error 404
        modelo_final = "models/gemini-1.5-flash"
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name:
                    modelo_final = m.name
                    break
        
        model = genai.GenerativeModel(modelo_final)
        
        # PROMPT MEJORADO PARA MÚLTIPLES PASAJEROS Y FECHAS
        prompt = f"""
            Extrae los datos de viaje del siguiente texto y entrégalos en un JSON estricto.

            ### ESTRUCTURA JSON OBLIGATORIA:
            {{
            "pasajeros": ["Nombre completo 1", "Nombre completo 2"], 
            "pnr": "Código de 6 caracteres",
            "origen": "Ciudad origen",
            "destino": "Ciudad destino",
            "aerolinea": "Nombre aerolínea",
            "fecha_salida": "YYYY-MM-DD",
            "fecha_regreso": "YYYY-MM-DD",
            "costo": 0.0,
            "no_vuelo": "Número de vuelo",
            "autoriza": "Persona que aprueba",
            "motivo": "Razón del viaje"
            }}

            ### REGLAS DE ORO:
            1. "pasajeros" DEBE ser una lista (array) de nombres, incluso si es solo una persona (ej: ["Juan Perez"]).
            2. FECHAS: Identifica el año principal del documento (ej. 2026). Si el mes viene en palabras, conviértelo a número. Formato final: YYYY-MM-DD.
            3. Si no encuentras una fecha de regreso clara o es vuelo "Sencillo", deja "fecha_regreso" como "".
            4. El costo debe ser un número decimal, el valor total a pagar (busca en la Factura si existe).
            5. Si hay varios archivos mezclados, únelos lógicamente usando el PNR como guía.

            Texto a analizar:
            {texto}
            """
        response = model.generate_content(prompt)
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        datos = json.loads(res_text)
        
        # Si la IA envuelve el JSON en una lista, extraemos el primer elemento
        if isinstance(datos, list) and len(datos) > 0: datos = datos[0]
        return datos
    except Exception as e:
        st.error(f"Error IA: {e}")
        return None

def render():
    st.markdown("<h4 style='letter-spacing:3px; font-weight:300; color:#00d4ff;'>ENTRADA DE NUEVO VUELO</h4>", unsafe_allow_html=True)
    st.info("💡 **Tip de búsqueda:** Da clic en las cajas que tienen la lupa (🔍) y empieza a teclear para filtrar las opciones al instante.")
    
    if 'reg_key' not in st.session_state: st.session_state['reg_key'] = 0
    rk = st.session_state['reg_key']
    
    # Aseguramos que el df existe en el session_state (si no, creamos uno vacío para evitar errores de renderizado)
    if 'db_vuelos' not in st.session_state:
        st.session_state.db_vuelos = pd.DataFrame(columns=['Pasajero', 'Origen', 'Destino', 'Aerolinea', 'Estado', 'Costo', 'PNR', 'id'])
    df = st.session_state.db_vuelos

    # --- ZONA DE ASISTENTE IA (Pre-llenado) ---
    with st.expander("🤖 ASISTENTE IA: ESCANEAR Y UNIFICAR DOCUMENTOS", expanded=True):
        c_ia1, c_ia2 = st.columns([3, 1])
        archivos_ia = c_ia1.file_uploader("Sube Confirmación, Factura y Correo (PDF)", type=['pdf'], accept_multiple_files=True, key=f"ia_files_{rk}")
        if c_ia2.button("🪄 PROCESAR IA", use_container_width=True):
            if archivos_ia:
                with st.spinner("La IA está leyendo y procesando los documentos..."):
                    texto = extraer_texto_pdf(archivos_ia)
                    datos = procesar_con_ia(texto)
                    if datos:
                        # 1. Unir nombres si hay varios
                        nombres = datos.get('pasajeros', [])
                        nombres_str = ", ".join(nombres).upper() if isinstance(nombres, list) else str(datos.get('pasajero', '')).upper()
                        
                        # 2. Inyectar datos de texto y numéricos al session_state
                        st.session_state[f"pax_text_{rk}"] = nombres_str
                        st.session_state[f"pnr_{rk}"] = str(datos.get('pnr', '')).upper()
                        st.session_state[f"ori_text_{rk}"] = str(datos.get('origen', '')).upper()
                        st.session_state[f"des_text_{rk}"] = str(datos.get('destino', '')).upper()
                        st.session_state[f"aer_text_{rk}"] = str(datos.get('aerolinea', '')).upper()
                        st.session_state[f"nvv_{rk}"] = str(datos.get('no_vuelo', '')).upper()
                        st.session_state[f"mot_{rk}"] = str(datos.get('motivo', '')).upper()
                        st.session_state[f"aut_{rk}"] = str(datos.get('autoriza', '')).upper()
                        st.session_state[f"cos_{rk}"] = float(datos.get('costo', 0.0))
                        
                        # 3. INYECCIÓN DE FECHAS COMO OBJETOS DATETIME (Solución al Problema 1)
                        try:
                            f_sal_str = datos.get('fecha_salida', '')
                            if f_sal_str:
                                st.session_state[f"fec_{rk}"] = datetime.strptime(f_sal_str, '%Y-%m-%d').date()
                        except Exception: pass
                        
                        try:
                            f_reg_str = datos.get('fecha_regreso', '')
                            if f_reg_str:
                                st.session_state[f"fec_reg_{rk}"] = datetime.strptime(f_reg_str, '%Y-%m-%d').date()
                            else:
                                st.session_state[f"fec_reg_{rk}"] = None
                        except Exception: pass

                        st.success("¡Datos inyectados con éxito! Revisa el formulario abajo.")
                        time.sleep(0.5)
                        st.rerun()

    # --- PREVENCIÓN DE ERRORES DE COLUMNAS ---
    if 'Motivo' not in df.columns: df['Motivo'] = 'NO ESPECIFICADO'
    if 'Autoriza' not in df.columns: df['Autoriza'] = 'PENDIENTE'

    # --- CATÁLOGOS ---
    rutas_conocidas = list(set([str(x).upper().strip() for x in df['Origen'].dropna().unique() if str(x).strip()] + 
                               [str(x).upper().strip() for x in df['Destino'].dropna().unique() if str(x).strip()]))
    aero_conocidas = [str(x).upper().strip() for x in df['Aerolinea'].dropna().unique() if str(x).strip() and x != 'N/A']

    # --- SISTEMA DE CANJE ---
    df_abiertos = df[df['Estado'] == 'Abierto (Disponible)'] if 'Estado' in df.columns else pd.DataFrame()
    id_abierto_seleccionado = None
    pnr_ligado = ""
    with st.container(border=True):
        usar_saldo = st.toggle("🎟️ REUTILIZAR BOLETO ABIERTO (CANJE)", help="Vincula este nuevo vuelo a un saldo a favor anterior.", key=f"tgl_{rk}")
        if usar_saldo:
            if not df_abiertos.empty:
                opciones = df_abiertos.apply(lambda x: f"ID: {x['id']} | PNR: {x['PNR']} | {x['Pasajero']} | ${x.get('Costo', 0)}", axis=1).tolist()
                seleccion = st.selectbox("Selecciona el boleto a canjear:", opciones, key=f"sel_canje_{rk}")
                id_abierto_seleccionado = int(seleccion.split(" | ")[0].replace("ID: ", ""))
                pnr_ligado = seleccion.split(" | ")[1].replace("PNR: ", "")
            else: st.warning("No hay boletos abiertos disponibles.")

    st.markdown("---")
    
    # --- FILA 1: Pasajeros / PNR / Tel ---
    c1, c2, c3 = st.columns([2, 1, 1])
    # Cambiamos a text_input para permitir múltiples nombres separados por coma fácilmente
    pax_input = c1.text_input("👥 PASAJERO(S) (Separados por coma)", placeholder="Ej: JUAN PEREZ, MARIA GOMEZ", key=f"pax_text_{rk}").upper()
    pnr = c2.text_input("🎫 PNR", placeholder="Ej: XJ3K9P", key=f"pnr_{rk}").upper()
    tel = c3.text_input("🟢 WHATSAPP", placeholder="Ej: 5281...", key=f"tel_{rk}")
    
    # --- FILA 2: Rutas y Fechas ---
    c4, c5, c6, c7 = st.columns([1.5, 1.5, 1, 1])
    sel_ori = c4.selectbox("🔍 ORIGEN", ["➕ NUEVO ORIGEN..."] + sorted(rutas_conocidas), key=f"sel_ori_{rk}")
    ori = c4.text_input("ESCRIBE ORIGEN", key=f"ori_text_{rk}").upper() if sel_ori == "➕ NUEVO ORIGEN..." else sel_ori
    
    sel_des = c5.selectbox("🔍 DESTINO", ["➕ NUEVO DESTINO..."] + sorted(rutas_conocidas), key=f"sel_des_{rk}")
    des = c5.text_input("ESCRIBE DESTINO", key=f"des_text_{rk}").upper() if sel_des == "➕ NUEVO DESTINO..." else sel_des
    
    # Las fechas ahora toman su valor automáticamente del session_state gracias a la "key"
    fec = c6.date_input("📅 SALIDA", key=f"fec_{rk}")
    fec_reg = c7.date_input("📅 REGRESO", value=None, key=f"fec_reg_{rk}")
    
    # --- FILA 3: Operación ---
    c8, c9, c10, c11 = st.columns([1.5, 1, 1, 1])
    sel_aer = c8.selectbox("🔍 AEROLÍNEA", ["➕ NUEVA AEROLÍNEA..."] + sorted(aero_conocidas), key=f"sel_aer_{rk}")
    aer = c8.text_input("ESCRIBE AEROLÍNEA", key=f"aer_text_{rk}").upper() if sel_aer == "➕ NUEVA AEROLÍNEA..." else sel_aer
    
    nvv = c9.text_input("🔢 NO. VUELO", placeholder="AMX001", key=f"nvv_{rk}").upper()
    pais = c10.selectbox("🌎 PAÍS", ["MÉXICO", "ESTADOS UNIDOS", "OTROS"], key=f"pais_{rk}")
    equ = c11.selectbox("🧳 EQUIPAJE", ["MANO", "DOCUMENTADO", "COMPLETO"], key=f"equ_{rk}")
    
    # --- FILA 4: Control ---
    st.markdown("---")
    c_mot, c_aut = st.columns(2)
    mot = c_mot.text_input("🎯 MOTIVO DEL VIAJE", key=f"mot_{rk}").upper()
    aut = c_aut.text_input("👤 QUIÉN AUTORIZA", key=f"aut_{rk}").upper()

    # --- FILA 5: Finanzas ---
    st.markdown("---")
    c12, c13, c14, c15 = st.columns([1, 1, 1, 2])
    cos = c12.number_input("💲COSTO TOTAL (MX)", min_value=0.0, step=0.01, key=f"cos_{rk}")
    ext = c13.selectbox("EXTRAS", ["NO", "SÍ"], key=f"ext_{rk}")
    est = c14.selectbox("ESTADO", ["Activo", "Abierto (Disponible)"], key=f"est_{rk}")
    archivos_manuales = c15.file_uploader("📄 SOPORTES EXTRA", type=['pdf', 'jpg', 'png'], accept_multiple_files=True, key=f"file_{rk}")
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("💾 CONFIRMAR Y GUARDAR REGISTRO", use_container_width=True, type="primary"):
        if not pax_input or not pnr:
            st.error("❌ Pasajero(s) y PNR son obligatorios.")
            return

        # Lógica de Expediente Unificado
        ruta_soporte = ""
        if archivos_ia:
            if not os.path.exists("attachments"): os.makedirs("attachments")
            pdf_unificado = unir_archivos_en_pdf(archivos_ia)
            nombre_exp = f"EXPEDIENTE_{pnr}_{datetime.now().strftime('%H%M%S')}.pdf"
            ruta_soporte = os.path.join("attachments", nombre_exp)
            with open(ruta_soporte, "wb") as f: f.write(pdf_unificado)
        elif archivos_manuales:
            rutas = []
            if not os.path.exists("attachments"): os.makedirs("attachments")
            for a in archivos_manuales:
                r = os.path.join("attachments", f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{a.name}")
                with open(r, "wb") as f: f.write(a.getbuffer())
                rutas.append(r)
            ruta_soporte = "|".join(rutas)

        try:
            conn = sqlite3.connect('logistics_v2.db')
            cursor = conn.cursor()
            
            # --- SOLUCIÓN PROBLEMA 2: MULTIPLES PASAJEROS ---
            # Separamos los nombres por coma y limpiamos espacios vacíos
            lista_pasajeros = [p.strip() for p in pax_input.split(",") if p.strip()]
            
            # Dividimos el costo total entre la cantidad de pasajeros
            costo_individual = cos / len(lista_pasajeros) if len(lista_pasajeros) > 0 else 0
            
            # Nombre de usuario fallback por si 'usuario' no está en session_state (evita error 500)
            nombre_usuario = st.session_state.usuario['nombre'] if 'usuario' in st.session_state else "SISTEMA"

            # Guardamos un registro por CADA pasajero
            for pax in lista_pasajeros:
                cursor.execute('''
                    INSERT INTO vuelos (Pasajero, Origen, Destino, Estado, Costo, PNR, Fecha, Fecha_Regreso, Pais, Soporte, Usuario, Hora, Telefono, Aerolinea, No_Vuelo, Motivo, Autoriza, Boleto_Ligado, Extra)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (pax, ori.strip(), des.strip(), est, costo_individual, pnr.strip(), str(fec), str(fec_reg) if fec_reg else "", pais, ruta_soporte, nombre_usuario, datetime.now().strftime("%H:%M"), tel.strip(), aer.strip(), nvv.strip(), mot.strip() or "NO ESPECIFICADO", aut.strip() or "PENDIENTE", pnr_ligado, ext))
            
            # Actualizamos estado si se usó un saldo a favor
            if usar_saldo and id_abierto_seleccionado:
                cursor.execute("UPDATE vuelos SET Estado='Canjeado' WHERE id=?", (id_abierto_seleccionado,))
            
            conn.commit()
            st.session_state.db_vuelos = pd.read_sql_query("SELECT * FROM vuelos WHERE deleted_at IS NULL", conn)
            conn.close()
            
            st.toast(f"✅ {len(lista_pasajeros)} Vuelo(s) del PNR {pnr} registrado(s) correctamente.", icon="✅")
            st.session_state['reg_key'] += 1 
            time.sleep(1) 
            st.rerun()
        except Exception as e: 
            st.error(f"Error DB: {e}")