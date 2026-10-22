import calendar
from datetime import date, timedelta
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

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
ETQ_TIPO = {
    "quincenal": "🏀 Quincenal estándar",
    "en_vivo_normal": "⚡ En vivo normal",
    "en_vivo_nba": "🔥 En vivo NBA",
}


def money(x):
    return f"${float(x):,.2f}"


# =========================================================
# 2. SEGURIDAD
# =========================================================
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


# =========================================================
# 3. CONEXIÓN Y HELPERS DE BASE DE DATOS (NEON POSTGRESQL)
# =========================================================
def get_db_connection():
    try:
        if "postgres" not in st.secrets or "url" not in st.secrets["postgres"]:
            st.error("❌ La clave '[postgres]' o 'url' no existe en los secretos de Streamlit.")
            return None
        return psycopg2.connect(st.secrets["postgres"]["url"])
    except Exception as e:
        st.error(f"❌ Error de conexión a Neon PostgreSQL: {e}")
        return None


def ejecutar(sql, params=None):
    """INSERT / UPDATE / DELETE. Devuelve True si salió bien."""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"❌ Error de base de datos: {e}")
        return False
    finally:
        conn.close()


def consultar_df(sql, params=None):
    conn = get_db_connection()
    if not conn:
        return pd.DataFrame()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    except Exception as e:
        st.error(f"❌ Error al consultar: {e}")
        return pd.DataFrame()
    finally:
        conn.close()


# =========================================================
# 4. INICIALIZACIÓN Y MIGRACIÓN DE TABLAS
# =========================================================
@st.cache_resource
def init_db():
    conn = get_db_connection()
    if not conn:
        return False
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

        # Migración de la columna antigua 'password' (texto plano) -> hash, y se borra el texto plano
        cur.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = 'usuarios' AND column_name = 'password';
        """)
        if cur.fetchone():
            cur.execute("ALTER TABLE usuarios ALTER COLUMN password DROP NOT NULL;")
            cur.execute("""
                UPDATE usuarios
                SET password_hash = encode(sha256(convert_to(password, 'UTF8')), 'hex')
                WHERE (password_hash IS NULL OR password_hash = '')
                  AND password IS NOT NULL AND password <> '';
            """)
            cur.execute("""
                UPDATE usuarios SET password = NULL
                WHERE password_hash IS NOT NULL AND password_hash <> '';
            """)

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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_partidos_user_fecha ON partidos (usuario_id, fecha);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_picheos_user_fecha ON picheos (usuario_id, fecha);")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuracion_global (
                clave VARCHAR(50) PRIMARY KEY,
                valor NUMERIC(10, 4) NOT NULL
            );
        """)

        defaults = [
            ("tasa_tramo_1", 6.00), ("tasa_tramo_2", 6.50),
            ("tasa_tramo_3", 7.00), ("tasa_tramo_4", 8.00),
            ("tasa_en_vivo_normal", 12.00), ("tasa_en_vivo_nba", 18.50),
            ("precio_beisbol", 0.024),
        ]
        for clave, val in defaults:
            cur.execute(
                "INSERT INTO configuracion_global (clave, valor) VALUES (%s, %s) ON CONFLICT (clave) DO NOTHING;",
                (clave, val),
            )

        # Admin: se crea SOLO si no existe. Ya no se reinicia su clave en cada arranque.
        # Clave inicial: secreto 'admin_password' (opcional) o 'admin123'. Cámbiala al entrar.
        admin_hash = hash_password(str(st.secrets.get("admin_password", "admin123")))
        cur.execute("""
            INSERT INTO usuarios (username, nombre, password_hash, rol)
            VALUES ('admin', 'Administrador Global', %s, 'admin')
            ON CONFLICT (username) DO NOTHING;
        """, (admin_hash,))
        cur.execute("""
            UPDATE usuarios SET password_hash = %s
            WHERE username = 'admin' AND (password_hash IS NULL OR password_hash = '');
        """, (admin_hash,))
        cur.execute("UPDATE usuarios SET rol = 'admin' WHERE username = 'admin';")

        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        conn.rollback()
        conn.close()
        st.error(f"❌ Error al inicializar tablas: {e}")
        return False


init_db()


# =========================================================
# 5. TARIFAS GLOBALES
# =========================================================
@st.cache_data(ttl=5)
def obtener_tasas_globales():
    tasas = {
        "tramo_1": 6.00, "tramo_2": 6.50, "tramo_3": 7.00, "tramo_4": 8.00,
        "en_vivo_normal": 12.00, "en_vivo_nba": 18.50, "precio_beisbol": 0.024,
    }
    mapa = {
        "tasa_tramo_1": "tramo_1", "tasa_tramo_2": "tramo_2",
        "tasa_tramo_3": "tramo_3", "tasa_tramo_4": "tramo_4",
        "tasa_en_vivo_normal": "en_vivo_normal", "tasa_en_vivo_nba": "en_vivo_nba",
        "precio_beisbol": "precio_beisbol",
    }
    df = consultar_df("SELECT clave, valor FROM configuracion_global;")
    for r in df.itertuples():
        if r.clave in mapa:
            tasas[mapa[r.clave]] = float(r.valor)
    return tasas


