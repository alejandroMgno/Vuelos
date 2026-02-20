import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import date
from modules import auth, dashboard, inventory, registrar, reporting, audit

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="LOGISTICS ENGINE v2.0", layout="wide")

# ==========================================================
# --- EL TRUCO DE REDIRECCIÓN AUTOMÁTICA (MOTOR JAVASCRIPT) ---
# ==========================================================
st.markdown("""
<style>
/* Esto es temporal para evitar flash de contenido */
#MainMenu {visibility: hidden;}
</style>

<script>
// Función para ejecutar después de que la página cargue
function initializeRedirect() {
    // Redirección automática a /vuelos si se accede sin él
    const currentPath = window.location.pathname;
    const basePath = '/vuelos';

    if (currentPath === '/' || !currentPath.includes(basePath)) {
        // Construir nueva URL manteniendo parámetros
        const newPath = basePath + (currentPath === '/' ? '' : currentPath);
        const newUrl = window.location.origin + newPath + window.location.search + window.location.hash;
        
        // Solo redirigir si es necesario
        if (window.location.href !== newUrl) {
            window.history.replaceState(null, null, newPath);
            console.log('Redirigido automáticamente a:', newPath);
        }
    }

    // Interceptar clics en enlaces internos
    document.addEventListener('click', function(e) {
        if (e.target.tagName === 'A') {
            const href = e.target.getAttribute('href');
            if (href && href.startsWith('/') && !href.startsWith('/vuelos/') && !href.startsWith('/static/')) {
                e.preventDefault();
                const newHref = '/vuelos' + href;
                window.location.href = newHref;
            }
        }
    });
}

// Ejecutar cuando el DOM esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeRedirect);
} else {
    initializeRedirect();
}
</script>
""", unsafe_allow_html=True)
# ==========================================================


def init_db():
    """Inicializa y actualiza la base de datos de forma segura."""
    conn = sqlite3.connect('logistics_v2.db')
    cursor = conn.cursor()
    
    try:
        # 1. Crear tabla principal si no existe
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

        # 2. Crear tabla de configuración para la API KEY y otros ajustes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configuracion (
                clave TEXT PRIMARY KEY,
                valor TEXT
            )
        ''')
        
        # 3. MIGRACIONES: Verificar y agregar columnas faltantes una por una
        cursor.execute("PRAGMA table_info(vuelos)")
        columnas = [columna[1] for columna in cursor.fetchall()]
        
        migraciones = {
            'Pais': 'ALTER TABLE vuelos ADD COLUMN Pais TEXT DEFAULT "N/A"',
            'deleted_at': 'ALTER TABLE vuelos ADD COLUMN deleted_at TEXT DEFAULT NULL',
            'Correo': 'ALTER TABLE vuelos ADD COLUMN Correo TEXT DEFAULT ""',
            'Telefono': 'ALTER TABLE vuelos ADD COLUMN Telefono TEXT DEFAULT ""',
            'Aerolinea': 'ALTER TABLE vuelos ADD COLUMN Aerolinea TEXT DEFAULT "N/A"',
            'Boleto_Ligado': 'ALTER TABLE vuelos ADD COLUMN Boleto_Ligado TEXT DEFAULT ""',
            'Motivo': 'ALTER TABLE vuelos ADD COLUMN Motivo TEXT DEFAULT "NO ESPECIFICADO"',
            'Autoriza': 'ALTER TABLE vuelos ADD COLUMN Autoriza TEXT DEFAULT "PENDIENTE"',
            'Fecha_Regreso': 'ALTER TABLE vuelos ADD COLUMN Fecha_Regreso TEXT DEFAULT ""',
            'Tipo_Viaje': 'ALTER TABLE vuelos ADD COLUMN Tipo_Viaje TEXT DEFAULT "Sencillo"'
        }
        

        for col, query in migraciones.items():
            if col not in columnas:
                cursor.execute(query)
        
        conn.commit()
        
        # 4. INSERTAR DATOS DEMO (Solo si la tabla está vacía)
        cursor.execute("SELECT COUNT(*) FROM vuelos")
        if cursor.fetchone()[0] == 0:
            vuelos_demo = [
                ("ALEXANDER PIERCE", "JFK", "LHR", "Activo", 2450.0, "XP-992", "FULL", "NO", "2024-05-10", "", "ADMIN", "22:15", "ESTADOS UNIDOS", "528100000000", "DELTA", ""),
                ("SARAH JENKINS", "MEX", "CDG", "Abierto (Disponible)", 1800.0, "FR-112", "MANO", "SÍ", "2024-05-15", "", "ADMIN", "11:00", "MÉXICO", "", "AEROMEXICO", "")
            ]
            cursor.executemany('''
                INSERT INTO vuelos (Pasajero, Origen, Destino, Estado, Costo, PNR, Equipaje, Extra, Fecha, Soporte, Usuario, Hora, Pais, Telefono, Aerolinea, Boleto_Ligado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', vuelos_demo)
            conn.commit()
            
    except sqlite3.Error as e:
        st.error(f"Error crítico en la base de datos: {e}")
    finally:
        conn.close()

def init_session_state():
    """Carga la configuración inicial de la sesión."""
    init_db()
    
    if not os.path.exists("attachments"):
        os.makedirs("attachments")

    # Manejo de autenticación vía URL o sesión
    if "logged_in" in st.query_params:
        st.session_state['autenticado'] = True
        if 'usuario' not in st.session_state or st.session_state['usuario'] is None:
            st.session_state['usuario'] = {
                "nombre": st.query_params.get("user", "USER"),
                "rol": st.query_params.get("rol", "ADMIN")
            }

    if 'autenticado' not in st.session_state:
        st.session_state['autenticado'] = False
    if 'usuario' not in st.session_state:
        st.session_state['usuario'] = None
    if 'logs' not in st.session_state:
        st.session_state['logs'] = []

    # Carga de datos optimizada
    try:
        conn = sqlite3.connect('logistics_v2.db')
        st.session_state['db_vuelos'] = pd.read_sql_query("SELECT * FROM vuelos WHERE deleted_at IS NULL", conn)
        conn.close()
    except:
        st.session_state['db_vuelos'] = pd.DataFrame()

# --- INICIALIZACIÓN ---
init_session_state()

# --- ESTILOS VISUALES (MODO DARK ENTERPRISE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif; 
        background-color: #000000; 
        color: #e5e7eb; 
    }
    
    .stApp { background: #000000; }
    
    /* Tabs personalizadas */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 30px; 
        border-bottom: 1px solid #1A1A1A; 
    }
    .stTabs [data-baseweb="tab"] { 
        background-color: transparent !important; 
        color: #666 !important; 
        letter-spacing: 1px; 
        font-size: 12px; 
        font-weight: 400;
    }
    .stTabs [aria-selected="true"] { 
        color: #00d4ff !important; 
        border-bottom: 2px solid #00d4ff !important; 
    }
    
    /* Botones estilo industrial */
    .stButton>button { 
        background: #0A0A0A; 
        border: 1px solid #333; 
        color: #AAA; 
        border-radius: 4px; 
        text-transform: uppercase; 
        letter-spacing: 1px; 
        font-size: 10px; 
        transition: 0.3s;
    }
    .stButton>button:hover { 
        border-color: #00d4ff; 
        color: #00d4ff; 
        background: #00d4ff11; 
    }
    
    /* Inputs */
    .stTextInput>div>div>input {
        background-color: #0A0A0A;
        color: #FFF;
        border: 1px solid #222;
    }
    </style>
