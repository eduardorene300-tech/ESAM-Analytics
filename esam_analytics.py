from datetime import date, datetime, timedelta
import hashlib
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st

# =========================================================
# 1. CONFIGURACIÓN GENERAL DE LA PÁGINA
# =========================================================
st.set_page_config(
    page_title="ESAM Analytics",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos visuales modernos (Tema oscuro deportivo profesional)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&family=Barlow:wght@300;400;500;600&display=swap');
*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stAppViewContainer"] {
    background: #030810 !important; color: #E8EFF8 !important;
    font-family: 'Barlow', sans-serif !important; }
[data-testid="stSidebar"] { background: #030810 !important; border-right: 1px solid #0D2040 !important; }
[data-testid="stSidebar"] * { color: #CBD5E0 !important; }
.stButton > button {
    background: linear-gradient(135deg, #00AAFF, #0077CC) !important;
    color: white !important; font-family: 'Rajdhani', sans-serif !important;
    font-weight: 700 !important; font-size: 0.9rem !important;
    letter-spacing: 0.08em !important; border: none !important;
    border-radius: 8px !important; transition: all 0.2s ease !important; }
.stButton > button:hover { transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(0,170,255,0.4) !important; }
.stTextInput > div > div > input, .stNumberInput > div > div > input,
.stSelectbox > div > div, .stTextArea textarea {
    background: #0A1628 !important; border: 1px solid #0D2040 !important;
    border-radius: 8px !important; color: #E8EFF8 !important; }
[data-testid="stDataFrame"] { background: #0A1628 !important; border-radius: 12px !important; }
.stTabs [data-baseweb="tab-list"] { background: #0A1628 !important; border-radius: 10px !important; padding: 4px !important; }
.stTabs [data-baseweb="tab"] { background: transparent !important; color: #7A90A8 !important;
    font-family: 'Rajdhani', sans-serif !important; font-weight: 600 !important;
    border-radius: 7px !important; border: none !important; }
.stTabs [aria-selected="true"] { background: #00AAFF !important; color: white !important; }
[data-testid="stMetric"] { background: #0A1628 !important; border: 1px solid #0D2040 !important;
    border-radius: 14px !important; padding: 1.2rem 1.5rem !important; }
[data-testid="stMetricLabel"] { font-family: 'Rajdhani', sans-serif !important;
    font-size: 0.78rem !important; letter-spacing: 0.12em !important;
    color: #7A90A8 !important; font-weight: 600 !important; }
[data-testid="stMetricValue"] { font-family: 'Rajdhani', sans-serif !important;
    font-size: 2.4rem !important; font-weight: 700 !important; color: #00AAFF !important; }
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# =========================================================
# 2. SEGURIDAD Y ENCRIPTACIÓN (SHA-256)
# =========================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# =========================================================
# 3. CONEXIÓN A BASE DE DATOS (NEON POSTGRESQL)
# =========================================================
def get_db_connection():
    try:
        if "postgres" not in st.secrets or "url" not in st.secrets["postgres"]:
            st.error("❌ Error de configuración: La clave '[postgres]' o 'url' no existe en los secretos de Streamlit.")
            return None
        return psycopg2.connect(st.secrets["postgres"]["url"])
    except Exception as e:
        st.error(f"❌ Error de conexión a Neon PostgreSQL: {e}")
        return None


# =========================================================
# 4. INICIALIZACIÓN DE TABLAS GLOBALES
# =========================================================
@st.cache_resource
def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # Tabla de Usuarios unificada
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    nombre VARCHAR(100) NOT NULL,
                    password_hash VARCHAR(64) NOT NULL,
                    rol VARCHAR(30) DEFAULT 'operador',
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Tabla de Partidos (Básquetbol)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS partidos (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
                    codigo_partido VARCHAR(50) NOT NULL,
                    fecha DATE NOT NULL,
                    tiempo_ejecucion VARCHAR(30),
                    tarifa NUMERIC(10, 2) DEFAULT 0.00,
                    tipo_partido VARCHAR(30) DEFAULT 'quincenal',
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Tabla de Picheos (Béisbol)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS picheos (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
                    fecha DATE NOT NULL,
                    id_control VARCHAR(50) NOT NULL,
                    cantidad INTEGER NOT NULL,
                    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Tabla de Configuración Global de Tarifas / Precios
            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracion_global (
                    clave VARCHAR(50) PRIMARY KEY,
                    valor NUMERIC(10, 4) NOT NULL
                );
            """)

            # Valores por defecto
            defaults = [
                ("tasa_tramo_1", 6.00),
                ("tasa_tramo_2", 6.50),
                ("tasa_tramo_3", 7.00),
                ("tasa_tramo_4", 8.00),
                ("tasa_en_vivo_normal", 12.00),
                ("tasa_en_vivo_nba", 18.50),
                ("precio_beisbol", 0.024),
            ]
            for clave, val in defaults:
                cur.execute("""
                    INSERT INTO configuracion_global (clave, valor) 
                    VALUES (%s, %s) 
                    ON CONFLICT (clave) DO NOTHING;
                """, (clave, val))

            # Crear usuario admin por defecto si no existe
            admin_hash = hash_password("admin123")
            cur.execute("""
                INSERT INTO usuarios (username, nombre, password_hash, rol)
                VALUES ('admin', 'Administrador Global', %s, 'admin')
                ON CONFLICT (username) DO NOTHING;
            """, (admin_hash,))

            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            st.error(f"❌ Error al inicializar tablas: {e}")
            return False
    return False

init_db()


# =========================================================
# 5. FUNCIONES DE CONFIGURACIÓN Y TARIFAS
# =========================================================
def obtener_tasas_globales():
    conn = get_db_connection()
    tasas = {
        "tramo_1": 6.00,
        "tramo_2": 6.50,
        "tramo_3": 7.00,
        "tramo_4": 8.00,
        "en_vivo_normal": 12.00,
        "en_vivo_nba": 18.50,
        "precio_beisbol": 0.024,
    }
    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT clave, valor FROM configuracion_global;")
            rows = cur.fetchall()
            for r in rows:
                k = r["clave"]
                val = float(r["valor"])
                if k == "tasa_tramo_1": tasas["tramo_1"] = val
                elif k == "tasa_tramo_2": tasas["tramo_2"] = val
                elif k == "tasa_tramo_3": tasas["tramo_3"] = val
                elif k == "tasa_tramo_4": tasas["tramo_4"] = val
                elif k == "tasa_en_vivo_normal": tasas["en_vivo_normal"] = val
                elif k == "tasa_en_vivo_nba": tasas["en_vivo_nba"] = val
                elif k == "precio_beisbol": tasas["precio_beisbol"] = val
            cur.close()
            conn.close()
        except Exception:
            pass
    return tasas


def actualizar_tasa_global(clave, nuevo_valor):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("UPDATE configuracion_global SET valor = %s WHERE clave = %s;", (nuevo_valor, clave))
            conn.commit()
            cur.close()
            conn.close()
            return True
        except Exception as e:
            st.error(f"Error al actualizar tasa: {e}")
            return False
    return False


def obtener_tarifa_basket(tipo_partido, cant_partidos=0):
    tasas = obtener_tasas_globales()
    if tipo_partido == "en_vivo_nba":
        return tasas["en_vivo_nba"]
    elif tipo_partido == "en_vivo_normal":
        return tasas["en_vivo_normal"]
    else:
        if cant_partidos <= 11: return tasas["tramo_1"]
        elif cant_partidos <= 14: return tasas["tramo_2"]
        elif cant_partidos <= 29: return tasas["tramo_3"]
        else: return tasas["tramo_4"]


# =========================================================
# 6. GESTIÓN DE USUARIOS Y AUTENTICACIÓN
# =========================================================
def registrar_usuario(username, nombre, password, rol="operador"):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            pwd_hash = hash_password(password)
            cur.execute("""
                INSERT INTO usuarios (username, nombre, password_hash, rol)
                VALUES (%s, %s, %s, %s);
            """, (username.lower().strip(), nombre.strip(), pwd_hash, rol))
            conn.commit()
            cur.close()
            conn.close()
            return True, "✅ Usuario registrado exitosamente."
        except psycopg2.IntegrityError:
            return False, "⚠️ El nombre de usuario ya existe."
        except Exception as e:
            return False, f"❌ Error en registro: {e}"
    return False, "❌ Error de conexión a BD."


def autenticar_usuario(username, password):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            pwd_hash = hash_password(password)
            cur.execute("""
                SELECT id, username, nombre, rol FROM usuarios
                WHERE username = %s AND password_hash = %s;
            """, (username.lower().strip(), pwd_hash))
            user = cur.fetchone()
            cur.close()
            conn.close()
            return user
        except Exception as e:
            st.error(f"Error al autenticar: {e}")
            return None
    return None


def cambiar_contrasena(user_id, nueva_password):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            pwd_hash = hash_password(nueva_password)
            cur.execute("UPDATE usuarios SET password_hash = %s WHERE id = %s;", (pwd_hash, user_id))
            conn.commit()
            cur.close()
            conn.close()
            return True, "✅ Contraseña actualizada correctamente."
        except Exception as e:
            return False, f"❌ Error al actualizar contraseña: {e}"
    return False, "❌ Error de conexión a BD."


def restablecer_contrasena_admin(username, nueva_password):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            pwd_hash = hash_password(nueva_password)
            cur.execute("UPDATE usuarios SET password_hash = %s WHERE username = %s;", (pwd_hash, username.lower().strip()))
            conn.commit()
            filas_afectadas = cur.rowcount
            cur.close()
            conn.close()
            if filas_afectadas > 0:
                return True, "✅ Contraseña restablecida exitosamente."
            else:
                return False, "⚠️ El nombre de usuario no existe."
        except Exception as e:
            return False, f"❌ Error al restablecer: {e}"
    return False, "❌ Error de conexión a BD."


def obtener_todos_los_usuarios():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        query = """
            SELECT u.id, u.username, u.nombre, u.rol, u.creado_en,
                   COUNT(DISTINCT p.id) as total_partidos_basket,
                   COUNT(DISTINCT pi.id) as total_picheos_beisbol
            FROM usuarios u
            LEFT JOIN partidos p ON u.id = p.usuario_id
            LEFT JOIN picheos pi ON u.id = pi.usuario_id
            GROUP BY u.id, u.username, u.nombre, u.rol, u.creado_en
            ORDER BY u.id ASC;
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error al cargar usuarios: {e}")
        return pd.DataFrame()


def obtener_rango_quincena(fecha_ref):
    if fecha_ref.day <= 15:
        inicio_q = date(fecha_ref.year, fecha_ref.month, 1)
        fin_q = date(fecha_ref.year, fecha_ref.month, 15)
    else:
        inicio_q = date(fecha_ref.year, fecha_ref.month, 16)
        if fecha_ref.month == 12:
            fin_q = date(fecha_ref.year, 12, 31)
        else:
            fin_q = date(fecha_ref.year, fecha_ref.month + 1, 1) - timedelta(days=1)
    return inicio_q, fin_q


# =========================================================
# 7. MANEJO DE SESIÓN Y LOGIN
# =========================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

if not st.session_state.authenticated:
    st.title("🏆 ESAM Analytics")
    st.caption("Plataforma Profesional de Análisis y Control Operativo (Básquetbol & Béisbol)")

    tab_login, tab_registro, tab_recuperar = st.tabs(["🔑 Iniciar Sesión", "📝 Registrar Usuario", "🔄 Recuperar Contraseña"])

    with tab_login:
        st.subheader("Ingreso de Operadores")
        with st.form("form_login"):
            user_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Entrar a ESAM Analytics", use_container_width=True)

            if submit_login:
                if user_input and pass_input:
                    user_data = autenticar_usuario(user_input, pass_input)
                    if user_data:
                        st.session_state.authenticated = True
                        st.session_state.user_info = user_data
                        st.success(f"Bienvenido/a, {user_data['nombre']}")
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                else:
                    st.warning("Complete todos los campos.")

    with tab_registro:
        st.subheader("Crear Cuenta de Operador")
        with st.form("form_registro"):
            reg_name = st.text_input("Nombre Completo")
            reg_user = st.text_input("Nombre de Usuario")
            reg_pass1 = st.text_input("Contraseña", type="password")
            reg_pass2 = st.text_input("Confirmar Contraseña", type="password")
            submit_reg = st.form_submit_button("Registrar Cuenta", use_container_width=True)

            if submit_reg:
                if not (reg_name and reg_user and reg_pass1 and reg_pass2):
                    st.warning("Todos los campos son obligatorios.")
                elif reg_pass1 != reg_pass2:
                    st.error("Las contraseñas no coinciden.")
                elif len(reg_pass1) < 6:
                    st.error("La contraseña debe tener al menos 6 caracteres.")
                else:
                    exito, msg = registrar_usuario(reg_user, reg_name, reg_pass1, "operador")
                    if exito: st.success(msg)
                    else: st.error(msg)

    with tab_recuperar:
        st.subheader("Restablecer Contraseña")
        st.info("Si olvidaste tu contraseña, ingresa tu usuario y establece una nueva clave directamente.")
        with st.form("form_recuperar_pass"):
            rec_user = st.text_input("Nombre de Usuario")
            rec_pass1 = st.text_input("Nueva Contraseña", type="password")
            rec_pass2 = st.text_input("Confirmar Nueva Contraseña", type="password")
            submit_rec = st.form_submit_button("Actualizar Contraseña", use_container_width=True)

            if submit_rec:
                if not (rec_user and rec_pass1 and rec_pass2):
                    st.warning("Complete todos los campos.")
                elif rec_pass1 != rec_pass2:
                    st.error("Las contraseñas no coinciden.")
                elif len(rec_pass1) < 6:
                    st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                else:
                    exito, msg = restablecer_contrasena_admin(rec_user, rec_pass1)
                    if exito: st.success(msg)
                    else: st.error(msg)
else:
    # =========================================================
    # PANEL PRINCIPAL Y NAVEGACIÓN ENTRE DEPORTES Y GESTIÓN
    # =========================================================
    user_id = st.session_state.user_info["id"]
    user_name = st.session_state.user_info["nombre"]
    username_actual = st.session_state.user_info["username"].lower().strip()
    rol_actual = st.session_state.user_info.get("rol", "operador")

    es_admin_base = (username_actual == "admin") or (rol_actual == "admin")

    st.sidebar.title("🏆 ESAM Analytics")
    st.sidebar.write(f"👤 **Analista:** {user_name}")
    
    # ── SELECTOR PRINCIPAL DE SECCIÓN / DEPORTE ──
    st.sidebar.markdown("---")
    deporte_sel = st.sidebar.selectbox(
        "🎯 Seleccionar Sección:",
        ["🏠 Pantalla Principal (Ganancias)", "🏀 Básquetbol", "⚾ Béisbol", "🔑 Cambiar Contraseña"]
    )

    st.sidebar.markdown("---")
    modo_super_admin = st.sidebar.checkbox("👑 Activar Modo Admin Global", value=es_admin_base)
    es_admin = es_admin_base or modo_super_admin

    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_info = None
        st.rerun()

    # =========================================================
    # MÓDULO 0: PANTALLA PRINCIPAL (RESUMEN DE GANANCIAS)
    # =========================================================
    if "Pantalla Principal" in deporte_sel:
        st.title("🏠 ESAM Analytics — Panel General de Ganancias")
        st.caption(f"Resumen Consolidado de Rendimiento y Ganancias (Básquetbol y Béisbol) | Operador: {user_name}")

        # Filtro de fecha general para la pantalla principal
        col_f1, col_f2, col_f3 = st.columns([2, 2, 2])
        with col_f1:
            filtro_gen_tipo = st.selectbox("Período de Análisis:", ["Este Mes", "Esta Quincena", "Últimos 30 Días", "Histórico Total"])
        
        hoy = date.today()
        if filtro_gen_tipo == "Este Mes":
            f_ini_g = date(hoy.year, hoy.month, 1)
            f_fin_g = hoy
        elif filtro_gen_tipo == "Esta Quincena":
            f_ini_g, f_fin_g = obtener_rango_quincena(hoy)
        elif filtro_gen_tipo == "Últimos 30 Días":
            f_ini_g = hoy - timedelta(days=30)
            f_fin_g = hoy
        else:
            f_ini_g = date(2020, 1, 1)
            f_fin_g = date(2035, 12, 31)

        # Consultar ganancias de Básquetbol
        conn_g = get_db_connection()
        total_g_basket = 0.0
        total_p_basket = 0
        total_g_beisbol = 0.0
        total_p_beisbol = 0
        precio_pich_g = obtener_tasas_globales()["precio_beisbol"]

        if conn_g:
            try:
                cur_g = conn_g.cursor()
                # Sumar básquetbol
                if es_admin:
                    cur_g.execute("SELECT COALESCE(SUM(tarifa), 0), COUNT(*) FROM partidos WHERE fecha BETWEEN %s AND %s;", (f_ini_g, f_fin_g))
                else:
                    cur_g.execute("SELECT COALESCE(SUM(tarifa), 0), COUNT(*) FROM partidos WHERE usuario_id = %s AND fecha BETWEEN %s AND %s;", (user_id, f_ini_g, f_fin_g))
                res_b = cur_g.fetchone()
                total_g_basket = float(res_b[0])
                total_p_basket = int(res_b[1])

                # Sumar béisbol
                if es_admin:
                    cur_g.execute("SELECT COALESCE(SUM(cantidad), 0) FROM picheos WHERE fecha BETWEEN %s AND %s;", (f_ini_g, f_fin_g))
                else:
                    cur_g.execute("SELECT COALESCE(SUM(cantidad), 0) FROM picheos WHERE usuario_id = %s AND fecha BETWEEN %s AND %s;", (user_id, f_ini_g, f_fin_g))
                res_be = cur_g.fetchone()
                total_p_beisbol = int(res_be[0])
                total_g_beisbol = total_p_beisbol * precio_pich_g

                cur_g.close()
                conn_g.close()
            except Exception as e:
                st.error(f"Error al calcular resumen: {e}")

        gran_total_ganancias = total_g_basket + total_g_beisbol

        st.markdown("### 💵 Métricas Consolidadas")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🏆 Ganancias Totales", f"${gran_total_ganancias:,.2f}")
        m2.metric("🏀 Ganancias Básquetbol", f"${total_g_basket:,.2f}", f"{total_p_basket} partidos")
        m3.metric("⚾ Ganancias Béisbol", f"${total_g_beisbol:,.2f}", f"{total_p_beisbol:,} picheos")
        m4.metric("📅 Período", f"{f_ini_g} al {f_fin_g}")

        st.markdown("---")
        st.subheader("📊 Desglose Comparativo de Rendimiento por Deporte")
        
        df_resumen_bar = pd.DataFrame({
            "Deporte": ["Básquetbol", "Béisbol"],
            "Ganancias (USD)": [total_g_basket, total_g_beisbol]
        })
        st.bar_chart(df_resumen_bar.set_index("Deporte"))

        st.info("💡 Consejo: Puedes cambiarte al módulo específico de Básquetbol o Béisbol en el menú lateral para registrar nuevos partidos, lotes de picheos o exportar reportes detallados en CSV.")

    # =========================================================
    # MÓDULO 1: BÁSQUETBOL
    # =========================================================
    elif "Básquetbol" in deporte_sel:
        st.title("🏀 ESAM Analytics — Módulo Básquetbol")
        st.caption(f"Operador: {user_name} | Control Financiero y Tiempos de Partidos")

        if es_admin:
            sub_vista_admin = st.sidebar.radio("🧭 Navegación Básquetbol:", ["📊 Panel de Partidos", "👑 Administración Global Tasas"])
        else:
            sub_vista_admin = "📊 Panel de Partidos"

        if es_admin and sub_vista_admin == "👑 Administración Global Tasas":
            st.subheader("⚙️ Configuración Global de Tarifas de Básquetbol")
            tasas_v = obtener_tasas_globales()
            with st.form("form_tasas_basket"):
                c1, c2, c3, c4 = st.columns(4)
                with c1: nt1 = st.number_input("Tramo 1 (1-11)", value=tasas_v["tramo_1"], step=0.25)
                with c2: nt2 = st.number_input("Tramo 2 (12-14)", value=tasas_v["tramo_2"], step=0.25)
                with c3: nt3 = st.number_input("Tramo 3 (15-29)", value=tasas_v["tramo_3"], step=0.25)
                with c4: nt4 = st.number_input("Tramo 4 (30+)", value=tasas_v["tramo_4"], step=0.25)

                cv1, cv2 = st.columns(2)
                with cv1: nv_norm = st.number_input("En Vivo Normal ($)", value=tasas_v["en_vivo_normal"], step=0.50)
                with cv2: nv_nba = st.number_input("En Vivo NBA ($)", value=tasas_v["en_vivo_nba"], step=0.50)

                if st.form_submit_button("💾 Guardar Cambios"):
                    actualizar_tasa_global("tasa_tramo_1", nt1)
                    actualizar_tasa_global("tasa_tramo_2", nt2)
                    actualizar_tasa_global("tasa_tramo_3", nt3)
                    actualizar_tasa_global("tasa_tramo_4", nt4)
                    actualizar_tasa_global("tasa_en_vivo_normal", nv_norm)
                    actualizar_tasa_global("tasa_en_vivo_nba", nv_nba)
                    st.success("✅ Tarifas actualizadas correctamente.")
                    st.rerun()

            st.markdown("---")
            st.subheader("👥 Listado de Todos los Usuarios del Sistema")
            df_usr_all = obtener_todos_los_usuarios()
            if not df_usr_all.empty:
                st.dataframe(df_usr_all, use_container_width=True, hide_index=True)
        else:
            st.sidebar.markdown("---")
            st.sidebar.subheader("🔍 Filtros de Búsqueda")
            filtro_b_tipo = st.sidebar.selectbox("Filtrar por:", ["Rango de Fechas Personalizado", "Esta Quincena", "Hoy", "Este Mes", "Todos"], key="b_filtro_sel")

            if filtro_b_tipo == "Rango de Fechas Personalizado":
                col_fd1, col_fd2 = st.sidebar.columns(2)
                with col_fd1: f_ini = st.date_input("Desde", value=date.today() - timedelta(days=15), key="b_f_ini")
                with col_fd2: f_fin = st.date_input("Hasta", value=date.today(), key="b_f_fin")
            elif filtro_b_tipo == "Hoy":
                f_ini = f_fin = date.today()
            elif filtro_b_tipo == "Esta Quincena":
                f_ini, f_fin = obtener_rango_quincena(date.today())
            elif filtro_b_tipo == "Este Mes":
                f_ini = date(date.today().year, date.today().month, 1)
                f_fin = date.today()
            else:
                f_ini = date(2020, 1, 1)
                f_fin = date(2035, 12, 31)

            with st.expander("➕ Registrar Nuevo Partido de Básquetbol", expanded=False):
                col_m1, _ = st.columns([2, 2])
                with col_m1:
                    modalidad_sel = st.radio("Modalidad:", ["🏀 Quincenal Estándar", "⚡ En Vivo Normal", "🔥 En Vivo NBA"])

                cf1, cf2, cf3 = st.columns(3)
                with cf1: fecha_p = st.date_input("Fecha", value=date.today(), key="b_fecha")
                with cf2: codigo_p = st.text_input("Código de Partido", placeholder="Ej: 1042")
                with cf3: tiempo_p = st.text_input("Tiempo Ejecución", placeholder="HH:MM:SS")

                tasas_v = obtener_tasas_globales()
                if "NBA" in modalidad_sel:
                    t_guardar = "en_vivo_nba"
                    tarifa_calc = tasas_v["en_vivo_nba"]
                elif "Normal" in modalidad_sel:
                    t_guardar = "en_vivo_normal"
                    tarifa_calc = tasas_v["en_vivo_normal"]
                else:
                    t_guardar = "quincenal"
                    iq_i, iq_f = obtener_rango_quincena(fecha_p)
                    conn_c = get_db_connection()
                    cnt_q = 0
                    if conn_c:
                        cur_c = conn_c.cursor()
                        cur_c.execute("SELECT COUNT(*) FROM partidos WHERE usuario_id=%s AND fecha >= %s AND fecha <= %s AND (tipo_partido IS NULL OR tipo_partido='quincenal')", (user_id, iq_i, iq_f))
                        cnt_q = cur_c.fetchone()[0]
                        cur_c.close()
                        conn_c.close()
                    tarifa_calc = obtener_tarifa_basket("quincenal", cnt_q + 1)

                if st.button("💾 Guardar Partido", use_container_width=True):
                    if not codigo_p.strip():
                        st.warning("Ingrese el código del partido.")
                    else:
                        conn_s = get_db_connection()
                        if conn_s:
                            cur_s = conn_s.cursor()
                            cur_s.execute("""
                                INSERT INTO partidos (usuario_id, codigo_partido, fecha, tiempo_ejecucion, tarifa, tipo_partido)
                                VALUES (%s, %s, %s, %s, %s, %s);
                            """, (user_id, codigo_p.strip(), fecha_p, tiempo_p.strip(), tarifa_calc, t_guardar))
                            conn_s.commit()
                            cur_s.close()
                            conn_s.close()
                            st.success("✅ Partido guardado exitosamente.")
                            st.rerun()

            conn_q = get_db_connection()
            if conn_q:
                df_basket = pd.read_sql_query("""
                    SELECT id, codigo_partido, fecha, tiempo_ejecucion, tarifa, tipo_partido 
                    FROM partidos 
                    WHERE usuario_id = %s AND fecha BETWEEN %s AND %s
                    ORDER BY fecha DESC, id DESC;
                """, conn_q, params=(user_id, f_ini, f_fin))
                conn_q.close()
            else:
                df_basket = pd.DataFrame()

            st.markdown(f"### 📋 Registros de Básquetbol ({f_ini} al {f_fin})")
            if not df_basket.empty:
                total_ganancias = df_basket["tarifa"].astype(float).sum()
                col_k1, col_k2, col_k3 = st.columns(3)
                col_k1.metric("🏀 Total Partidos", len(df_basket))
                col_k2.metric("💵 Total Ganancias", f"${total_ganancias:.2f}")
                col_k3.metric("📅 Rango", f"{f_ini} al {f_fin}")

                st.dataframe(df_basket, use_container_width=True, hide_index=True)

                csv_b = df_basket.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Exportar Reporte de Básquetbol (CSV)",
                    data=csv_b,
                    file_name=f"esam_basket_{f_ini}_al_{f_fin}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No hay registros de básquetbol في el rango de fechas seleccionado.")

    # =========================================================
    # MÓDULO 2: BÉISBOL
    # =========================================================
    elif "Béisbol" in deporte_sel:
        st.title("⚾ ESAM Analytics — Módulo Béisbol")
        st.caption(f"Operador: {user_name} | Control de Picheos y Registros")

        if es_admin:
            sub_v_beis = st.sidebar.radio("🧭 Navegación Béisbol:", ["📊 Panel & Cargas", "⚙️ Configuración Precio"])
        else:
            sub_v_beis = "📊 Panel & Cargas"

        if es_admin and sub_v_beis == "⚙️ Configuración Precio":
            st.subheader("⚙️ Configuración de Precio por Picheo")
            tasas_b = obtener_tasas_globales()
            with st.form("form_precio_beis"):
                nuevo_precio_b = st.number_input("Precio por Picheo (USD)", value=tasas_b["precio_beisbol"], format="%.4f", step=0.001)
                if st.form_submit_button("💾 Actualizar Precio"):
                    actualizar_tasa_global("precio_beisbol", nuevo_precio_b)
                    st.success("✅ Precio actualizado con éxito.")
                    st.rerun()
        else:
            st.sidebar.markdown("---")
            st.sidebar.subheader("🔍 Filtros de Búsqueda")
            f_tipo_beis = st.sidebar.selectbox("Filtrar Béisbol por:", ["Rango de Fechas Personalizado", "Esta Quincena", "Este Mes", "Todos"], key="b_beis_filtro")

            if f_tipo_beis == "Rango de Fechas Personalizado":
                col_fb1, col_fb2 = st.sidebar.columns(2)
                with col_fb1: b_fini = st.date_input("Desde", value=date.today() - timedelta(days=15), key="beis_ini")
                with col_fb2: b_ffin = st.date_input("Hasta", value=date.today(), key="beis_fin")
            elif f_tipo_beis == "Esta Quincena":
                b_fini, b_ffin = obtener_rango_quincena(date.today())
            elif f_tipo_beis == "Este Mes":
                b_fini = date(date.today().year, date.today().month, 1)
                b_ffin = date.today()
            else:
                b_fini = date(2020, 1, 1)
                b_ffin = date(2035, 12, 31