def actualizar_tasa_global(clave, nuevo_valor):
    ok = ejecutar("UPDATE configuracion_global SET valor = %s WHERE clave = %s;", (nuevo_valor, clave))
    if ok:
        st.cache_data.clear()
    return ok


def obtener_tarifa_basket(tipo_partido, cant_partidos=0):
    tasas = obtener_tasas_globales()
    if tipo_partido == "en_vivo_nba":
        return tasas["en_vivo_nba"]
    if tipo_partido == "en_vivo_normal":
        return tasas["en_vivo_normal"]
    if cant_partidos <= 11:
        return tasas["tramo_1"]
    if cant_partidos <= 14:
        return tasas["tramo_2"]
    if cant_partidos <= 29:
        return tasas["tramo_3"]
    return tasas["tramo_4"]


# =========================================================
# 6. USUARIOS Y AUTENTICACIÓN
# =========================================================
def registrar_usuario(username, nombre, password, rol="operador"):
    conn = get_db_connection()
    if not conn:
        return False, "❌ Error de conexión a BD."
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usuarios (username, nombre, password_hash, rol) VALUES (%s, %s, %s, %s);",
                (username.lower().strip(), nombre.strip(), hash_password(password), rol),
            )
        conn.commit()
        st.cache_data.clear()
        return True, "✅ Usuario registrado exitosamente."
    except psycopg2.IntegrityError:
        conn.rollback()
        return False, "⚠️ El nombre de usuario ya existe."
    except Exception as e:
        conn.rollback()
        return False, f"❌ Error en registro: {e}"
    finally:
        conn.close()


def autenticar_usuario(username, password):
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, username, nombre, rol FROM usuarios WHERE username = %s AND password_hash = %s;",
            (username.lower().strip(), hash_password(password)),
        )
        user = cur.fetchone()
        cur.close()
        return user
    except Exception as e:
        st.error(f"Error al autenticar: {e}")
        return None
    finally:
        conn.close()


def cambiar_password_usuario(user_id, nueva_password):
    ok = ejecutar("UPDATE usuarios SET password_hash = %s WHERE id = %s;", (hash_password(nueva_password), user_id))
    if ok:
        return True, "✅ Contraseña actualizada correctamente."
    return False, "❌ No se pudo actualizar la contraseña."


@st.cache_data(ttl=5)
def obtener_todos_los_usuarios():
    return consultar_df("""
        SELECT u.id, u.username, u.nombre, u.rol,
               COUNT(DISTINCT p.id) AS total_partidos_basket,
               COUNT(DISTINCT pi.id) AS total_lotes_beisbol
        FROM usuarios u
        LEFT JOIN partidos p ON u.id = p.usuario_id
        LEFT JOIN picheos pi ON u.id = pi.usuario_id
        GROUP BY u.id, u.username, u.nombre, u.rol
        ORDER BY u.id ASC;
    """)


# =========================================================
# 7. QUINCENAS Y PERIODOS
# =========================================================
def obtener_rango_quincena(anio, mes, numero_quincena=None):
    """1 = días 1-15, 2 = día 16 a fin de mes, None = mes completo."""
    ultimo = calendar.monthrange(anio, mes)[1]
    if numero_quincena == 1:
        return date(anio, mes, 1), date(anio, mes, 15)
    if numero_quincena == 2:
        return date(anio, mes, 16), date(anio, mes, ultimo)
    return date(anio, mes, 1), date(anio, mes, ultimo)


def quincena_de(fecha):
    return obtener_rango_quincena(fecha.year, fecha.month, 1 if fecha.day <= 15 else 2)


OPC_PERIODO = [
    "1.ª Quincena (días 1 al 15)",
    "2.ª Quincena (día 16 al fin de mes)",
    "Mes completo (ambas quincenas)",
    "Todos los registros",
    "Rango personalizado",
]


