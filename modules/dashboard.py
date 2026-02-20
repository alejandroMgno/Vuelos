import streamlit as st
import pandas as pd
import plotly.express as px
import io
from datetime import datetime

# Función auxiliar para exportar datos del dashboard
def descargar_datos(df_descarga, nombre_archivo):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_descarga.to_excel(writer, index=False, sheet_name='Dashboard_Export')
    return output.getvalue()

def render():
    df = st.session_state.db_vuelos
    
    # Asegurar que la fecha sea objeto datetime para cálculos
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    hoy = datetime.now().date()

    st.markdown("<h4 style='letter-spacing:2px; font-weight:300;'>DASHBOARD_ESTADÍSTICO</h4>", unsafe_allow_html=True)

    # --- FILA 1: MÉTRICAS CON BOTÓN DE EXPORTACIÓN ---
    c1, c2, c3 = st.columns(3)
    
    with c1:
        activos = df[df['Estado'] == 'Activo']
        st.metric("TICKETS ACTIVOS", len(activos))
        st.download_button("💾 Exportar Activos", descargar_datos(activos, "Activos"), "activos.xlsx", key="dl_act")

    with c2:
        abiertos = df[df['Estado'].str.contains('Abierto', na=False)]
        st.metric("TICKETS ABIERTOS", len(abiertos))
        st.download_button("💾 Exportar Abiertos", descargar_datos(abiertos, "Abiertos"), "abiertos.xlsx", key="dl_abi")

    with c3:
        cancelados = df[df['Estado'] == 'Cancelado']
        st.metric("TICKETS CANCELADOS", len(cancelados))
        st.download_button("💾 Exportar Cancelados", descargar_datos(cancelados, "Cancelados"), "cancelados.xlsx", key="dl_can")

    st.divider()

    # --- FILA 2: COSTOS ANUALES Y MENSUALES ---
    c_costo1, c_costo2 = st.columns(2)
    
    with c_costo1:
        costo_anual = df[df['Fecha'].dt.year == datetime.now().year]['Costo'].sum()
        st.markdown(f"<small>COSTO TOTAL AÑO {datetime.now().year}</small>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color:#4CD964;'>${costo_anual:,.2f} </h2>", unsafe_allow_html=True)
        st.download_button("📊 Reporte Anual", descargar_datos(df[df['Fecha'].dt.year == datetime.now().year], "Anual"), "costo_anual.xlsx")

    with c_costo2:
        costo_mes = df[(df['Fecha'].dt.month == datetime.now().month) & (df['Fecha'].dt.year == datetime.now().year)]['Costo'].sum()
        st.markdown(f"<small>COSTO TOTAL MES ACTUAL</small>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='color:#00d4ff;'>${costo_mes:,.2f} </h2>", unsafe_allow_html=True)

    st.divider()

    # --- FILA 3: PRÓXIMOS VUELOS Y EXPORTACIÓN ---
    st.markdown("##### ✈️ PRÓXIMOS VUELOS")
    proximos = df[df['Fecha'].dt.date >= hoy].sort_values('Fecha')
    
    col_p1, col_p2 = st.columns([3, 1])
    col_p1.dataframe(proximos[['Pasajero', 'Clave_de_Reserva', 'Fecha', 'Origen', 'Destino', 'Estado']].head(5), use_container_width=True)
    col_p2.markdown("<br>", unsafe_allow_html=True)
    col_p2.download_button("🛫 Exportar Próximos", descargar_datos(proximos, "Proximos"), "proximos_vuelos.xlsx", use_container_width=True)

    st.divider()

    # --- FILA 3.5: TICKETS ABIERTOS Y EXPORTACIÓN ---
    st.markdown("##### ⚠️ TICKETS ABIERTOS (DISPONIBLES)")
    # Ordenamos por Costo descendente para ver los de mayor valor primero
    abiertos_df = df[df['Estado'].str.contains('Abierto', na=False)].sort_values('Costo', ascending=False)
    
    col_a1, col_a2 = st.columns([3, 1])
    # Mostramos las columnas más relevantes, incluyendo el Costo
    col_a1.dataframe(abiertos_df[['Pasajero', 'Clave_de_Reserva', 'Costo', 'Fecha', 'Origen', 'Destino']].head(5), use_container_width=True)
    col_a2.markdown("<br>", unsafe_allow_html=True)
    col_a2.download_button("📥 Exportar Abiertos", descargar_datos(abiertos_df, "Abiertos_Detalle"), "tickets_abiertos_detalle.xlsx", use_container_width=True)

    st.divider()

    # --- FILA 4: GRÁFICAS ---
    g1, g2 = st.columns(2)

    with g1:
        st.markdown("<small>VUELOS POR CIUDAD DE DESTINO</small>", unsafe_allow_html=True)
        # Gráfica de número de vuelos por ciudad
        vuelos_ciudad = df['Destino'].value_counts().reset_index()
        vuelos_ciudad.columns = ['Ciudad', 'Cantidad']
        fig_ciudad = px.bar(vuelos_ciudad, x='Ciudad', y='Cantidad', template="plotly_dark", color_discrete_sequence=['#00d4ff'])
        fig_ciudad.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_ciudad, use_container_width=True)

    with g2:
        st.markdown("<small>DISTRIBUCIÓN POR ESTADO</small>", unsafe_allow_html=True)
        # Gráfica de activos, cancelados, realizados y abiertos
        fig_estado = px.pie(df, names='Estado', hole=0.4, template="plotly_dark", 
                            color_discrete_map={'Activo':'#00d4ff', 'Cancelado':'#FF3B30', 'Realizado':'#4CD964', 'Abierto (Disponible)':'#FFCC00'})
        fig_estado.update_layout(paper_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_estado, use_container_width=True)