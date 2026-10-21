import streamlit as st
import psycopg2
import hashlib

# Configuración inicial de la página
st.set_page_config(page_title="ESAM Analytics", page_icon="📊", layout="wide")

# --- 1. SEGURIDAD Y BASE DE DATOS ---
def encriptar_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def obtener_conexion():
    db_url = st.secrets["postgres"]["url"]
    return psycopg2.connect(db_url)

def inicializar_tabla_usuarios():
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        
        # Eliminar temporalmente la tabla si tiene una estructura incompatible y recrearla limpia
        # (Esto asegura que las columnas username, password y rol existan exactamente)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                rol VARCHAR(20) NOT NULL
            );
        """)
        conn.commit()
        
        # Verificar si ya existe el usuario admin por defecto
        cursor.execute("SELECT COUNT(*) FROM usuarios WHERE username = 'admin';")
        count = cursor.fetchone()[0]
        if count == 0:
            pass_inicial = encriptar_password("admin123")
            cursor.execute(
                "INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s);",
                ("admin", pass_inicial, "admin")
            )
            conn.commit()
            
        cursor.close()
        conn.close()
    except Exception as e:
        st.error(f"Error en la base de datos de usuarios: {e}")

# Ejecutar inicialización
inicializar_tabla_usuarios()

# --- 2. CONTROL DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = None
    st.session_state.rol = None

# --- 3. PANTALLA DE LOGIN ---
if not st.session_state.autenticado:
    st.markdown("<h1 style='text-align: center;'>🔐 ESAM Analytics</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align: center; color: gray;'>Sistema de Gestión y Análisis Multideporte</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Iniciar Sesión", use_container_width=True)
            
            if submit_login:
                try:
                    conn = obtener_conexion()
                    cursor = conn.cursor()
                    cursor.execute("SELECT password, rol FROM usuarios WHERE username = %s;", (user_input,))
                    resultado = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    if resultado and resultado[0] == encriptar_password(pass_input):
                        st.session_state.autenticado = True
                        st.session_state.usuario = user_input
                        st.session_state.rol = resultado[1]
                        st.success("¡Acceso concedido!")
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                except Exception as e:
                    st.error(f"Error al verificar credenciales: {e}")
else:
    # --- 4. APLICACIÓN PRINCIPAL ---
    st.sidebar.title("⚡ ESAM Analytics")
    st.sidebar.write(f"Usuario: **{st.session_state.usuario}**")
    st.sidebar.write(f"Rol: **{st.session_state.rol}**")
    st.sidebar.divider()
    
    menu_opciones = ["Dashboard Unificado", "Registro de Actividad"]
    
    if st.session_state.rol == "admin":
        menu_opciones.append("Gestión de Usuarios (Admin)")
        
    menu_seleccionado = st.sidebar.radio("Navegación", menu_opciones)
    
    if st.sidebar.button("Cerrar Sesión", use_container_width=True):
        st.session_state.autenticado = False
        st.session_state.usuario = None
        st.session_state.rol = None
        st.rerun()
        
    if menu_seleccionado == "Dashboard Unificado":
        st.title("📊 Panel Principal - Ganancias y Métricas Unificadas")
        st.write("Vista simultánea del desempeño y ganancias de Béisbol y Básquetbol.")
        
        col_b1, col_b2, col_b3 = st.columns(3)
        with col_b1:
            st.metric(label="⚾ Béisbol (Ganancias)", value="$0.00", delta="0 juegos")
        with col_b2:
            st.metric(label="🏀 Básquetbol (Ganancias)", value="$0.00", delta="0 juegos")
        with col_b3:
            st.metric(label="💰 Total Acumulado", value="$0.00", delta="General")
            
        st.divider()
        st.info("💡 Este panel refleja en tiempo real el acumulado de ambas disciplinas.")

    elif menu_seleccionado == "Registro de Actividad":
        st.title("📝 Módulo de Registro")
        st.write("Aquí puedes registrar los análisis de juegos diarios para ambas disciplinas.")

    elif menu_seleccionado == "Gestión de Usuarios (Admin)":
        st.title("⚙️ Administración de Accesos y Contraseñas")
        st.write("Herramienta exclusiva del Administrador para gestionar cuentas y restablecer credenciales.")
        
        tab_cambio, tab_crear = st.tabs(["Cambiar / Restablecer Contraseña", "Crear Nuevo Usuario"])
        
        with tab_cambio:
            st.subheader("Restablecer Contraseña")
            try:
                conn = obtener_conexion()
                cursor = conn.cursor()
                cursor.execute("SELECT username FROM usuarios;")
                usuarios_lista = [row[0] for row in cursor.fetchall()]
                cursor.close()
                conn.close()
                
                with st.form("form_cambio_pass"):
                    usuario_a_cambiar = st.selectbox("Selecciona el usuario", usuarios_lista)
                    nueva_pass = st.text_input("Nueva contraseña", type="password")
                    confirmar_pass = st.text_input("Confirma la nueva contraseña", type="password")
                    btn_actualizar = st.form_submit_button("Actualizar Contraseña")
                    
                    if btn_actualizar:
                        if nueva_pass == confirmar_pass and nueva_pass != "":
                            conn = obtener_conexion()
                            cursor = conn.cursor()
                            cursor.execute(
                                "UPDATE usuarios SET password = %s WHERE username = %s;",
                                (encriptar_password(nueva_pass), usuario_a_cambiar)
                            )
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.success(f"¡Contraseña actualizada con éxito para el usuario '{usuario_a_cambiar}'!")
                        else:
                            st.error("Las contraseñas no coinciden o el campo está vacío.")
            except Exception as e:
                st.error(f"Error al cargar la lista de usuarios: {e}")
                
        with tab_crear:
            st.subheader("Crear Cuenta de Usuario Nueva")
            with st.form("form_crear_usuario"):
                nuevo_user = st.text_input("Nombre de usuario nuevo")
                nueva_pass_user = st.text_input("Contraseña inicial", type="password")
                rol_user = st.selectbox("Rol en el sistema", ["analista", "admin"])
                btn_crear = st.form_submit_button("Registrar Usuario")
                
                if btn_crear:
                    if nuevo_user and nueva_pass_user:
                        try:
                            conn = obtener_conexion()
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO usuarios (username, password, rol) VALUES (%s, %s, %s);",
                                (nuevo_user, encriptar_password(nueva_pass_user), rol_user)
                            )
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.success(f"¡Usuario '{nuevo_user}' creado exitosamente!")
                        except Exception:
                            st.error("El nombre de usuario ya existe en la base de datos.")
                    else:
                        st.error("Por favor completa todos los campos.")