def selector_periodo(clave):
    """Selector de año/mes/quincena en la barra lateral. Devuelve dict con el periodo."""
    hoy = date.today()
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗓️ Periodo a evaluar")
    anios = list(range(hoy.year - 3, hoy.year + 2))
    anio = st.sidebar.selectbox("Año", anios, index=anios.index(hoy.year), key=f"{clave}_anio")
    mes = st.sidebar.selectbox("Mes", list(range(1, 13)), index=hoy.month - 1,
                               format_func=lambda m: MESES[m - 1], key=f"{clave}_mes")
    opcion = st.sidebar.radio("Quincena", OPC_PERIODO, index=0 if hoy.day <= 15 else 1, key=f"{clave}_q")

    if opcion == OPC_PERIODO[0]:
        ini, fin = obtener_rango_quincena(anio, mes, 1)
        etiqueta = f"1.ª Quincena de {MESES[mes - 1]} {anio}"
    elif opcion == OPC_PERIODO[1]:
        ini, fin = obtener_rango_quincena(anio, mes, 2)
        etiqueta = f"2.ª Quincena de {MESES[mes - 1]} {anio}"
    elif opcion == OPC_PERIODO[2]:
        ini, fin = obtener_rango_quincena(anio, mes)
        etiqueta = f"Mes completo: {MESES[mes - 1]} {anio}"
    elif opcion == OPC_PERIODO[3]:
        ini, fin = date(2000, 1, 1), date(2100, 12, 31)
        etiqueta = "Todos los registros"
    else:
        c1, c2 = st.sidebar.columns(2)
        with c1:
            ini = st.date_input("Desde", value=hoy - timedelta(days=15), key=f"{clave}_ini")
        with c2:
            fin = st.date_input("Hasta", value=hoy, key=f"{clave}_fin")
        if ini > fin:
            st.sidebar.warning("'Desde' era mayor que 'Hasta'; se invirtieron.")
            ini, fin = fin, ini
        etiqueta = "Rango personalizado"

    return {"ini": ini, "fin": fin, "etiqueta": etiqueta, "anio": anio, "mes": mes}


def texto_periodo(p):
    if p["etiqueta"] == "Todos los registros":
        return "Todos los registros"
    return f"{p['ini'].strftime('%d/%m/%Y')} al {p['fin'].strftime('%d/%m/%Y')}"


def selector_usuario(clave, es_admin, user_id):
    """Solo el admin (modo global) puede elegir otro usuario o el consolidado (0)."""
    if not es_admin:
        return user_id, "mis datos"
    df = obtener_todos_los_usuarios()
    opciones = {"🌐 Consolidado global (todos los usuarios)": 0}
    for r in df.itertuples():
        opciones[f"👤 {r.nombre} (@{r.username})"] = int(r.id)
    sel = st.sidebar.selectbox("👑 [ADMIN] Ver datos de:", list(opciones), key=f"{clave}_usr")
    return opciones[sel], sel


# =========================================================
# 8. RESÚMENES FINANCIEROS
# =========================================================
def resumen_periodo(uid, f_ini, f_fin):
    """uid = 0 -> todos los usuarios."""
    filtro, params = "", [f_ini, f_fin]
    if uid:
        filtro = " AND usuario_id = %s"
        params.append(uid)
    params = tuple(params)

    df_b = consultar_df(f"""
        SELECT COALESCE(tipo_partido, 'quincenal') AS tipo,
               COUNT(*) AS partidos, COALESCE(SUM(tarifa), 0) AS total
        FROM partidos WHERE fecha BETWEEN %s AND %s{filtro}
        GROUP BY 1 ORDER BY 1;
    """, params)
    df_p = consultar_df(f"""
        SELECT COUNT(*) AS lotes, COALESCE(SUM(cantidad), 0) AS picheos
        FROM picheos WHERE fecha BETWEEN %s AND %s{filtro};
    """, params)

    precio = obtener_tasas_globales()["precio_beisbol"]
    if not df_b.empty:
        df_b["partidos"] = df_b["partidos"].astype(int)
        df_b["total"] = df_b["total"].astype(float)
    partidos = int(df_b["partidos"].sum()) if not df_b.empty else 0
    g_basket = float(df_b["total"].sum()) if not df_b.empty else 0.0
    lotes = int(df_p["lotes"].iloc[0]) if not df_p.empty else 0
    picheos = int(df_p["picheos"].iloc[0]) if not df_p.empty else 0
    g_beis = picheos * precio
    return {
        "df_basket_tipos": df_b, "partidos": partidos, "g_basket": g_basket,
        "lotes": lotes, "picheos": picheos, "precio": precio, "g_beis": g_beis,
        "total": g_basket + g_beis,
    }


def resumen_por_operador(f_ini, f_fin):
    precio = obtener_tasas_globales()["precio_beisbol"]
    df_b = consultar_df("""
        SELECT u.id, u.nombre, u.username,
               COUNT(p.id) AS partidos, COALESCE(SUM(p.tarifa), 0) AS basket
        FROM usuarios u
        LEFT JOIN partidos p ON p.usuario_id = u.id AND p.fecha BETWEEN %s AND %s
        GROUP BY u.id, u.nombre, u.username;
    """, (f_ini, f_fin))
    df_p = consultar_df("""
        SELECT u.id, COALESCE(SUM(pi.cantidad), 0) AS picheos
        FROM usuarios u
        LEFT JOIN picheos pi ON pi.usuario_id = u.id AND pi.fecha BETWEEN %s AND %s
        GROUP BY u.id;
    """, (f_ini, f_fin))
    if df_b.empty or df_p.empty:
        return pd.DataFrame()
    df = df_b.merge(df_p, on="id")
    df["basket"] = df["basket"].astype(float)
    df["picheos"] = df["picheos"].astype(float)
    df["beisbol"] = df["picheos"] * precio
    df["total"] = df["basket"] + df["beisbol"]
    return df.sort_values("total", ascending=False)