""", unsafe_allow_html=True)

def main():
    if not st.session_state.autenticado:
        auth.show_login()
    else:
        # Mantener parámetros en URL
        st.query_params["logged_in"] = "true"
        if st.session_state.usuario:
            st.query_params["user"] = st.session_state.usuario.get("nombre", "USER")
            st.query_params["rol"] = st.session_state.usuario.get("rol", "ADMIN")

        # Navbar Superior
        c_nav1, c_nav2 = st.columns([9, 1])
        rol_user = st.session_state.usuario.get('rol', 'USER')
        c_nav1.markdown(f"""
            <div style='display: flex; align-items: center; gap: 20px;'>
                <h3 style='letter-spacing:4px; font-weight:300; font-size:16px; margin:0;'>LOGISTICS ENGINE // {rol_user}</h3>
                <span style='color: #444;'>|</span>
                <span style='color: #00d4ff; font-size: 10px; letter-spacing: 1px;'>{st.session_state.usuario.get('nombre').upper()}</span>
            </div>
        """, unsafe_allow_html=True)
        
        if c_nav2.button("SALIR", use_container_width=True):
            st.session_state.autenticado = False
            st.session_state.usuario = None
            st.query_params.clear()
            st.rerun()

        # Menú Principal
        tabs = st.tabs([
            "📈 DASHBOARD", 
            "📦 INVENTARIO", 
            "📝 REGISTRO", 
            "🤖 INTELIGENCIA", 
            # "🛡️ AUDITORÍA"
        ])
        
        with tabs[0]: dashboard.render()
        with tabs[1]: inventory.render()
        with tabs[2]: registrar.render()
        with tabs[3]: reporting.render()
        # with tabs[4]: audit.render() # Asegúrate de tener audit.py con la función render()

if __name__ == "__main__":
    main()