import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, datetime
from fpdf import FPDF
import io
import os
import tempfile
import sqlite3
import matplotlib.pyplot as plt

# --- INTENTAMOS IMPORTAR LA LIBRERÍA DE IA ---
try:
    import google.generativeai as genai
    IA_DISPONIBLE = True
except ImportError:
    IA_DISPONIBLE = False

# --- FUNCIONES DE PERSISTENCIA EN BASE DE DATOS ---
def obtener_config(clave):
    try:
        conn = sqlite3.connect('logistics_v2.db')
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM configuracion WHERE clave=?", (clave,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else ""
    except:
        return ""

def guardar_config(clave, valor):
    try:
        conn = sqlite3.connect('logistics_v2.db')
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)", (clave, valor))
        conn.commit()
        conn.close()
    except Exception as e:
        pass

# --- FUNCIÓN SANITIZADORA PARA PDF ---
def limpiar_texto_pdf(texto):
    if pd.isna(texto): return ""
    if not isinstance(texto, str): texto = str(texto)
    texto = texto.replace('“', '"').replace('”', '"').replace('—', '-').replace('–', '-').replace('•', '-')
    return texto.encode('latin-1', 'replace').decode('latin-1')

# --- CLASE MAESTRA PARA EL REPORTE PDF ---
class ReporteEjecutivo(FPDF):
    def header(self):
        self.set_fill_color(10, 10, 10)
        self.rect(0, 0, 210, 35, 'F')
        self.set_font('Arial', 'B', 18)
        self.set_text_color(0, 212, 255) # Cyan Corporativo
        self.cell(0, 15, 'LOGISTICS ENGINE v2.0', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.set_text_color(200, 200, 200)
        self.cell(0, 5, 'REPORTE DE INTELIGENCIA E IMPACTO FINANCIERO', 0, 1, 'C')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f'Generado el {date.today().strftime("%d/%m/%Y")} | Documento Confidencial | Pagina {self.page_no()}', 0, 0, 'C')

# --- MOTOR DE INTELIGENCIA ARTIFICIAL ---
def obtener_analisis_ia(df, m_total, m_recuperar, riesgo, ahorro, api_key):
    if not IA_DISPONIBLE or not api_key:
        return f"MODO OFFLINE: Configura tu API Key. El riesgo es del {riesgo:.1f}%. Has recuperado ${ahorro:,.2f} MX."
    
    try:
        genai.configure(api_key=api_key)
        modelo_elegido = None
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                if 'flash' in m.name or 'pro' in m.name:
                    modelo_elegido = m.name
                    break
                    
        if not modelo_elegido:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    modelo_elegido = m.name
                    break

        model = genai.GenerativeModel(modelo_elegido)
        
        top_destinos = df['Destino'].value_counts().head(3).to_dict()
        top_pax_gasto = df.groupby('Pasajero')['Costo'].sum().nlargest(3).to_dict()
        top_aero = df['Aerolinea'].value_counts().head(3).to_dict()
        
        prompt = f"""
        Actúa como Director Financiero Logístico y Científico de Datos. Analiza:
        - Inversión Total: ${m_total:,.2f}
        - Capital en Riesgo (Boletos Abiertos): ${m_recuperar:,.2f} ({riesgo:.1f}%)
        - Ahorro por Canjes (Reutilización): ${ahorro:,.2f}
        - Top 3 Destinos: {top_destinos}
        - Top 3 Viajeros (Costo): {top_pax_gasto}
        - Top Aerolíneas: {top_aero}
        
        Escribe 2 párrafos altamente ejecutivos. 
        Párrafo 1: Diagnóstico financiero destacando el ahorro y la concentración del gasto en viajeros/destinos.
        Párrafo 2: Dos recomendaciones estrictas para mitigar el riesgo de los boletos abiertos y negociar con aerolíneas.
        No uses markdown, asteriscos ni emojis. Texto plano y profesional.
        """
        respuesta = model.generate_content(prompt)
        return respuesta.text.replace('*', '').strip()
    except Exception as e:
        return f"Error conectando a la IA: {e}"

