import streamlit as st
import extra_streamlit_components as cookie_manager

def get_manager():
    return cookie_manager.CookieManager()

def show_login():
    cookies = get_manager()
    st.markdown("<div style='height:100px'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    
    with c2:
        st.markdown("<h4 style='text-align:center; letter-spacing:5px; font-weight:300;'>AUTHORIZATION</h4>", unsafe_allow_html=True)
        user = st.text_input("USER_ID", placeholder="USER_ID")
        pw = st.text_input("ACCESS_KEY", type="password", placeholder="ACCESS_KEY")
        
        if st.button("EXEC_AUTH"):
            if (user == "admin" and pw == "1234") or (user == "operador" and pw == "5678"):
                rol = "ADMIN" if user == "admin" else "OPS"
                # GUARDAR COOKIE (Persiste tras F5)
                cookies.set("auth_token", f"{user}:{rol}", key="set_auth")
                
                st.session_state.autenticado = True
                st.session_state.usuario = {"rol": rol, "nombre": user.upper()}
                st.rerun()
            else:
                st.error("AUTH_FAILED")