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
    page_title="ESAM Analytics 360°",
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
# 4. INICIALIZACIÓN Y MIGRACIÓN AUTOMÁTICA DE TABLAS
# =========================================================
@st.cache_resource
def init_db():
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
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

            cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre VARCHAR(100) DEFAULT 'Operador';")
            cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash VARCHAR(64) DEFAULT '';")
            cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS rol VARCHAR(30) DEFAULT 'operador';")
            cur.execute("ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
            
            try:
                cur.execute("ALTER TABLE usuarios ALTER COLUMN password DROP NOT NULL;")
            except Exception:
                conn.rollback()
                cur = conn.cursor()

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

            cur.execute("""
                CREATE TABLE IF NOT EXISTS configuracion_global (
                    clave VARCHAR(50) PRIMARY KEY,
                    valor NUMERIC(10, 4) NOT NULL
                );
            """)

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

            admin_hash = hash_password("admin123")
            try:
                cur.execute("""
                    INSERT INTO usuarios (username, nombre, password_hash, rol)
                    VALUES ('admin', 'Administrador Global', %s, 'admin')
                    ON CONFLICT (username) DO UPDATE 
                    SET password_hash = EXCLUDED.password_hash,
                        rol = 'admin';
                """, (admin_hash,))
            except Exception:
                conn.rollback()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO usuarios (username, nombre, password, password_hash, rol)
                    VALUES ('admin', 'Administrador Global', 'admin123', %s, 'admin')
                    ON CONFLICT (username) DO UPDATE 
                    SET password_hash = EXCLUDED.password_hash,
                        password = 'admin123',
                        rol = 'admin';
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
# 5. CONSULTAS OPTIMIZADAS CON CACHÉ
# =========================================================
@st.cache_data(ttl=5)
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
            st.cache_data.clear()
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
# 6. GESTIÓN DE USUARIOS Y MANEJO DE QUINCENAS EXACTAS
# =========================================================
def registrar_usuario(username, nombre, password, rol="operador"):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            pwd_hash = hash_password(password)
            try:
                cur.execute("""
                    INSERT INTO usuarios (username, nombre, password_hash, rol)
                    VALUES (%s, %s, %s, %s);
                """, (username.lower().strip(), nombre.strip(), pwd_hash, rol))
            except Exception:
                conn.rollback()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO usuarios (username, nombre, password, password_hash, rol)
                    VALUES (%s, %s, %s, %s, %s);
                """, (username.lower().strip(), nombre.strip(), password, pwd_hash, rol))
            conn.commit()
            cur.close()
            conn.close()
            st.cache_data.clear()
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
                WHERE username = %s AND (password_hash = %s OR password = %s);
            """, (username.lower().strip(), pwd_hash, password))
            user = cur.fetchone()
            cur.close()
            conn.close()
            return user
        except Exception as e:
            st.error(f"Error al autenticar: {e}")
            return None
    return None


def cambiar_password_usuario(user_id, nueva_password):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            pwd_hash = hash_password(nueva_password)
            try:
                cur.execute("UPDATE usuarios SET password_hash = %s, password = %s WHERE id = %s;", (pwd_hash, nueva_password, user_id))
            except Exception:
                conn.rollback()
                cur = conn.cursor()
                cur.execute("UPDATE usuarios SET password_hash = %s WHERE id = %s;", (pwd_hash, user_id))
            conn.commit()
            cur.close()
            conn.close()
            return True, "✅ Contraseña actualizada correctamente."
        except Exception as e:
            return False, f"❌ Error al actualizar contraseña: {e}"
    return False, "❌ Error de conexión a BD."


@st.cache_data(ttl=5)
def obtener_todos_los_usuarios():
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        query = """
            SELECT u.id, u.username, u.nombre, u.rol,
                   COUNT(DISTINCT p.id) as total_partidos_basket,
                   COUNT(DISTINCT pi.id) as total_picheos_beisbol
            FROM usuarios u
            LEFT JOIN partidos p ON u.id = p.usuario_id
            LEFT JOIN picheos pi ON u.id = pi.usuario_id
            GROUP BY u.id, u.username, u.nombre, u.rol
            ORDER BY u.id ASC;
        """
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        st.error(f"Error al cargar usuarios: {e}")
        return pd.DataFrame()