# --- GENERADOR DE GRÁFICOS TEMPORALES PARA EL PDF ---
def generar_graficos_temporales(df):
    fd_pie1, ruta_pie_estado = tempfile.mkstemp(suffix=".png")
    fd_pie2, ruta_pie_aero = tempfile.mkstemp(suffix=".png")
    os.close(fd_pie1)
    os.close(fd_pie2)
    
    # Gráfico 1: Estado de Cartera
    plt.figure(figsize=(6, 4), dpi=150)
    datos_estado = df.groupby('Estado')['Costo'].sum()
    colores_est = {'Activo':'#00aeef', 'Abierto (Disponible)':'#FFCC00', 'Realizado':'#4CD964', 'Cancelado':'#FF3B30', 'Canjeado':'#888888'}
    plt.pie(datos_estado, labels=datos_estado.index, autopct='%1.1f%%', startangle=140, colors=[colores_est.get(x, '#999') for x in datos_estado.index])
    plt.title("SALUD DE CARTERA", fontweight='bold')
    plt.savefig(ruta_pie_estado)
    plt.close()

    # Gráfico 2: Top 5 Aerolíneas
    plt.figure(figsize=(6, 4), dpi=150)
    datos_aero = df.groupby('Aerolinea')['Costo'].sum().sort_values(ascending=False).head(5)
    plt.bar(datos_aero.index, datos_aero.values, color='#00d4ff')
    plt.title("TOP 5 PROVEEDORES (AEROLINEAS)", fontweight='bold')
    plt.xticks(rotation=15, fontsize=8)
    plt.tight_layout()
    plt.savefig(ruta_pie_aero)
    plt.close()
    
    return ruta_pie_estado, ruta_pie_aero