# =========================================================
# 9. SESIÓN Y LOGIN
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
                        st.session_state.user_info = dict(user_data)
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
                    if exito:
                        st.success(msg)
                    else:
                        st.error(msg)

else:
    # =========================================================
    # PANEL PRINCIPAL
    # =========================================================
    user_id = int(st.session_state.user_info["id"])
    user_name = st.session_state.user_info["nombre"]
    username_actual = st.session_state.user_info["username"].lower().strip()

    # Solo el usuario 'admin' tiene privilegios de administrador
    es_admin_estricto = (username_actual == "admin")

    M_PANEL = "📊 Panel General y Ganancias"
    M_BASKET = "🏀 Módulo Básquetbol"
    M_BEIS = "⚾ Módulo Béisbol"
    M_PRECIOS = "⚙️ Administración de Precios por Deporte"
    M_SEG = "🔐 Seguridad y Contraseñas"

    menu = [M_PANEL, M_BASKET, M_BEIS]
    if es_admin_estricto:
        menu += [M_PRECIOS, M_SEG]  # contraseñas: SOLO admin

    st.sidebar.title("🏆 ESAM Analytics")
    st.sidebar.write(f"👤 **Analista:** {user_name}")
    st.sidebar.markdown("---")
    opcion_menu = st.sidebar.radio("🧭 Menú Principal:", menu)
    st.sidebar.markdown("---")

    if es_admin_estricto:
        es_admin = st.sidebar.checkbox("👑 Activar Modo Admin Global", value=True)
    else:
        es_admin = False

    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_info = None
        st.rerun()

    # =========================================================
    # PANEL GENERAL: TOTAL GANADO EN AMBOS DEPORTES
    # =========================================================
    if opcion_menu == M_PANEL:
        st.title("📊 Panel General y Ganancias Totales")

        target_id, target_label = selector_usuario("panel", es_admin, user_id)
        per = selector_periodo("panel")

        if target_id == 0:
            st.caption("Consolidado financiero global de TODOS los operadores")
        else:
            st.caption(f"Mostrando: **{target_label}**")
        st.info(f"📅 **{per['etiqueta']}** · {texto_periodo(per)}")

        r = resumen_periodo(target_id, per["ini"], per["fin"])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("💰 Total Ganado (ambos deportes)", money(r["total"]))
        c2.metric("🏀 Básquetbol", money(r["g_basket"]), f"{r['partidos']} partidos")
        c3.metric("⚾ Béisbol", money(r["g_beis"]), f"{r['picheos']:,} picheos")
        c4.metric("📦 Total Registros", f"{r['partidos'] + r['lotes']}",
                  f"{r['partidos']} basket / {r['lotes']} béisbol")

        st.markdown("---")
        st.subheader("🔎 Detalle por deporte")
        cb, cs = st.columns(2)
        with cb:
            st.markdown("##### 🏀 Básquetbol")
            if r["df_basket_tipos"].empty:
                st.caption("Sin partidos en este periodo.")
            else:
                det = r["df_basket_tipos"].copy()
                det["Modalidad"] = det["tipo"].map(ETQ_TIPO).fillna(det["tipo"])
                det["Ganado"] = det["total"].map(money)
                det = det.rename(columns={"partidos": "Partidos"})[["Modalidad", "Partidos", "Ganado"]]
                st.dataframe(det, use_container_width=True, hide_index=True)
        with cs:
            st.markdown("##### ⚾ Béisbol")
            d1, d2 = st.columns(2)
            d1.metric("Lotes registrados", r["lotes"])
            d2.metric("Picheos totales", f"{r['picheos']:,}")
            st.caption(f"Tarifa vigente: ${r['precio']}/picheo → **{money(r['g_beis'])}**")

        st.markdown("---")
        st.subheader(f"🗓️ Comparativo de quincenas — {MESES[per['mes'] - 1]} {per['anio']}")
        filas = []
        acum = {"b": 0.0, "e": 0.0, "pa": 0, "pi": 0}
        for num, nombre in ((1, "1.ª Quincena (1–15)"), (2, "2.ª Quincena (16–fin)")):
            qi, qf = obtener_rango_quincena(per["anio"], per["mes"], num)
            rq = resumen_periodo(target_id, qi, qf)
            filas.append({"Quincena": nombre, "Partidos": rq["partidos"], "🏀 Básquetbol": money(rq["g_basket"]),
                          "Picheos": f"{rq['picheos']:,}", "⚾ Béisbol": money(rq["g_beis"]),
                          "💰 Total": money(rq["total"])})
            acum["b"] += rq["g_basket"]; acum["e"] += rq["g_beis"]
            acum["pa"] += rq["partidos"]; acum["pi"] += rq["picheos"]
        filas.append({"Quincena": "TOTAL DEL MES", "Partidos": acum["pa"], "🏀 Básquetbol": money(acum["b"]),
                      "Picheos": f"{acum['pi']:,}", "⚾ Béisbol": money(acum["e"]),
                      "💰 Total": money(acum["b"] + acum["e"])})
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

        # Solo admin en modo global y consolidado: desglose por operador
        if es_admin and target_id == 0:
            st.markdown("---")
            st.subheader("👥 Ganancias por operador en el periodo")
            df_op = resumen_por_operador(per["ini"], per["fin"])
            if df_op.empty:
                st.caption("Sin datos.")
            else:
                vista = pd.DataFrame({
                    "Operador": df_op["nombre"] + " (@" + df_op["username"] + ")",
                    "Partidos": df_op["partidos"].astype(int),
                    "🏀 Básquetbol": df_op["basket"].map(money),
                    "Picheos": df_op["picheos"].astype(int).map(lambda x: f"{x:,}"),
                    "⚾ Béisbol": df_op["beisbol"].map(money),
                    "💰 Total": df_op["total"].map(money),
                })
                st.dataframe(vista, use_container_width=True, hide_index=True)

    # =========================================================
    # MÓDULO BÁSQUETBOL
    # =========================================================
    elif opcion_menu == M_BASKET:
        st.title("🏀 ESAM Analytics — Módulo Básquetbol")
        target_id, target_label = selector_usuario("basket", es_admin, user_id)
        per = selector_periodo("basket")
        f_ini, f_fin = per["ini"], per["fin"]

        st.caption("Control financiero y tiempos de partidos por quincena")
        st.info(f"📅 **{per['etiqueta']}** · {texto_periodo(per)}")

        with st.expander("➕ Registrar Nuevo Partido de Básquetbol", expanded=False):
            modalidad_sel = st.radio("Modalidad:", ["🏀 Quincenal Estándar", "⚡ En Vivo Normal", "🔥 En Vivo NBA"])
            cf1, cf2, cf3 = st.columns(3)
            with cf1:
                fecha_p = st.date_input("Fecha", value=date.today(), key="b_fecha")
            with cf2:
                codigo_p = st.text_input("Código de Partido", placeholder="Ej: 1042")
            with cf3:
                tiempo_p = st.text_input("Tiempo Ejecución", placeholder="HH:MM:SS")

            if "NBA" in modalidad_sel:
                t_guardar = "en_vivo_nba"
                tarifa_calc = obtener_tarifa_basket("en_vivo_nba")
            elif "Normal" in modalidad_sel:
                t_guardar = "en_vivo_normal"
                tarifa_calc = obtener_tarifa_basket("en_vivo_normal")
            else:
                t_guardar = "quincenal"
                iq_i, iq_f = quincena_de(fecha_p)
                df_cnt = consultar_df("""
                    SELECT COUNT(*) AS n FROM partidos
                    WHERE usuario_id = %s AND fecha BETWEEN %s AND %s
                      AND (tipo_partido IS NULL OR tipo_partido = 'quincenal');
                """, (user_id, iq_i, iq_f))
                cnt_q = int(df_cnt["n"].iloc[0]) if not df_cnt.empty else 0
                tarifa_calc = obtener_tarifa_basket("quincenal", cnt_q + 1)
                st.caption(f"Este sería el partido #{cnt_q + 1} de la quincena "
                           f"{iq_i.strftime('%d/%m')}–{iq_f.strftime('%d/%m')}.")
            st.caption(f"Tarifa que se aplicará: **{money(tarifa_calc)}** · Se guarda a nombre de **{user_name}**")

            if st.button("💾 Guardar Partido", use_container_width=True):
                if not codigo_p.strip():
                    st.warning("Ingrese el código del partido.")
                elif ejecutar("""
                    INSERT INTO partidos (usuario_id, codigo_partido, fecha, tiempo_ejecucion, tarifa, tipo_partido)
                    VALUES (%s, %s, %s, %s, %s, %s);
                """, (user_id, codigo_p.strip(), fecha_p, tiempo_p.strip(), tarifa_calc, t_guardar)):
                    st.cache_data.clear()
                    st.success("✅ Partido guardado exitosamente.")
                    st.rerun()

        if target_id == 0:
            df_basket = consultar_df("""
                SELECT p.id, u.nombre AS operador, p.codigo_partido, p.fecha, p.tiempo_ejecucion,
                       p.tarifa, p.tipo_partido
                FROM partidos p JOIN usuarios u ON p.usuario_id = u.id
                WHERE p.fecha BETWEEN %s AND %s
                ORDER BY p.fecha DESC, p.id DESC;
            """, (f_ini, f_fin))
        else:
            df_basket = consultar_df("""
                SELECT id, codigo_partido, fecha, tiempo_ejecucion, tarifa, tipo_partido
                FROM partidos
                WHERE usuario_id = %s AND fecha BETWEEN %s AND %s
                ORDER BY fecha DESC, id DESC;
            """, (target_id, f_ini, f_fin))

        st.markdown(f"### 📋 Registros de Básquetbol — {per['etiqueta']}")
        if df_basket.empty:
            st.info("No hay registros de básquetbol para el periodo seleccionado.")
        else:
            df_basket["tarifa"] = df_basket["tarifa"].astype(float)
            total_gan = df_basket["tarifa"].sum()
            k1, k2, k3 = st.columns(3)
            k1.metric("🏀 Total Partidos", len(df_basket))
            k2.metric("💵 Total Ganado", money(total_gan))
            k3.metric("📅 Periodo", f"{f_ini.strftime('%d/%m')} - {f_fin.strftime('%d/%m/%Y')}"
                      if per["etiqueta"] != "Todos los registros" else "Histórico")

            st.dataframe(df_basket, use_container_width=True, hide_index=True)

            with st.expander("🛠️ Modificar o Eliminar Registros de Básquetbol"):
                etiquetas = {int(r.id): f"#{r.id} · {r.fecha} · {r.codigo_partido}"
                             + (f" · {r.operador}" if "operador" in df_basket.columns else "")
                             for r in df_basket.itertuples()}
                tab_e, tab_d = st.tabs(["✏️ Modificar Partido", "🗑️ Eliminar Partido"])

                with tab_e:
                    id_edit = st.selectbox("Partido a modificar:", list(etiquetas),
                                           format_func=etiquetas.get, key="sel_edit_b")
                    row = df_basket[df_basket["id"] == id_edit].iloc[0]
                    t_actual = row["tiempo_ejecucion"]
                    with st.form(f"form_edit_b_{id_edit}"):
                        fe = st.date_input("Fecha", value=pd.to_datetime(row["fecha"]).date())
                        cod = st.text_input("Código de Partido", value=str(row["codigo_partido"]))
                        tmp = st.text_input("Tiempo de Ejecución", value="" if pd.isna(t_actual) else str(t_actual))
                        tar = st.number_input("Tarifa ($) — solo editable por el admin", value=float(row["tarifa"]),
                                              step=0.25, disabled=not es_admin)
                        if st.form_submit_button("💾 Guardar Cambios"):
                            if es_admin:
                                ok = ejecutar("""
                                    UPDATE partidos SET fecha=%s, codigo_partido=%s, tiempo_ejecucion=%s, tarifa=%s
                                    WHERE id=%s;
                                """, (fe, cod.strip(), tmp.strip(), tar, id_edit))
                            else:
                                ok = ejecutar("""
                                    UPDATE partidos SET fecha=%s, codigo_partido=%s, tiempo_ejecucion=%s
                                    WHERE id=%s AND usuario_id=%s;
                                """, (fe, cod.strip(), tmp.strip(), id_edit, user_id))
                            if ok:
                                st.cache_data.clear()
                                st.success("✅ Partido modificado con éxito.")
                                st.rerun()

                with tab_d:
                    id_del = st.selectbox("Partido a eliminar:", list(etiquetas),
                                          format_func=etiquetas.get, key="sel_del_b")
                    confirma = st.checkbox("Confirmo que quiero eliminar este partido", key="chk_del_b")
                    if st.button("🚨 Eliminar Partido", use_container_width=True, disabled=not confirma):
                        if es_admin:
                            ok = ejecutar("DELETE FROM partidos WHERE id = %s;", (id_del,))
                        else:
                            ok = ejecutar("DELETE FROM partidos WHERE id = %s AND usuario_id = %s;", (id_del, user_id))
                        if ok:
                            st.cache_data.clear()
                            st.success("🗑️ Partido eliminado correctamente.")
                            st.rerun()

            st.download_button(
                "📥 Exportar Reporte de Básquetbol (CSV)",
                data=df_basket.to_csv(index=False).encode("utf-8"),
                file_name=f"esam_basket_{f_ini}_al_{f_fin}.csv",
                mime="text/csv",
            )

    # =========================================================
    # MÓDULO BÉISBOL
    # =========================================================
    elif opcion_menu == M_BEIS:
        st.title("⚾ ESAM Analytics — Módulo Béisbol")
        target_id, target_label = selector_usuario("beis", es_admin, user_id)
        per = selector_periodo("beis")
        f_ini, f_fin = per["ini"], per["fin"]

        st.caption("Control de picheos y registros por quincena")
        st.info(f"📅 **{per['etiqueta']}** · {texto_periodo(per)}")

        with st.expander("➕ Registrar Lote de Picheos", expanded=False):
            p1, p2, p3 = st.columns(3)
            with p1:
                f_pich = st.date_input("Fecha", value=date.today(), key="p_fich")
            with p2:
                id_ctrl = st.text_input("ID Control / Partido", placeholder="Ej: BC-2026")
            with p3:
                cant_pich = st.number_input("Cantidad de Picheos", min_value=1, step=1, value=100)
            st.caption(f"Se guarda a nombre de **{user_name}**")

            if st.button("💾 Guardar Picheos", use_container_width=True):
                if not id_ctrl.strip():
                    st.warning("Ingrese el ID de control.")
                elif ejecutar("""
                    INSERT INTO picheos (usuario_id, fecha, id_control, cantidad) VALUES (%s, %s, %s, %s);
                """, (user_id, f_pich, id_ctrl.strip(), int(cant_pich))):
                    st.cache_data.clear()
                    st.success("✅ Picheos guardados correctamente.")
                    st.rerun()

        if target_id == 0:
            df_pich = consultar_df("""
                SELECT pi.id, u.nombre AS operador, pi.fecha, pi.id_control, pi.cantidad
                FROM picheos pi JOIN usuarios u ON pi.usuario_id = u.id
                WHERE pi.fecha BETWEEN %s AND %s
                ORDER BY pi.fecha DESC, pi.id DESC;
            """, (f_ini, f_fin))
        else:
            df_pich = consultar_df("""
                SELECT id, fecha, id_control, cantidad
                FROM picheos
                WHERE usuario_id = %s AND fecha BETWEEN %s AND %s
                ORDER BY fecha DESC, id DESC;
            """, (target_id, f_ini, f_fin))

        st.markdown(f"### 📋 Listado de Picheos — {per['etiqueta']}")
        if df_pich.empty:
            st.info("No hay registros de picheos para el periodo seleccionado.")
        else:
            total_p = int(df_pich["cantidad"].sum())
            precio_u = obtener_tasas_globales()["precio_beisbol"]
            k1, k2, k3 = st.columns(3)
            k1.metric("⚾ Total Picheos", f"{total_p:,}")
            k2.metric("💵 Total Ganado", money(total_p * precio_u), f"@ ${precio_u}/u")
            k3.metric("📦 Lotes Registrados", len(df_pich))

            st.dataframe(df_pich, use_container_width=True, hide_index=True)

            with st.expander("🛠️ Modificar o Eliminar Lotes de Picheos"):
                etiquetas = {int(r.id): f"#{r.id} · {r.fecha} · {r.id_control} · {r.cantidad:,}"
                             + (f" · {r.operador}" if "operador" in df_pich.columns else "")
                             for r in df_pich.itertuples()}
                tab_e, tab_d = st.tabs(["✏️ Modificar Lote", "🗑️ Eliminar Lote"])

                with tab_e:
                    id_edit = st.selectbox("Lote a modificar:", list(etiquetas),
                                           format_func=etiquetas.get, key="sel_edit_p")
                    row = df_pich[df_pich["id"] == id_edit].iloc[0]
                    with st.form(f"form_edit_p_{id_edit}"):
                        fe = st.date_input("Fecha", value=pd.to_datetime(row["fecha"]).date())
                        idc = st.text_input("ID Control / Partido", value=str(row["id_control"]))
                        cant = st.number_input("Cantidad de Picheos", value=int(row["cantidad"]), step=1, min_value=1)
                        if st.form_submit_button("💾 Guardar Cambios"):
                            if es_admin:
                                ok = ejecutar("UPDATE picheos SET fecha=%s, id_control=%s, cantidad=%s WHERE id=%s;",
                                              (fe, idc.strip(), int(cant), id_edit))
                            else:
                                ok = ejecutar("""
                                    UPDATE picheos SET fecha=%s, id_control=%s, cantidad=%s
                                    WHERE id=%s AND usuario_id=%s;
                                """, (fe, idc.strip(), int(cant), id_edit, user_id))
                            if ok:
                                st.cache_data.clear()
                                st.success("✅ Lote modificado con éxito.")
                                st.rerun()

                with tab_d:
                    id_del = st.selectbox("Lote a eliminar:", list(etiquetas),
                                          format_func=etiquetas.get, key="sel_del_p")
                    confirma = st.checkbox("Confirmo que quiero eliminar este lote", key="chk_del_p")
                    if st.button("🚨 Eliminar Lote", use_container_width=True, disabled=not confirma):
                        if es_admin:
                            ok = ejecutar("DELETE FROM picheos WHERE id = %s;", (id_del,))
                        else:
                            ok = ejecutar("DELETE FROM picheos WHERE id = %s AND usuario_id = %s;", (id_del, user_id))
                        if ok:
                            st.cache_data.clear()
                            st.success("🗑️ Lote eliminado correctamente.")
                            st.rerun()

            st.download_button(
                "📥 Exportar Reporte de Béisbol (CSV)",
                data=df_pich.to_csv(index=False).encode("utf-8"),
                file_name=f"esam_beisbol_{f_ini}_al_{f_fin}.csv",
                mime="text/csv",
            )

    # =========================================================
    # ADMINISTRACIÓN DE PRECIOS (SOLO ADMIN)
    # =========================================================
    elif opcion_menu == M_PRECIOS and es_admin_estricto:
        st.title("⚙️ Control y Configuración de Tarifas")
        st.caption("Ajusta los valores en USD asignados a cada disciplina")
        tasas = obtener_tasas_globales()

        tab_b, tab_e = st.tabs(["🏀 Tarifas de Básquetbol", "⚾ Precios de Béisbol"])

        with tab_b:
            with st.form("form_admin_basket_prices"):
                st.markdown("##### 📈 Tramos Quincenales (USD por partido)")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    nt1 = st.number_input("Tramo 1 (1 - 11 partidos)", value=tasas["tramo_1"], step=0.25)
                with c2:
                    nt2 = st.number_input("Tramo 2 (12 - 14 partidos)", value=tasas["tramo_2"], step=0.25)
                with c3:
                    nt3 = st.number_input("Tramo 3 (15 - 29 partidos)", value=tasas["tramo_3"], step=0.25)
                with c4:
                    nt4 = st.number_input("Tramo 4 (30+ partidos)", value=tasas["tramo_4"], step=0.25)
                st.markdown("---")
                st.markdown("##### ⚡ Modalidad En Vivo")
                e1, e2 = st.columns(2)
                with e1:
                    n_norm = st.number_input("Partido En Vivo Normal ($)", value=tasas["en_vivo_normal"], step=0.50)
                with e2:
                    n_nba = st.number_input("Partido En Vivo NBA ($)", value=tasas["en_vivo_nba"], step=0.50)
                st.caption("Los cambios aplican a partidos NUEVOS; los ya registrados conservan su tarifa.")
                if st.form_submit_button("💾 Actualizar Tarifas de Básquetbol", use_container_width=True):
                    for k, v in (("tasa_tramo_1", nt1), ("tasa_tramo_2", nt2), ("tasa_tramo_3", nt3),
                                 ("tasa_tramo_4", nt4), ("tasa_en_vivo_normal", n_norm), ("tasa_en_vivo_nba", n_nba)):
                        actualizar_tasa_global(k, v)
                    st.success("✅ Tarifas de Básquetbol actualizadas.")
                    st.rerun()

        with tab_e:
            with st.form("form_admin_beis_prices"):
                n_precio = st.number_input("Precio por Picheo (USD)", value=tasas["precio_beisbol"],
                                           format="%.4f", step=0.001)
                st.caption("⚠️ El béisbol se calcula con el precio vigente: al cambiarlo se recalcula TODO el histórico.")
                if st.form_submit_button("💾 Actualizar Precio de Béisbol", use_container_width=True):
                    actualizar_tasa_global("precio_beisbol", n_precio)
                    st.success("✅ Precio por picheo actualizado.")
                    st.rerun()

    # =========================================================
    # SEGURIDAD Y CONTRASEÑAS (SOLO ADMIN)
    # =========================================================
    elif opcion_menu == M_SEG and es_admin_estricto:
        st.title("🔐 Seguridad y Contraseñas (Administrador)")

        tab_mi, tab_reset, tab_users = st.tabs(
            ["🔑 Cambiar mi contraseña", "♻️ Restablecer contraseña de usuario", "👥 Usuarios"]
        )

        with tab_mi:
            with st.form("form_cambiar_pass"):
                pass_vieja = st.text_input("Contraseña Actual", type="password")
                pass_nueva = st.text_input("Nueva Contraseña", type="password")
                pass_conf = st.text_input("Confirmar Nueva Contraseña", type="password")
                if st.form_submit_button("🔒 Actualizar Contraseña", use_container_width=True):
                    if not (pass_vieja and pass_nueva and pass_conf):
                        st.warning("Complete todos los campos.")
                    elif pass_nueva != pass_conf:
                        st.error("Las nuevas contraseñas no coinciden.")
                    elif len(pass_nueva) < 6:
                        st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                    elif not autenticar_usuario(username_actual, pass_vieja):
                        st.error("❌ La contraseña actual es incorrecta.")
                    else:
                        ok, msg = cambiar_password_usuario(user_id, pass_nueva)
                        (st.success if ok else st.error)(msg)

        with tab_reset:
            df_u = obtener_todos_los_usuarios()
            if df_u.empty:
                st.info("No hay usuarios.")
            else:
                mapa = {int(r.id): f"{r.nombre} (@{r.username})" for r in df_u.itertuples()}
                with st.form("form_reset_pass"):
                    uid_sel = st.selectbox("Usuario:", list(mapa), format_func=mapa.get)
                    n1 = st.text_input("Nueva contraseña", type="password")
                    n2 = st.text_input("Confirmar nueva contraseña", type="password")
                    if st.form_submit_button("♻️ Restablecer Contraseña", use_container_width=True):
                        if not (n1 and n2):
                            st.warning("Complete ambos campos.")
                        elif n1 != n2:
                            st.error("Las contraseñas no coinciden.")
                        elif len(n1) < 6:
                            st.error("Debe tener al menos 6 caracteres.")
                        else:
                            ok, msg = cambiar_password_usuario(uid_sel, n1)
                            (st.success if ok else st.error)(f"{msg} ({mapa[uid_sel]})")

        with tab_users:
            df_u = obtener_todos_los_usuarios()
            if not df_u.empty:
                st.dataframe(
                    df_u.rename(columns={"username": "Usuario", "nombre": "Nombre", "rol": "Rol",
                                         "total_partidos_basket": "Partidos basket",
                                         "total_lotes_beisbol": "Lotes béisbol"}),
                    use_container_width=True, hide_index=True,
                )