def obtener_rango_quincena(fecha_ref, numero_quincena=None):
    """
    Retorna el rango exacto de fechas para:
    - Q1: Días 1 al 15 del mes.
    - Q2: Días 16 al último día del mes.
    """
    anio = fecha_ref.year
    mes = fecha_ref.month
    
    if numero_quincena == 1:
        return date(anio, mes, 1), date(anio, mes, 15)
    elif numero_quincena == 2:
        if mes == 12:
            fin_mes = date(anio, 12, 31)
        else:
            fin_mes = date(anio, mes + 1, 1) - timedelta(days=1)
        return date(anio, mes, 16), fin_mes
    else:
        if fecha_ref.day <= 15:
            return date(anio, mes, 1), date(anio, mes, 15)
        else:
            if mes == 12:
                fin_mes = date(anio, 12, 31)
            else:
                fin_mes = date(anio, mes + 1, 1) - timedelta(days=1)
            return date(anio, mes, 16), fin_mes


# =========================================================
# 7. MANEJO DE SESIÓN Y AUTENTICACIÓN
# =========================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

if not st.session_state.authenticated:
    st.title("🏆 ESAM Analytics 360°")
    st.caption("Plataforma Profesional de Análisis y Control Operativo (Básquetbol & Béisbol)")

    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrar Usuario"])

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