# --- CREADOR DE PDF DIRECTIVO ---
def generar_pdf_pro(df, m_total, m_recuperar, riesgo, ahorro, texto_ia):
    pdf = ReporteEjecutivo()
    pdf.add_page()
    
    # SECCIÓN 1: FINANZAS
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, ' 1. MACROMETRICAS FINANCIERAS', 0, 1, 'L', True)
    pdf.ln(3)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(65, 8, f'INVERSION TOTAL:', 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f'${m_total:,.2f} MX', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    if riesgo > 15:
        pdf.set_text_color(255, 59, 48)
    else:
        pdf.set_text_color(76, 217, 100)
    pdf.cell(65, 8, f'CAPITAL EN RIESGO (ABIERTOS):', 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f'${m_recuperar:,.2f} MX ({riesgo:.1f}%)', 0, 1)
    
    pdf.set_font('Arial', 'B', 10)
    pdf.set_text_color(0, 150, 255)
    pdf.cell(65, 8, f'AHORRO LOGRADO (CANJES):', 0, 0)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f'${ahorro:,.2f} MX', 0, 1)
    pdf.ln(5)
    pdf.set_text_color(0,0,0)

    # SECCIÓN 2: IA
    pdf.set_fill_color(230, 245, 255)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(0, 100, 150)
    pdf.cell(0, 10, ' 2. DIAGNOSTICO DE INTELIGENCIA ARTIFICIAL', 0, 1, 'L', True)
    pdf.ln(3)
    pdf.set_font('Arial', '', 10)
    pdf.set_text_color(50, 50, 50)
    pdf.multi_cell(0, 6, limpiar_texto_pdf(texto_ia))
    pdf.ln(5)

    # SECCIÓN 3: GRÁFICOS
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Arial', 'B', 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 10, ' 3. PANORAMA VISUAL', 0, 1, 'L', True)
    pdf.ln(5)

    try:
        r1, r2 = generar_graficos_temporales(df)
        y_graficos = pdf.get_y()
        pdf.image(r1, x=10, y=y_graficos, w=90)
        pdf.image(r2, x=110, y=y_graficos, w=90)
        pdf.set_y(y_graficos + 65)
        os.remove(r1)
        os.remove(r2)
    except Exception as e:
        pdf.cell(0, 10, f"Error generando graficos visuales: {e}", 0, 1)

    # SECCIÓN 4: AUDITORÍA (NUEVA TABLA CON NO. VUELO)
    pdf.ln(5)
    if pdf.get_y() > 200: 
        pdf.add_page()
        
    pdf.set_fill_color(30, 30, 30)
    pdf.set_font('Arial', 'B', 8)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, ' 4. AUDITORIA OPERATIVA (TOP 30 DE MAYOR VALOR)', 0, 1, 'L', True)
    
    anchos = [40, 15, 18, 20, 25, 20, 20, 15, 20]
    headers = ['PASAJERO', 'PNR', 'FECHA', 'AEROLINEA', 'VUELO/RUTA', 'ESTADO', 'CANJE', 'EXTRAS', 'COSTO']
    for i in range(len(headers)): 
        pdf.cell(anchos[i], 8, headers[i], 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_font('Arial', '', 6.5)
    pdf.set_text_color(0, 0, 0)
    
    df_top = df.sort_values(by='Costo', ascending=False).head(30)
    for i, f in df_top.iterrows():
        if i % 2 == 0: 
            pdf.set_fill_color(245, 245, 245)
        else: 
            pdf.set_fill_color(255, 255, 255)
            
        estado = limpiar_texto_pdf(str(f.get('Estado',''))[:15])
        aerolinea = limpiar_texto_pdf(str(f.get('Aerolinea', 'N/A'))[:12])
        bol_ligado = limpiar_texto_pdf(str(f.get('Boleto_Ligado', '')))
        canje_str = bol_ligado if bol_ligado and bol_ligado != "nan" else "-"
        ruta_vuelo = limpiar_texto_pdf(f"{f.get('No_Vuelo','S/N')} | {f.get('Origen','')}->{f.get('Destino','')}")
        
        pdf.cell(anchos[0], 7, limpiar_texto_pdf(str(f.get('Pasajero',''))[:25]), 1, 0, 'L', True)
        pdf.cell(anchos[1], 7, limpiar_texto_pdf(str(f.get('PNR',''))), 1, 0, 'C', True)
        pdf.cell(anchos[2], 7, limpiar_texto_pdf(str(f.get('Fecha',''))), 1, 0, 'C', True)
        pdf.cell(anchos[3], 7, aerolinea, 1, 0, 'C', True)
        pdf.cell(anchos[4], 7, ruta_vuelo, 1, 0, 'C', True)
        pdf.cell(anchos[5], 7, estado, 1, 0, 'C', True)
        pdf.cell(anchos[6], 7, canje_str, 1, 0, 'C', True)
        pdf.cell(anchos[7], 7, limpiar_texto_pdf(str(f.get('Extra','NO'))), 1, 0, 'C', True)
        pdf.cell(anchos[8], 7, f"${f.get('Costo',0):,.2f}", 1, 0, 'R', True)
        pdf.ln()

    return pdf.output(dest='S').encode('latin-1')

# --- EXPORTADOR EXCEL ---
def generar_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data_Intelligence')
    return output.getvalue()

# ==========================================
# VISTA PRINCIPAL (STREAMLIT RENDER)
# ==========================================
def render():
    st.markdown("<h3 style='letter-spacing:4px; font-weight:300; color:#00d4ff;'>📊 BI & ANALYTICS CENTER</h3>", unsafe_allow_html=True)
    
    # --- CONFIGURACIÓN IA SIDEBAR ---
    with st.sidebar.expander("🤖 MOTOR DE IA GEMINI", expanded=False):
        api_actual = obtener_config("gemini_api_key")
        nueva_api = st.text_input("Ingresa tu API Key", value=api_actual, type="password")
        if nueva_api != api_actual:
            guardar_config("gemini_api_key", nueva_api)
            st.success("API Key vinculada al sistema.")

    df_f = st.session_state.db_vuelos.copy()
    
    # --- PREVENCIÓN DE ERRORES DE COLUMNAS ---
    if 'No_Vuelo' not in df_f.columns:
        df_f['No_Vuelo'] = 'S/N'
    if 'Aerolinea' not in df_f.columns:
        df_f['Aerolinea'] = 'N/A'
    if 'Boleto_Ligado' not in df_f.columns:
        df_f['Boleto_Ligado'] = ''

    # --- FILTROS GLOBALES ---
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns(4)
        inicio = f1.date_input("DESDE", date(2024, 1, 1))
        fin = f2.date_input("HASTA", date(2026, 12, 31))
        
        df_f['Fecha_DT'] = pd.to_datetime(df_f['Fecha']).dt.date
        df_f = df_f[(df_f['Fecha_DT'] >= inicio) & (df_f['Fecha_DT'] <= fin)]
        
        pax_lista = df_f['Pasajero'].unique().tolist()
        aero_lista = df_f['Aerolinea'].unique().tolist()
        
        filtro_pax = f3.multiselect("PASAJEROS", pax_lista)
        filtro_aero = f4.multiselect("AEROLÍNEAS", aero_lista)
        
        if filtro_pax: 
            df_f = df_f[df_f['Pasajero'].isin(filtro_pax)]
        if filtro_aero: 
            df_f = df_f[df_f['Aerolinea'].isin(filtro_aero)]

    if df_f.empty:
        st.warning("No hay registros que coincidan con los filtros de búsqueda.")
        return

    # --- CÁLCULO DE MACROMÉTRICAS ---
    m_total = df_f['Costo'].sum()
    abiertos = df_f[df_f['Estado'] == 'Abierto (Disponible)']
    m_riesgo = abiertos['Costo'].sum()
    riesgo_p = (m_riesgo / m_total * 100) if m_total > 0 else 0
    ahorro = df_f[df_f['Estado'] == 'Canjeado']['Costo'].sum()

    # --- KPI BANNER ---
    st.markdown("<br>", unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("GASTO ACUMULADO", f"${m_total:,.0f}")
    k2.metric("CAPITAL EN RIESGO", f"${m_riesgo:,.0f}", f"{riesgo_p:.1f}%", delta_color="inverse")
    k3.metric("EFICIENCIA (AHORRO)", f"${ahorro:,.0f}", "Canjes Logrados", delta_color="normal")
    k4.metric("TOTAL BOLETOS", len(df_f))
    k5.metric("AEROLÍNEAS ACTIVAS", df_f['Aerolinea'].nunique())

    # --- BOTONERA DE ACCIÓN ---
    st.markdown("<hr style='margin: 10px 0; border-color: #333;'>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    
    if b1.button("🧠 EJECUTAR DIAGNÓSTICO IA", use_container_width=True, type="primary"):
        with st.spinner("Motor neuronal analizando tendencias..."):
            st.session_state['texto_ia'] = obtener_analisis_ia(df_f, m_total, m_riesgo, riesgo_p, ahorro, nueva_api)

    texto_ia = st.session_state.get('texto_ia', "El análisis predictivo no ha sido generado.")
    
    pdf_data = generar_pdf_pro(df_f, m_total, m_riesgo, riesgo_p, ahorro, texto_ia)
    b2.download_button("📄 EXPORTAR PDF DIRECTIVO", data=pdf_data, file_name=f"BI_Report_{date.today()}.pdf", use_container_width=True)
    
    excel_data = generar_excel_bytes(df_f)
    b3.download_button("📊 EXPORTAR RAW DATA (EXCEL)", data=excel_data, file_name=f"RawData_{date.today()}.xlsx", use_container_width=True)

    if st.session_state.get('texto_ia'):
        st.markdown(f"""
            <div style='background: #0d1b2a; border-left: 5px solid #00d4ff; padding: 20px; border-radius: 5px; margin-top: 15px;'>
                <div style='color: #00d4ff; font-weight: bold; margin-bottom: 10px; letter-spacing: 2px;'>🤖 INSIGHTS GENERADOS POR IA</div>
                <div style='color: #e0e1dd; font-size: 14px; line-height: 1.6;'>{st.session_state['texto_ia']}</div>
            </div>
        """, unsafe_allow_html=True)

    # ==========================================
    # DASHBOARD GRÁFICO (PLOTLY MASTERCLASS)
    # ==========================================
    st.markdown("<br><h4 style='color:#777; font-weight:300;'>VISUALIZACIÓN DE DATOS</h4>", unsafe_allow_html=True)

    # FILA 1: Timeline a lo ancho completo
    df_f['Mes_Anio'] = pd.to_datetime(df_f['Fecha']).dt.to_period('M').astype(str)
    df_time = df_f.groupby('Mes_Anio')['Costo'].sum().reset_index()
    fig_time = px.area(df_time, x='Mes_Anio', y='Costo', title="TENDENCIA DE GASTO EN EL TIEMPO", template="plotly_dark", color_discrete_sequence=['#00d4ff'])
    fig_time.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=350)
    st.plotly_chart(fig_time, use_container_width=True)

    # FILA 2: TOP Viajeros (Gasto vs Cantidad de Vuelos)
    st.markdown("<hr style='margin: 20px 0; border-color: #222;'>", unsafe_allow_html=True)
    c_p1, c_p2 = st.columns(2)
    
    with c_p1:
        # Top 10 Pasajeros por Gasto
        df_pax_gasto = df_f.groupby('Pasajero')['Costo'].sum().sort_values(ascending=True).tail(10).reset_index()
        fig_pax_gasto = px.bar(df_pax_gasto, x='Costo', y='Pasajero', orientation='h', title="TOP 10 VIAJEROS (MAYOR INVERSIÓN MX)", template="plotly_dark", color='Costo', color_continuous_scale='Blues')
        fig_pax_gasto.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', coloraxis_showscale=False, height=350)
        st.plotly_chart(fig_pax_gasto, use_container_width=True)

    with c_p2:
        # Top 10 Pasajeros por Cantidad de Vuelos
        df_pax_vol = df_f.groupby('Pasajero').size().reset_index(name='Vuelos').sort_values(by='Vuelos', ascending=True).tail(10)
        fig_pax_vol = px.bar(df_pax_vol, x='Vuelos', y='Pasajero', orientation='h', title="TOP 10 VIAJEROS (MAYOR CANTIDAD DE VUELOS)", template="plotly_dark", color='Vuelos', color_continuous_scale='Purples')
        fig_pax_vol.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', coloraxis_showscale=False, height=350)
        st.plotly_chart(fig_pax_vol, use_container_width=True)

    # FILA 3: Destinos, Estados y Aerolíneas
    st.markdown("<hr style='margin: 20px 0; border-color: #222;'>", unsafe_allow_html=True)
    c_g3, c_g4, c_g5 = st.columns([1.5, 1, 1])
    
    with c_g3:
        # Frecuencia de Vuelos por Destino
        df_dest = df_f.groupby('Destino').agg(Vuelos=('id', 'count'), Costo_Total=('Costo', 'sum')).reset_index().sort_values('Vuelos', ascending=False).head(15)
        fig_dest = px.bar(df_dest, x='Destino', y='Vuelos', text='Vuelos', hover_data=['Costo_Total'], title="VOLUMEN DE VUELOS POR DESTINO", template="plotly_dark", color='Costo_Total', color_continuous_scale='Teal')
        fig_dest.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_dest, use_container_width=True)
        
    with c_g4:
        # Pastel de Estados
        fig_est = px.pie(df_f, names="Estado", values="Costo", hole=0.7, title="SALUD DE CARTERA",
                         color_discrete_map={"Abierto (Disponible)":"#FFCC00", "Activo":"#00aeef", "Realizado":"#4CD964", "Cancelado":"#FF3B30", "Canjeado":"#888888"}, template="plotly_dark")
        fig_est.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
        fig_est.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_est, use_container_width=True)
        
    with c_g5:
        # Pastel de Aerolíneas
        fig_aero = px.pie(df_f, names="Aerolinea", values="Costo", hole=0.4, title="MARKET SHARE (AEROLÍNEAS)", template="plotly_dark")
        fig_aero.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
        fig_aero.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_aero, use_container_width=True)

    # ==========================================
    # SECCIÓN DE MATRICES DE DATOS (TABLAS)
    # ==========================================
    st.markdown("<hr style='margin: 20px 0; border-color: #333;'>", unsafe_allow_html=True)
    t1, t2 = st.columns(2)
    
    with t1:
        st.markdown("<b style='color:#00d4ff'>📋 MATRIZ DE RUTAS OPERADAS</b>", unsafe_allow_html=True)
        st.caption("Frecuencia y gasto agrupado por ruta y número de vuelo.")
        df_rutas = df_f.groupby(['Aerolinea', 'No_Vuelo', 'Origen', 'Destino']).agg(
            Viajes=('id', 'count'), Inversion=('Costo', 'sum')
        ).reset_index().sort_values(by='Inversion', ascending=False)
        st.dataframe(df_rutas, use_container_width=True, hide_index=True, height=250)
        
    with t2:
        st.markdown("<b style='color:#4CD964'>🔄 TRAZABILIDAD DE CANJES (AHORROS)</b>", unsafe_allow_html=True)
        st.caption("Registro de nuevos PNR generados reciclando boletos viejos.")
        df_canjes_realizados = df_f[df_f['Boleto_Ligado'].astype(str).str.strip() != '']
        if not df_canjes_realizados.empty:
            tabla_canjes = df_canjes_realizados[['Pasajero', 'PNR', 'Destino', 'Boleto_Ligado', 'Costo']].copy()
            tabla_canjes.columns = ['Pasajero', 'PNR NUEVO', 'Destino', 'PNR RECICLADO', 'Extra Pagado']
            st.dataframe(tabla_canjes, use_container_width=True, hide_index=True, height=250)
        else:
            st.info("No se han registrado canjes en este periodo.")