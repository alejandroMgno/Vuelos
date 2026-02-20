import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, datetime
from fpdf import FPDF
import io

class ReporteEjecutivo(FPDF):
    def header(self):
        self.set_fill_color(15, 15, 15)
        self.rect(0, 0, 210, 40, 'F')
        self.set_font('Arial', 'B', 16)
        self.set_text_color(255, 255, 255)
        self.cell(0, 20, 'INFORME EJECUTIVO DE AUDITORIA', 0, 1, 'C')
        self.ln(25)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Pagina {self.page_no()} | Confidencial', 0, 0, 'C')

def generar_pdf_bytes(df, m_total, m_recuperar, riesgo):
    # Usamos 'latin-1' para evitar errores de caracteres especiales en FPDF
    pdf = ReporteEjecutivo()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, ' 1. RESUMEN FINANCIERO', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 8, f'VALOR TOTAL: ${m_total:,.2f} USD', 0, 1)
    pdf.cell(0, 8, f'RIESGO (ABIERTOS): ${m_recuperar:,.2f} USD ({riesgo:.1f}%)', 0, 1)
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 8)
    pdf.set_fill_color(0, 174, 255)
    pdf.set_text_color(255, 255, 255)
    for col_name, width in [('PASAJERO', 70), ('PNR', 30), ('RUTA', 50), ('COSTO', 35)]:
        pdf.cell(width, 8, col_name, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_font('Arial', '', 7)
    pdf.set_text_color(0, 0, 0)
    for _, fila in df.iterrows():
        pdf.cell(70, 7, str(fila['Pasajero'])[:35], 1)
        pdf.cell(30, 7, str(fila['PNR']), 1, 0, 'C')
        pdf.cell(50, 7, f"{fila['Origen']} > {fila['Destino']}", 1, 0, 'C')
        pdf.cell(35, 7, f"${fila['Costo']:,.2f}", 1, 0, 'R')
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

def generar_excel_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Auditoria')
    return output.getvalue()

def render():
    st.markdown("<h4 style='letter-spacing:4px; font-weight:300;'>CENTRO_DE_INTELIGENCIA_Y_AUDITORIA</h4>", unsafe_allow_html=True)
    
    # --- FILTROS ---
    c_f1, c_f2 = st.columns(2)
    inicio = c_f1.date_input("FECHA_INICIO", date(2024, 1, 1))
    fin = c_f2.date_input("FECHA_FIN", date(2025, 12, 31))
    
    # SOLUCIÓN AL ERROR DE COMPARACIÓN:
    # Convertimos la columna a datetime y luego a .date() para que coincida con 'inicio' y 'fin'
    df_temp = st.session_state.db_vuelos.copy()
    df_temp['Fecha_DT'] = pd.to_datetime(df_temp['Fecha']).dt.date
    
    df_f = df_temp[(df_temp['Fecha_DT'] >= inicio) & (df_temp['Fecha_DT'] <= fin)]

    if df_f.empty:
        st.warning("No hay datos disponibles para el rango seleccionado.")
        return

    # Cálculos
    abiertos = df_f[df_f['Estado'] == 'Abierto (Disponible)']
    costo_abiertos = abiertos['Costo'].sum()
    costo_total = df_f['Costo'].sum()
    riesgo = (costo_abiertos / costo_total * 100) if costo_total > 0 else 0

    # --- DESCARGAS ---
    c_d1, c_d2 = st.columns(2)
    with c_d1:
        try:
            pdf_data = generar_pdf_bytes(df_f, costo_total, costo_abiertos, riesgo)
            st.download_button("📄 REPORTE_PDF_EJECUTIVO", data=pdf_data, file_name=f"Auditoria_{date.today()}.pdf", mime="application/pdf", use_container_width=True)
        except Exception as e:
            st.error(f"Error generando PDF: {e}")
            
    with c_d2:
        excel_data = generar_excel_bytes(df_f)
        st.download_button("📊 REPORTE_EXCEL_DATA", data=excel_data, file_name=f"Datos_{date.today()}.xlsx", use_container_width=True)

    # --- DIAGNÓSTICO IA ---
    color_riesgo = "#FF3B30" if riesgo > 15 else "#4CD964"
    st.markdown(f"""
        <div style='background: #0A0A0A; border-left: 5px solid #00d4ff; padding: 20px; margin: 20px 0;'>
            <div style='color: #00d4ff; font-size: 11px; letter-spacing: 3px; font-weight: 600;'>🤖 DIAGNOSTICO_SISTEMA_IA</div>
            <div style='font-size: 18px; color: #FFF; margin: 10px 0;'>Capital Abierto Detectado: <b>${costo_abiertos:,.2f}</b></div>
            <div style='color: #888; font-size: 13px;'>Riesgo: <span style='color:{color_riesgo};'>{riesgo:.1f}%</span> del total auditado.</div>
        </div>
    """, unsafe_allow_html=True)

    # --- MÉTRICAS ---
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("CAPITAL_TOTAL", f"${costo_total:,.0f}")
    m2.metric("EN_RIESGO", len(abiertos))
    m3.metric("RECUPERACIÓN", f"${costo_abiertos:,.0f}")
    m4.metric("AUDITADOS", len(df_f))

    # --- GRÁFICOS ---
    st.divider()
    col_g1, col_g2 = st.columns(2)
    
    with col_g1:
        # Gráfico de Barras con estilo neón
        fig_bar = px.bar(df_f, x="Destino", y="Costo", title="COSTOS_POR_DESTINO", 
                         color="Costo", color_continuous_scale="GnBu", template="plotly_dark")
        fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_g2:
        # Gráfico de Cartera (Donut Chart)
        fig_pie = px.pie(df_f, names="Estado", values="Costo", hole=0.6, title="ESTADO_DE_CARTERA",
                         color_discrete_map={"Abierto (Disponible)":"#FFCC00", "Activo":"#00aeef", "Realizado":"#4CD964", "Cancelado":"#FF3B30"})
        fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- GESTIÓN RÁPIDA ---
    if not abiertos.empty:
        st.markdown("<br><b style='letter-spacing:2px;'>GESTIÓN_DE_PRIORIDADES (PENDIENTES)</b>", unsafe_allow_html=True)
        for idx, fila in abiertos.iterrows():
            with st.expander(f"🔴 {fila['Pasajero']} | {fila['PNR']} | ${fila['Costo']:,.2f}"):
                c1, c2 = st.columns([3, 1])
                nuevo = c1.selectbox("CAMBIAR_ESTADO:", ["Abierto (Disponible)", "Activo", "Realizado", "Cancelado"], key=f"upd_{idx}")
                if c2.button("CONFIRMAR", key=f"btn_{idx}", use_container_width=True):
                    # Actualización directa en session_state y sincronización manual (opcional)
                    st.session_state.db_vuelos.at[idx, 'Estado'] = nuevo
                    st.success(f"Actualizado: {fila['PNR']}")
                    st.rerun()