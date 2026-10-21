import streamlit as st
import psycopg2
import hashlib
import pandas as pd
from datetime import date

# Configuración inicial de la página
st.set_page_config(page_title="ESAM Analytics", page_icon="📊", layout="wide")

# --- 1. SEGURIDAD Y BASE DE DATOS ---
def encriptar_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def obtener_conexion():
    db_url = st.secrets["postgres"]["url"]
    return psycopg2.connect(db_url)

def inicializar_tablas():
    try:
        conn = obtener_conexion()
        cursor = conn.cursor()
        
        # Tabla de usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                rol VARCHAR(20) NOT NULL
            );
        """)
        
        # Tabla de registros de juegos y ganancias
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS registros_juegos (
                id SERIAL PRIMARY KEY,
                usuario VARCHAR(50) NOT NULL,
                deporte VARCHAR(20) NOT NULL,
                fecha DATE NOT NULL,
                detalles VARCHAR(255),
                cantidad_picheos INT DEFAULT 0,
                ganancia NUMERIC(10, 4) NOT NULL
            );
        """)
        conn.commit()
        
        # Crear usuario admin por defecto si no existe
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
        st.error(f"Error inicializando tablas en la base de datos: {e}")

# Ejecutar inicialización de tablas
inicializar_tablas()

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
        
    # --- VISTA 1: DASHBOARD UNIFICADO ---
    if menu_seleccionado == "Dashboard Unificado":
        st.title("📊 Panel Principal - Ganancias y Métricas Unificadas")
        st.write("Vista simultánea del desempeño y ganancias de Béisbol y Básquetbol.")
        
        # Consultar métricas reales desde la base de datos
        try:
            conn = obtener_conexion()
            query = "SELECT deporte, COALESCE(SUM(ganancia), 0), COUNT(*) FROM registros_juegos GROUP BY deporte;"
            df_totales = pd.read_sql(query, conn)
            conn.close()
            
            ganancia_beisbol = 0.0
            juegos_beisbol = 0
            ganancia_basket = 0.0
            juegos_basket = 0
            
            for _, row in df_totales.iterrows():
                if row['deporte'] == 'Béisbol':
                    ganancia_beisbol = float(row['coalesce'])
                    juegos_beisbol = int(row['count'])
                elif row['deporte'] == 'Básquetbol':
                    ganancia_basket = float(row['coalesce'])
                    juegos_basket = int(row['count'])
            
            total_acumulado = ganancia_beisbol + ganancia_basket
            
            # Tarjetas métricas
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                st.metric(label="⚾ Béisbol (Ganancias)", value=f"${ganancia_beisbol:.2f}", delta=f"{juegos_beisbol} registros")
            with col_b2:
                st.metric(label="🏀 Básquetbol (Ganancias)", value=f"${ganancia_basket:.2f}", delta=f"{juegos_basket} registros")
            with col_b3:
                st.metric(label="💰 Total Acumulado", value=f"${total_acumulado:.2f}", delta="General")
                
            st.divider()
            st.subheader("Historial de Actividad Reciente")
            
            # Mostrar tabla de registros
            conn = obtener_conexion()
            df_historial = pd.read_sql("SELECT usuario, deporte, fecha, detalles, cantidad_picheos, ganancia FROM registros_juegos ORDER BY id DESC LIMIT 15;", conn)
            conn.close()
            
            if not df_historial.empty:
                st.dataframe(df_historial, use_container_width=True)
            else:
                st.info("Aún no hay registros guardados. Utiliza el módulo de 'Registro de Actividad' para agregar juegos.")
                
        except Exception as e:
            st.error(f"Error al cargar las métricas: {e}")

    # --- VISTA 2: REGISTRO DE ACTIVIDAD ---
    elif menu_seleccionado == "Registro de Actividad":
        st.title("📝 Módulo de Registro de Juegos")
        st.write("Registra tus análisis de Béisbol (calculado por picheos a $0.024) o Básquetbol.")
        
        tab_beisbol, tab_basket = st.tabs(["⚾ Registrar Béisbol", "🏀 Registrar Básquetbol"])
        
        with tab_beisbol:
            st.subheader("Registro de Béisbol (Tarifa: $0.024 / picheo)")
            with st.form("form_beisbol"):
                fecha_b = st.date_input("Fecha del juego", value=date.today(), key="fb")
                detalles_b = st.text_input("Detalles / Equipos / ID del juego", key="db")
                picheos_b = st.number_input("Cantidad de Picheos analizados", min_value=0, step=1, key="pb")
                btn_guardar_b = st.form_submit_button("Guardar Registro de Béisbol")
                
                if btn_guardar_b:
                    if picheos_b > 0:
                        ganancia_calc = picheos_b * 0.024
                        try:
                            conn = obtener_conexion()
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO registros_juegos (usuario, deporte, fecha, detalles, cantidad_picheos, ganancia) VALUES (%s, %s, %s, %s, %s, %s);",
                                (st.session_state.usuario, "Béisbol", fecha_b, detalles_b, picheos_b, ganancia_calc)
                            )
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.success(f"¡Registro guardado con éxito! Ganancia calculada: ${ganancia_calc:.4f}")
                        except Exception as e:
                            st.error(f"Error al guardar en la base de datos: {e}")
                    else:
                        st.error("La cantidad de picheos debe ser mayor a 0.")
                        
        with tab_basket:
            st.subheader("Registro de Básquetbol (Synergy Sports)")
            with st.form("form_basket"):
                fecha_k = st.date_input("Fecha del juego", value=date.today(), key="fk")
                detalles_k = st.text_input("Detalles / Equipos / ID del juego", key="dk")
                tarifa_k = st.number_input("Ganancia fija por juego ($)", min_value=0.0, value=0.0, step=0.5, key="tk")
                btn_guardar_k = st.form_submit_button("Guardar Registro de Básquetbol")
                
                if btn_guardar_k:
                    if tarifa_k >= 0:
                        try:
                            conn = obtener_conexion()
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO registros_juegos (usuario, deporte, fecha, detalles, cantidad_picheos, ganancia) VALUES (%s, %s, %s, %s, %s, %s);",
                                (st.session_state.usuario, "Básquetbol", fecha_k, detalles_k, 0, tarifa_k)
                            )
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.success(f"¡Registro de básquetbol guardado con éxito! Ganancia: ${tarifa_k:.2f}")
                        except Exception as e:
                            st.error(f"Error al guardar en la base de datos: {e}")
                    else:
                        st.error("Por favor ingresa un monto válido.")

    # --- VISTA 3: GESTIÓN DE USUARIOS (ADMIN) ---
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
