import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import date
from modules import auth, dashboard, inventory, registrar, reporting, audit

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="LOGISTICS ENGINE v2.0", layout="wide")

# --- GESTIÓN DE BASE DE DATOS (SQLITE) ---
def init_db():
    """Crea la base de datos y la tabla si no existen."""
    conn = sqlite3.connect('logistics_v2.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vuelos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Pasajero TEXT NOT NULL,
            Origen TEXT,
            Destino TEXT,
            Estado TEXT,
            Costo REAL,
            PNR TEXT,
            Equipaje TEXT,
            Extra TEXT,
            Fecha TEXT,
            Soporte TEXT,
            Usuario TEXT,
            Hora TEXT
        )
    ''')
    conn.commit()
    
    # Si la tabla está vacía, insertar datos de ejemplo para no iniciar en blanco
    cursor.execute("SELECT COUNT(*) FROM vuelos")
    if cursor.fetchone()[0] == 0:
        vuelos_demo = [
            ("ALEXANDER PIERCE", "JFK", "LHR", "Activo", 2450.0, "XP-992", "FULL", "NO", "2024-05-10", "", "ADMIN", "22:15"),
            ("SARAH JENKINS", "MEX", "CDG", "Abierto (Disponible)", 1800.0, "FR-112", "MANO", "SÍ", "2024-05-15", "", "ADMIN", "11:00")
        ]
        cursor.executemany('''
            INSERT INTO vuelos (Pasajero, Origen, Destino, Estado, Costo, PNR, Equipaje, Extra, Fecha, Soporte, Usuario, Hora)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', vuelos_demo)
        conn.commit()
    conn.close()

# --- INICIALIZACIÓN DE ESTADO ---
def init_session_state():
    # Inicializar DB física
    init_db()
    
    # Crear carpeta de archivos si no existe
    if not os.path.exists("attachments"):
        os.makedirs("attachments")

    # Cargar datos desde SQLite al Session State
    if 'db_vuelos' not in st.session_state:
        conn = sqlite3.connect('logistics_v2.db')
        # Cargamos todo como DataFrame
        st.session_state['db_vuelos'] = pd.read_sql_query("SELECT * FROM vuelos", conn)
        conn.close()

    if 'logs' not in st.session_state:
        st.session_state['logs'] = []
    if 'autenticado' not in st.session_state:
        st.session_state['autenticado'] = False
    if 'usuario' not in st.session_state:
        st.session_state['usuario'] = None

init_session_state()

# --- ESTILOS ENTERPRISE ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #000000; color: #e5e7eb; }
    .stApp { background: #000000; }
    .stTabs [data-baseweb="tab-list"] { gap: 50px; border-bottom: 1px solid #1A1A1A; }
    .stTabs [data-baseweb="tab"] { background-color: transparent !important; color: #444 !important; letter-spacing: 2px; font-size: 11px; }
    .stTabs [aria-selected="true"] { color: #00d4ff !important; border-bottom: 1px solid #00d4ff !important; }
    .stButton>button { background: #0A0A0A; border: 1px solid #222; color: #AAA; border-radius: 2px; text-transform: uppercase; letter-spacing: 1px; font-size: 10px; width: 100%; }
    .stButton>button:hover { border-color: #00d4ff; color: #00d4ff; background: #00d4ff11; }
    </style>
""", unsafe_allow_html=True)

def main():
    if not st.session_state.autenticado:
        auth.show_login()
    else:
        # Barra de Navegación Superior
        c_nav1, c_nav2 = st.columns([9, 1])
        # Usamos .get() para evitar errores si el diccionario no tiene las llaves esperadas
        rol_user = st.session_state.usuario.get('rol', 'USER') if st.session_state.usuario else "USER"
        c_nav1.markdown(f"<h3 style='letter-spacing:6px; font-weight:300; font-size:16px;'>SYSTEM ENGINE // {rol_user}</h3>", unsafe_allow_html=True)
        
        if c_nav2.button("LOGOUT"):
            st.session_state.autenticado = False
            st.session_state.usuario = None
            st.rerun()

        tabs = st.tabs(["DASHBOARD", "INVENTARIO VUELOS", "REGISTRO VUELO", "INTELIGENCIA DE NEGOCIO", "HISTORIAL DE EVENTOS"])
        
        with tabs[0]: dashboard.render()
        with tabs[1]: inventory.render()
        with tabs[2]: registrar.render()
        with tabs[3]: reporting.render()
        with tabs[4]: 
            st.info("Bitácora de auditoría disponible en logs del sistema.")

if __name__ == "__main__":
    main()