else:
    # =========================================================
    # PANEL PRINCIPAL Y NAVEGACIÓN PRIVADA
    # =========================================================
    user_id = st.session_state.user_info["id"]
    user_name = st.session_state.user_info["nombre"]
    username_actual = st.session_state.user_info["username"].lower().strip()
    rol_actual = st.session_state.user_info.get("rol", "operador")

    es_admin_estricto = (username_actual == "admin")

    st.sidebar.title("🏆 ESAM Analytics")
    st.sidebar.write(f"👤 **Analista:** {user_name}")
    
    opciones_menu_list = [
        "📊 Panel General y Ganancias",
        "🏀 Módulo Básquetbol",
        "⚾ Módulo Béisbol",
        "🔐 Seguridad y Contraseñas"
    ]
    
    if es_admin_estricto:
        opciones_menu_list.insert(3, "⚙️ Administración de Precios por Deporte")

    st.sidebar.markdown("---")
    opcion_menu = st.sidebar.radio("🧭 Menú Principal:", opciones_menu_list)

    st.sidebar.markdown("---")
    
    if es_admin_estricto:
        modo_super_admin = st.sidebar.checkbox("👑 Activar Modo Admin Global", value=True)
        es_admin = modo_super_admin
    else:
        es_admin = False

    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_info = None
        st.rerun()

    # =========================================================
    # MÓDULO: PANEL GENERAL Y GANANCIAS TOTALES
    # =========================================================
    if opcion_menu == "📊 Panel General y Ganancias":
        st.title("📊 Panel General y Ganancias Totales")
        
        target_user_id = user_id
        opcion_label = f"👤 mis datos ({user_name})"

        if es_admin:
            df_usrs = obtener_todos_los_usuarios()
            if not df_usrs.empty:
                opciones_u = {"🌐 CONSOLIDADO GLOBAL (TODOS LOS USUARIOS)": 0}
                for _, r_u in df_usrs.iterrows():
                    opciones_u[f"👤 {r_u['nombre']} (@{r_u['username']})"] = r_u['id']
                
                u_seleccionado = st.selectbox("👑 [ADMIN] Inspeccionar Datos de Usuario Individual / Global:", list(opciones_u.keys()))
                target_user_id = opciones_u[u_seleccionado]
                opcion_label = u_seleccionado

        if target_user_id == 0:
            st.caption("Consolidado financiero global de TODOS los operadores en el sistema")
        else:
            st.caption(f"Mostrando datos individuales de: **{opcion_label}**")

        conn_gen = get_db_connection()
        total_g_basket = 0.0
        total_g_beisbol = 0.0
        total_juegos_b = 0
        total_lotes_beisbol = 0
        total_pich_b = 0

        if conn_gen:
            try:
                if target_user_id == 0:
                    df_b_all = pd.read_sql_query("SELECT tarifa FROM partidos;", conn_gen)
                    df_beis_all = pd.read_sql_query("SELECT cantidad FROM picheos;", conn_gen)
                else:
                    df_b_all = pd.read_sql_query("SELECT tarifa FROM partidos WHERE usuario_id = %s;", conn_gen, params=(target_user_id,))
                    df_beis_all = pd.read_sql_query("SELECT cantidad FROM picheos WHERE usuario_id = %s;", conn_gen, params=(target_user_id,))

                if not df_b_all.empty:
                    total_g_basket = float(df_b_all["tarifa"].sum())
                    total_juegos_b = len(df_b_all)

                if not df_beis_all.empty:
                    total_pich_b = int(df_beis_all["cantidad"].sum())
                    total_lotes_beisbol = len(df_beis_all)
                    precio_b_u = obtener_tasas_globales()["precio_beisbol"]
                    total_g_beisbol = total_pich_b * precio_b_u

                conn_gen.close()
            except Exception as e:
                st.error(f"Error al calcular totales: {e}")

        total_ganancias_general = total_g_basket + total_g_beisbol
        total_registros_brutos = total_juegos_b + total_lotes_beisbol

        col_mg1, col_mg2, col_mg3, col_mg4 = st.columns(4)
        col_mg1.metric("💰 Ganancias Totales ($)", f"${total_ganancias_general:,.2f}")
        col_mg2.metric("🏀 Ingresos Básquetbol", f"${total_g_basket:,.2f}", f"{total_juegos_b} partidos")
        col_mg3.metric("⚾ Ingresos Béisbol", f"${total_g_beisbol:,.2f}", f"{total_pich_b:,} picheos")
        col_mg4.metric("📊 Total Registros", f"{total_registros_brutos} cargas", f"{total_juegos_b} basket / {total_lotes_beisbol} béisbol")

        st.markdown("---")
        st.subheader("💡 Resumen Operativo")
        st.info("Este panel consolida de forma automática el rendimiento económico de los análisis de básquetbol y béisbol en tiempo real según las tarifas y precios activos del sistema.")

    # =========================================================
    # MÓDULO 1: BÁSQUETBOL (FILTRADO POR QUINCENA SEPARADA)
    # =========================================================
    elif opcion_menu == "🏀 Módulo Básquetbol":
        st.title("🏀 ESAM Analytics — Módulo Básquetbol")
        
        target_b_user_id = user_id
        if es_admin:
            df_usrs = obtener_todos_los_usuarios()
            if not df_usrs.empty:
                opciones_b = {"🌐 CONSOLIDADO GLOBAL (TODOS LOS USUARIOS)": 0}
                for _, r_u in df_usrs.iterrows():
                    opciones_b[f"👤 {r_u['nombre']} (@{r_u['username']})"] = r_u['id']
                
                u_b_sel = st.sidebar.selectbox("👑 Ver Básquetbol de:", list(opciones_b.keys()))
                target_b_user_id = opciones_b[u_b_sel]

        st.caption("Control Financiero y Tiempos de Partidos por Quincena")

        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 Filtro por Quincena y Periodo")
        
        hoy = date.today()
        filtro_b_tipo = st.sidebar.selectbox(
            "Seleccionar Quincena / Periodo:",
            [
                "1.ª Quincena del Mes (Días 1 al 15)",
                "2.ª Quincena del Mes (Días 16 al fin)",
                "Quincena Actual",
                "Quincena Anterior",
                "Este Mes Completo",
                "Todos los Registros",
                "Rango de Fechas Personalizado"
            ],
            key="b_filtro_sel"
        )

        if filtro_b_tipo == "1.ª Quincena del Mes (Días 1 al 15)":
            f_ini, f_fin = obtener_rango_quincena(hoy, numero_quincena=1)
        elif filtro_b_tipo == "2.ª Quincena del Mes (Días 16 al fin)":
            f_ini, f_fin = obtener_rango_quincena(hoy, numero_quincena=2)
        elif filtro_b_tipo == "Quincena Actual":
            f_ini, f_fin = obtener_rango_quincena(hoy)
        elif filtro_b_tipo == "Quincena Anterior":
            if hoy.day <= 15:
                # Quincena anterior es la 2da quincena del mes pasado
                primer_dia_mes_actual = date(hoy.year, hoy.month, 1)
                ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
                f_ini, f_fin = obtener_rango_quincena(ultimo_dia_mes_pasado, numero_quincena=2)
            else:
                # Quincena anterior es la 1ra quincena de este mes
                f_ini, f_fin = obtener_rango_quincena(hoy, numero_quincena=1)
        elif filtro_b_tipo == "Este Mes Completo":
            f_ini = date(hoy.year, hoy.month, 1)
            if hoy.month == 12:
                f_fin = date(hoy.year, 12, 31)
            else:
                f_fin = date(hoy.year, hoy.month + 1, 1) - timedelta(days=1)
        elif filtro_b_tipo == "Rango de Fechas Personalizado":
            col_fd1, col_fd2 = st.sidebar.columns(2)
            with col_fd1: f_ini = st.date_input("Desde", value=date.today() - timedelta(days=30), key="b_f_ini")
            with col_fd2: f_fin = st.date_input("Hasta", value=date.today(), key="b_f_fin")
        else:
            f_ini = date(2020, 1, 1)
            f_fin = date(2035, 12, 31)

        st.info(f"📅 **Periodo Evaluado:** Del **{f_ini.strftime('%d/%m/%Y')}** al **{f_fin.strftime('%d/%m/%Y')}**")

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
                        st.cache_data.clear()
                        st.success("✅ Partido guardado exitosamente.")
                        st.rerun()

        conn_q = get_db_connection()
        if conn_q:
            if target_b_user_id == 0:
                df_basket = pd.read_sql_query("""
                    SELECT p.id, u.nombre as operador, p.codigo_partido, p.fecha, p.tiempo_ejecucion, p.tarifa, p.tipo_partido 
                    FROM partidos p
                    JOIN usuarios u ON p.usuario_id = u.id
                    WHERE p.fecha BETWEEN %s AND %s
                    ORDER BY p.fecha DESC, p.id DESC;
                """, conn_q, params=(f_ini, f_fin))
            else:
                df_basket = pd.read_sql_query("""
                    SELECT id, codigo_partido, fecha, tiempo_ejecucion, tarifa, tipo_partido 
                    FROM partidos 
                    WHERE usuario_id = %s AND fecha BETWEEN %s AND %s
                    ORDER BY fecha DESC, id DESC;
                """, conn_q, params=(target_b_user_id, f_ini, f_fin))
            conn_q.close()
        else:
            df_basket = pd.DataFrame()

        st.markdown(f"### 📋 Registros de Básquetbol ({f_ini.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')})")
        if not df_basket.empty:
            total_ganancias = df_basket["tarifa"].astype(float).sum()
            col_k1, col_k2, col_k3 = st.columns(3)
            col_k1.metric("🏀 Total Partidos Quincena", len(df_basket))
            col_k2.metric("💵 Total Ganancias Quincena", f"${total_ganancias:.2f}")
            col_k3.metric("📅 Rango Evaluado", f"{f_ini.strftime('%d/%m')} - {f_fin.strftime('%d/%m/%Y')}")

            st.dataframe(df_basket, use_container_width=True, hide_index=True)

            with st.expander("🛠️ Opciones de Edición / Eliminación de Partidos"):
                tab_eb1, tab_eb2 = st.tabs(["✏️ Editar Partido", "🗑️ Eliminar Partido"])
                
                with tab_eb1:
                    list_ids_b = df_basket["id"].tolist()
                    id_edit_b = st.selectbox("Seleccione el ID del partido a editar:", list_ids_b, key="sel_edit_b")
                    
                    row_b = df_basket[df_basket["id"] == id_edit_b].iloc[0]
                    with st.form("form_edit_b"):
                        fe_b = st.date_input("Fecha", value=pd.to_datetime(row_b["fecha"]).date())
                        cod_b = st.text_input("Código de Partido", value=str(row_b["codigo_partido"]))
                        t_b = st.text_input("Tiempo de Ejecución", value=str(row_b["tiempo_ejecucion"]))
                        tar_b = st.number_input("Tarifa ($)", value=float(row_b["tarifa"]), step=0.50)
                        
                        if st.form_submit_button("💾 Guardar Cambios en Partido"):
                            conn_eb = get_db_connection()
                            if conn_eb:
                                cur_eb = conn_eb.cursor()
                                cur_eb.execute("UPDATE partidos SET fecha=%s, codigo_partido=%s, tiempo_ejecucion=%s, tarifa=%s WHERE id=%s;", (fe_b, cod_b, t_b, tar_b, id_edit_b))
                                conn_eb.commit()
                                cur_eb.close()
                                conn_eb.close()
                                st.cache_data.clear()
                                st.success("✅ Partido actualizado con éxito.")
                                st.rerun()

                with tab_eb2:
                    id_del_b = st.selectbox("Seleccione el ID del partido a eliminar:", df_basket["id"].tolist(), key="sel_del_b")
                    if st.button("🚨 Confirmar y Eliminar Partido", use_container_width=True):
                        conn_db = get_db_connection()
                        if conn_db:
                            cur_db = conn_db.cursor()
                            cur_db.execute("DELETE FROM partidos WHERE id = %s;", (id_del_b,))
                            conn_db.commit()
                            cur_db.close()
                            conn_db.close()
                            st.cache_data.clear()
                            st.success("🗑️ Partido eliminado correctamente.")
                            st.rerun()

            csv_b = df_basket.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Exportar Reporte Quincenal de Básquetbol (CSV)",
                data=csv_b,
                file_name=f"esam_basket_quincena_{f_ini}_al_{f_fin}.csv",
                mime="text/csv"
            )
        else:
            st.info("No hay registros de básquetbol para la quincena o periodo seleccionado.")

    # =========================================================
    # MÓDULO 2: BÉISBOL (FILTRADO POR QUINCENA SEPARADA)
    # =========================================================
    elif opcion_menu == "⚾ Módulo Béisbol":
        st.title("⚾ ESAM Analytics — Módulo Béisbol")

        target_beis_user_id = user_id
        if es_admin:
            df_usrs = obtener_todos_los_usuarios()
            if not df_usrs.empty:
                opciones_beis = {"🌐 CONSOLIDADO GLOBAL (TODOS LOS USUARIOS)": 0}
                for _, r_u in df_usrs.iterrows():
                    opciones_beis[f"👤 {r_u['nombre']} (@{r_u['username']})"] = r_u['id']
                
                u_beis_sel = st.sidebar.selectbox("👑 Ver Béisbol de:", list(opciones_beis.keys()))
                target_beis_user_id = opciones_beis[u_beis_sel]

        st.caption("Control de Picheos y Registros por Quincena")

        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 Filtro por Quincena y Periodo")
        
        hoy_b = date.today()
        f_tipo_beis = st.sidebar.selectbox(
            "Seleccionar Quincena / Periodo Béisbol:",
            [
                "1.ª Quincena del Mes (Días 1 al 15)",
                "2.ª Quincena del Mes (Días 16 al fin)",
                "Quincena Actual",
                "Quincena Anterior",
                "Este Mes Completo",
                "Todos los Registros",
                "Rango de Fechas Personalizado"
            ],
            key="b_beis_filtro"
        )

        if f_tipo_beis == "1.ª Quincena del Mes (Días 1 al 15)":
            b_fini, b_ffin = obtener_rango_quincena(hoy_b, numero_quincena=1)
        elif f_tipo_beis == "2.ª Quincena del Mes (Días 16 al fin)":
            b_fini, b_ffin = obtener_rango_quincena(hoy_b, numero_quincena=2)
        elif f_tipo_beis == "Quincena Actual":
            b_fini, b_ffin = obtener_rango_quincena(hoy_b)
        elif f_tipo_beis == "Quincena Anterior":
            if hoy_b.day <= 15:
                primer_dia_mes_actual = date(hoy_b.year, hoy_b.month, 1)
                ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
                b_fini, b_ffin = obtener_rango_quincena(ultimo_dia_mes_pasado, numero_quincena=2)
            else:
                b_fini, b_ffin = obtener_rango_quincena(hoy_b, numero_quincena=1)
        elif f_tipo_beis == "Este Mes Completo":
            b_fini = date(hoy_b.year, hoy_b.month, 1)
            if hoy_b.month == 12:
                b_ffin = date(hoy_b.year, 12, 31)
            else:
                b_ffin = date(hoy_b.year, hoy_b.month + 1, 1) - timedelta(days=1)
        elif f_tipo_beis == "Rango de Fechas Personalizado":
            col_fb1, col_fb2 = st.sidebar.columns(2)
            with col_fb1: b_fini = st.date_input("Desde", value=date.today() - timedelta(days=30), key="beis_ini")
            with col_fb2: b_ffin = st.date_input("Hasta", value=date.today(), key="beis_fin")
        else:
            b_fini = date(2020, 1, 1)
            b_ffin = date(2035, 12, 31)

        st.info(f"📅 **Periodo Evaluado Béisbol:** Del **{b_fini.strftime('%d/%m/%Y')}** al **{b_ffin.strftime('%d/%m/%Y')}**")

        with st.expander("➕ Registrar Lote de Picheos", expanded=False):
            p1, p2, p3 = st.columns(3)
            with p1: f_pich = st.date_input("Fecha", value=date.today(), key="p_fich")
            with p2: id_ctrl = st.text_input("ID Control / Partido", placeholder="Ej: BC-2026")
            with p3: cant_pich = st.number_input("Cantidad de Picheos", min_value=1, step=1, value=100)

            if st.button("💾 Guardar Picheos", use_container_width=True):
                if not id_ctrl.strip():
                    st.warning("Ingrese el ID de control.")
                else:
                    conn_p = get_db_connection()
                    if conn_p:
                        cur_p = conn_p.cursor()
                        cur_p.execute("""
                            INSERT INTO picheos (usuario_id, fecha, id_control, cantidad)
                            VALUES (%s, %s, %s, %s);
                        """, (user_id, f_pich, id_ctrl.strip(), int(cant_pich)))
                        conn_p.commit()
                        cur_p.close()
                        conn_p.close()
                        st.cache_data.clear()
                        st.success("✅ Picheos guardados correctamente.")
                        st.rerun()

        conn_pb = get_db_connection()
        if conn_pb:
            if target_beis_user_id == 0:
                df_picheos = pd.read_sql_query("""
                    SELECT pi.id, u.nombre as operador, pi.fecha, pi.id_control, pi.cantidad 
                    FROM picheos pi
                    JOIN usuarios u ON pi.usuario_id = u.id
                    WHERE pi.fecha BETWEEN %s AND %s
                    ORDER BY pi.fecha DESC, pi.id DESC;
                """, conn_pb, params=(b_fini, b_ffin))
            else:
                df_picheos = pd.read_sql_query("""
                    SELECT id, fecha, id_control, cantidad 
                    FROM picheos 
                    WHERE usuario_id = %s AND fecha BETWEEN %s AND %s
                    ORDER BY fecha DESC, id DESC;
                """, conn_pb, params=(target_beis_user_id, b_fini, b_ffin))
            conn_pb.close()
        else:
            df_picheos = pd.DataFrame()

        st.markdown(f"### 📋 Listado de Picheos ({b_fini.strftime('%d/%m/%Y')} al {b_ffin.strftime('%d/%m/%Y')})")
        if not df_picheos.empty:
            total_p = df_picheos["cantidad"].sum()
            precio_u = obtener_tasas_globales()["precio_beisbol"]
            total_dolares = total_p * precio_u

            cp1, cp2, cp3 = st.columns(3)
            cp1.metric("⚾ Total Picheos Quincena", f"{total_p:,}")
            cp2.metric("💵 USD Estimado", f"${total_dolares:,.2f}", f"@ ${precio_u}/u")
            cp3.metric("📅 Lotes Registrados", len(df_picheos))

            st.dataframe(df_picheos, use_container_width=True, hide_index=True)

            with st.expander("🛠️ Opciones de Edición / Eliminación de Picheos"):
                tab_ep1, tab_ep2 = st.tabs(["✏️ Editar Lote de Picheos", "🗑️ Eliminar Lote"])
                
                with tab_ep1:
                    list_ids_p = df_picheos["id"].tolist()
                    id_edit_p = st.selectbox("Seleccione el ID del lote a editar:", list_ids_p, key="sel_edit_p")
                    
                    row_p = df_picheos[df_picheos["id"] == id_edit_p].iloc[0]
                    with st.form("form_edit_p"):
                        fe_p = st.date_input("Fecha", value=pd.to_datetime(row_p["fecha"]).date())
                        id_c_p = st.text_input("ID Control / Partido", value=str(row_p["id_control"]))
                        cant_p = st.number_input("Cantidad de Picheos", value=int(row_p["cantidad"]), step=1, min_value=1)
                        
                        if st.form_submit_button("💾 Guardar Cambios en Picheos"):
                            conn_ep = get_db_connection()
                            if conn_ep:
                                cur_ep = conn_ep.cursor()
                                cur_ep.execute("UPDATE picheos SET fecha=%s, id_control=%s, cantidad=%s WHERE id=%s;", (fe_p, id_c_p, int(cant_p), id_edit_p))
                                conn_ep.commit()
                                cur_ep.close()
                                conn_ep.close()
                                st.cache_data.clear()
                                st.success("✅ Lote de picheos actualizado con éxito.")
                                st.rerun()

                with tab_ep2:
                    id_del_p = st.selectbox("Seleccione el ID del lote a eliminar:", df_picheos["id"].tolist(), key="sel_del_p")
                    if st.button("🚨 Confirmar y Eliminar Lote", use_container_width=True):
                        conn_dp = get_db_connection()
                        if conn_dp:
                            cur_dp = conn_dp.cursor()
                            cur_dp.execute("DELETE FROM picheos WHERE id = %s;", (id_del_p,))
                            conn_dp.commit()
                            cur_dp.close()
                            conn_dp.close()
                            st.cache_data.clear()
                            st.success("🗑️ Lote de picheos eliminado correctamente.")
                            st.rerun()

            csv_b = df_picheos.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Exportar Reporte Quincenal de Béisbol (CSV)",
                data=csv_b,
                file_name=f"esam_beisbol_quincena_{b_fini}_al_{b_ffin}.csv",
                mime="text/csv"
            )
        else:
            st.info("No hay registros de picheos para la quincena o periodo seleccionado.")

    # =========================================================
    # MÓDULO: ADMINISTRACIÓN DE PRECIOS POR DEPORTE (EXCLUSIVO ADMIN)
    # =========================================================
    elif opcion_menu == "⚙️ Administración de Precios por Deporte" and es_admin_estricto:
        st.title("⚙️ PANEL DE CONTROL Y CONFIGURACIÓN DE TARIFAS")
        st.caption("Ajusta en tiempo real los valores en USD asignados a cada disciplina deportiva")

        tasas_actuales = obtener_tasas_globales()

        tab_p_basket, tab_p_beis = st.tabs(["🏀 Tarifas de Básquetbol", "⚾ Precios de Béisbol"])

        with tab_p_basket:
            st.subheader("🏀 Tarifas y Tramos de Básquetbol")
            with st.form("form_admin_basket_prices"):
                st.markdown("##### 📈 Tramos Quincenales (USD por partido):")
                cb1, cb2, cb3, cb4 = st.columns(4)
                with cb1: nt1 = st.number_input("Tramo 1 (1 - 11 partidos)", value=tasas_actuales["tramo_1"], step=0.25)
                with cb2: nt2 = st.number_input("Tramo 2 (12 - 14 partidos)", value=tasas_actuales["tramo_2"], step=0.25)
                with cb3: nt3 = st.number_input("Tramo 3 (15 - 29 partidos)", value=tasas_actuales["tramo_3"], step=0.25)
                with cb4: nt4 = st.number_input("Tramo 4 (30+ partidos)", value=tasas_actuales["tramo_4"], step=0.25)

                st.markdown("---")
                st.markdown("##### ⚡ Modalidad Especial En Vivo:")
                cbe1, cbe2 = st.columns(2)
                with cbe1: n_norm = st.number_input("Partido En Vivo Normal ($)", value=tasas_actuales["en_vivo_normal"], step=0.50)
                with cbe2: n_nba = st.number_input("Partido En Vivo NBA ($)", value=tasas_actuales["en_vivo_nba"], step=0.50)

                sub_b_prices = st.form_submit_button("💾 Actualizar Tarifas de Básquetbol", use_container_width=True)
                if sub_b_prices:
                    actualizar_tasa_global("tasa_tramo_1", nt1)
                    actualizar_tasa_global("tasa_tramo_2", nt2)
                    actualizar_tasa_global("tasa_tramo_3", nt3)
                    actualizar_tasa_global("tasa_tramo_4", nt4)
                    actualizar_tasa_global("tasa_en_vivo_normal", n_norm)
                    actualizar_tasa_global("tasa_en_vivo_nba", n_nba)
                    st.success("✅ Tarifas de Básquetbol actualizadas con éxito.")
                    st.rerun()

        with tab_p_beis:
            st.subheader("⚾ Tarifa Unitaria de Béisbol")
            with st.form("form_admin_beis_prices"):
                n_precio_beis = st.number_input("Precio por Picheo Registrado (USD)", value=tasas_actuales["precio_beisbol"], format="%.4f", step=0.001)
                sub_beis_price = st.form_submit_button("💾 Actualizar Precio de Béisbol", use_container_width=True)
                if sub_beis_price:
                    actualizar_tasa_global("precio_beisbol", n_precio_beis)
                    st.success("✅ Precio por picheo de Béisbol actualizado con éxito.")
                    st.rerun()

    # =========================================================
    # MÓDULO: SEGURIDAD Y CREDENCIALES
    # =========================================================
    elif opcion_menu == "🔐 Seguridad y Contraseñas":
        st.title("🔐 Gestión de Seguridad y Contraseñas")
        st.caption(f"Actualiza la contraseña de tu cuenta de operador — {user_name}")

        with st.form("form_cambiar_pass"):
            pass_vieja = st.text_input("Contraseña Actual", type="password")
            pass_nueva = st.text_input("Nueva Contraseña", type="password")
            pass_conf = st.text_input("Confirmar Nueva Contraseña", type="password")

            submit_pass = st.form_submit_button("🔒 Actualizar Contraseña", use_container_width=True)

            if submit_pass:
                if not (pass_vieja and pass_nueva and pass_conf):
                    st.warning("Por favor complete todos los campos.")
                elif pass_nueva != pass_conf:
                    st.error("Las nuevas contraseñas no coinciden.")
                elif len(pass_nueva) < 6:
                    st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                else:
                    user_verif = autenticar_usuario(st.session_state.user_info["username"], pass_vieja)
                    if not user_verif:
                        st.error("❌ La contraseña actual es incorrecta.")
                    else:
                        exito_c, msg_c = cambiar_password_usuario(user_id, pass_nueva)
                        if exito_c:
                            st.success(msg_c)
                        else:
                            st.error(msg_c)
