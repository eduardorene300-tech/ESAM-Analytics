from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
import streamlit as st
import plotly.express as px

# =========================================================
# 0. ZONA HORARIA LOCAL (EL SERVIDOR TRABAJA EN UTC)
# =========================================================
# El servidor (Streamlit Cloud / Neon) usa UTC. A partir de la noche, en UTC
# ya es el día siguiente y por eso las cargas quedaban con la fecha de mañana.
# Aquí se fija el desfase real del operador.
ZONA_HORARIA_UTC_OFFSET = -4  # Venezuela / Bolivia (UTC-4). Ajusta si cambias de país.


def ahora_local():
    """Fecha y hora local real del operador (UTC + desfase)."""
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=ZONA_HORARIA_UTC_OFFSET)


def hoy_local():
    """Fecha de HOY según la hora local del operador (nunca la del servidor)."""
    return ahora_local().date()


# =========================================================
# 0.1 UTILIDADES DE TIEMPO DE PARTIDO (HH:MM:SS)
# =========================================================
def parsear_tiempo_a_segundos(valor):
    """Convierte 'HH:MM:SS', 'MM:SS' o 'SS' a segundos. None si no es válido."""
    if valor is None or pd.isna(valor):
        return None
    texto_val = str(valor).strip()
    if not texto_val or texto_val.lower() in ("none", "nan", "nat", "null"):
        return None
    partes = texto_val.split(":")
    try:
        numeros = [int(float(p)) for p in partes]
    except ValueError:
        return None
    if len(numeros) == 3:
        horas, minutos, segundos = numeros
    elif len(numeros) == 2:
        horas, minutos, segundos = 0, numeros[0], numeros[1]
    elif len(numeros) == 1:
        horas, minutos, segundos = 0, 0, numeros[0]
    else:
        return None
    return horas * 3600 + minutos * 60 + segundos


def formatear_segundos(segundos):
    """Convierte segundos a texto HH:MM:SS legible."""
    if segundos is None:
        return "—"
    total = int(round(segundos))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


# =========================================================
# 1. CONFIGURACIÓN GENERAL DE LA PÁGINA Y ESTILOS VISUALES
# =========================================================
st.set_page_config(
    page_title="ESAM Analytics 360°",
    page_icon="💻",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Barlow:wght@300;400;500;600&display=swap');
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
    border-radius: 14px !important; padding: 1rem !important; }
[data-testid="stMetricLabel"] { font-family: 'Rajdhani', sans-serif !important;
    font-size: 0.85rem !important; letter-spacing: 0.05em !important;
    color: #7A90A8 !important; font-weight: 600 !important; white-space: nowrap !important; }
[data-testid="stMetricValue"] { font-family: 'Rajdhani', sans-serif !important;
    font-size: 2.1rem !important; font-weight: 700 !important; color: #00AAFF !important; }
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# =========================================================
# 2. SEGURIDAD Y ENCRIPTACIÓN (PBKDF2-SHA256 CON SAL)
# =========================================================
PBKDF2_ITERACIONES = 240_000


def hash_password(password: str) -> str:
    """Hash con sal aleatoria: pbkdf2_sha256$iteraciones$sal$hash."""
    sal = os.urandom(16)
    digesto = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), sal, PBKDF2_ITERACIONES)
    return f"pbkdf2_sha256${PBKDF2_ITERACIONES}${sal.hex()}${digesto.hex()}"


def verificar_password(password: str, hash_guardado) -> bool:
    """Verifica la clave contra el hash nuevo (con sal) o el viejo SHA-256."""
    if not hash_guardado:
        return False
    guardado = str(hash_guardado)
    if guardado.startswith("pbkdf2_sha256$"):
        try:
            _, iteraciones, sal_hex, digesto_hex = guardado.split("$")
            digesto = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), bytes.fromhex(sal_hex), int(iteraciones)
            )
            return hmac.compare_digest(digesto.hex(), digesto_hex)
        except Exception:
            return False
    # Compatibilidad con el hash antiguo (SHA-256 sin sal), se migra al iniciar sesión
    return hmac.compare_digest(hashlib.sha256(password.encode("utf-8")).hexdigest(), guardado)


def hash_es_legado(hash_guardado) -> bool:
    """True si el hash guardado es del esquema viejo (sin sal) o está vacío."""
    return not str(hash_guardado or "").startswith("pbkdf2_sha256$")


def _secreto(clave, defecto=None):
    try:
        if clave in st.secrets:
            return st.secrets[clave]
    except Exception:
        pass
    return defecto


# Contraseña inicial del admin. Puedes fijarla en st.secrets con: admin_password = "..."
ADMIN_PASSWORD_INICIAL = _secreto("admin_password", "admin123")

# Aviso único si las tarifas no se pueden leer de la base de datos
AVISO_TASAS_MOSTRADO = {"visto": False}


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


def cerrar_conexion(conn):
    """Cierra la conexión sin romper la app si ya estaba cerrada."""
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass


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

            # El hash nuevo (PBKDF2 con sal) ocupa más de 64 caracteres
            try:
                cur.execute("ALTER TABLE usuarios ALTER COLUMN password_hash TYPE VARCHAR(200);")
            except Exception:
                conn.rollback()
                cur = conn.cursor()

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

            # Índices: sin ellos cada consulta recorre la tabla completa
            cur.execute("CREATE INDEX IF NOT EXISTS idx_partidos_usuario_fecha ON partidos (usuario_id, fecha);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_partidos_fecha ON partidos (fecha);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_picheos_usuario_fecha ON picheos (usuario_id, fecha);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_picheos_fecha ON picheos (fecha);")

            defaults = [
                ("tasa_tramo_1", 6.00),
                ("tasa_tramo_2", 6.50),
                ("tasa_tramo_3", 7.00),
                ("tasa_tramo_4", 7.50),
                ("tasa_tramo_5", 8.00),
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

            # Migración única al esquema de 5 tramos de básquetbol
            cur.execute("SELECT valor FROM configuracion_global WHERE clave = 'esquema_tramos_basket';")
            if cur.fetchone() is None:
                tramos_nuevos = [
                    ("tasa_tramo_1", 6.00),
                    ("tasa_tramo_2", 6.50),
                    ("tasa_tramo_3", 7.00),
                    ("tasa_tramo_4", 7.50),
                    ("tasa_tramo_5", 8.00),
                ]
                for clave_t, val_t in tramos_nuevos:
                    cur.execute("""
                        INSERT INTO configuracion_global (clave, valor)
                        VALUES (%s, %s)
                        ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor;
                    """, (clave_t, val_t))
                cur.execute("""
                    INSERT INTO configuracion_global (clave, valor)
                    VALUES ('esquema_tramos_basket', 2)
                    ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor;
                """)

            # El admin se crea una sola vez: no se resetea la clave en cada arranque
            admin_hash = hash_password(ADMIN_PASSWORD_INICIAL)
            try:
                cur.execute("""
                    INSERT INTO usuarios (username, nombre, password_hash, rol)
                    VALUES ('admin', 'Administrador Global', %s, 'admin')
                    ON CONFLICT (username) DO NOTHING;
                """, (admin_hash,))
            except Exception:
                conn.rollback()
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO usuarios (username, nombre, password, password_hash, rol)
                    VALUES ('admin', 'Administrador Global', %s, %s, 'admin')
                    ON CONFLICT (username) DO NOTHING;
                """, (ADMIN_PASSWORD_INICIAL, admin_hash))

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
# 5. CONSULTAS OPTIMIZADAS Y RECÁLCULO RETROACTIVO ESTRICTO
# =========================================================
@st.cache_data(ttl=5)
def obtener_tasas_globales():
    tasas = {
        "tramo_1": 6.00,
        "tramo_2": 6.50,
        "tramo_3": 7.00,
        "tramo_4": 7.50,
        "tramo_5": 8.00,
        "en_vivo_normal": 12.00,
        "en_vivo_nba": 18.50,
        "precio_beisbol": 0.024,
    }
    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT clave, valor FROM configuracion_global;")
            for r in cur.fetchall():
                k = r["clave"]
                val = float(r["valor"])
                if k == "tasa_tramo_1": tasas["tramo_1"] = val
                elif k == "tasa_tramo_2": tasas["tramo_2"] = val
                elif k == "tasa_tramo_3": tasas["tramo_3"] = val
                elif k == "tasa_tramo_4": tasas["tramo_4"] = val
                elif k == "tasa_tramo_5": tasas["tramo_5"] = val
                elif k == "tasa_en_vivo_normal": tasas["en_vivo_normal"] = val
                elif k == "tasa_en_vivo_nba": tasas["en_vivo_nba"] = val
                elif k == "precio_beisbol": tasas["precio_beisbol"] = val
        except Exception as e:
            # No se oculta el fallo: sin BD se estarían usando precios de fábrica
            if not AVISO_TASAS_MOSTRADO["visto"]:
                AVISO_TASAS_MOSTRADO["visto"] = True
                st.warning(f"⚠️ No se pudieron leer las tarifas de la base de datos ({e}). Se muestran las de fábrica.")
        finally:
            try:
                if cur is not None: cur.close()
            except Exception:
                pass
            cerrar_conexion(conn)
    return tasas


def actualizar_tasa_global(clave, nuevo_valor):
    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("UPDATE configuracion_global SET valor = %s WHERE clave = %s;", (nuevo_valor, clave))
            conn.commit()
            st.cache_data.clear()
            return True
        except Exception as e:
            conn.rollback()
            st.error(f"Error al actualizar tasa: {e}")
            return False
        finally:
            try:
                if cur is not None: cur.close()
            except Exception:
                pass
            cerrar_conexion(conn)
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
        elif cant_partidos <= 26: return tasas["tramo_3"]
        elif cant_partidos <= 29: return tasas["tramo_4"]
        else: return tasas["tramo_5"]


def recalcular_tarifas_quincena_basket(u_id, fecha_ref):
    """
    1. Cuenta EXCLUSIVAMENTE los partidos de modalidad 'quincenal' en la quincena dada.
    2. Los partidos 'en_vivo_normal' y 'en_vivo_nba' NO CUENTAN para el volumen del tramo.
    3. Actualiza RETROACTIVAMENTE solo la tarifa de los partidos 'quincenal' al tramo correspondiente.
    """
    iq_i, iq_f = obtener_rango_quincena(fecha_ref)
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            # Si u_id es 0 (Consolidado Admin), recalcula para cada usuario individualmente
            if u_id == 0:
                cur.execute("SELECT id FROM usuarios;")
                usuarios_list = [r[0] for r in cur.fetchall()]
                for uid in usuarios_list:
                    recalcular_tarifas_quincena_basket(uid, fecha_ref)
                cur.close()
                conn.close()
                return

            # Contar ÚNICAMENTE partidos de modalidad 'quincenal' (los en vivo no suman)
            cur.execute("""
                SELECT COUNT(*) FROM partidos 
                WHERE usuario_id = %s 
                  AND fecha >= %s 
                  AND fecha <= %s 
                  AND (tipo_partido IS NULL OR tipo_partido = 'quincenal');
            """, (u_id, iq_i, iq_f))
            partidos_quincenales_contados = cur.fetchone()[0]

            # Determinar la tarifa del tramo alcanzado
            nueva_tarifa = obtener_tarifa_basket("quincenal", partidos_quincenales_contados)

            # Actualizar ÚNICAMENTE la tarifa de los partidos de modalidad 'quincenal'
            cur.execute("""
                UPDATE partidos 
                SET tarifa = %s 
                WHERE usuario_id = %s 
                  AND fecha >= %s 
                  AND fecha <= %s 
                  AND (tipo_partido IS NULL OR tipo_partido = 'quincenal');
            """, (nueva_tarifa, u_id, iq_i, iq_f))

            conn.commit()
        except Exception as e:
            st.error(f"Error al recalcular quincena: {e}")
        finally:
            try:
                cur.close()
            except Exception:
                pass
            cerrar_conexion(conn)


def recalcular_si_hace_falta(u_id, fecha_ref):
    """Recalcula la quincena una sola vez por sesión (evita consultas en cada clic)."""
    iq_i, iq_f = obtener_rango_quincena(fecha_ref)
    hechos = st.session_state.setdefault("_recalculos_hechos", set())
    clave = f"{u_id}|{iq_i}|{iq_f}"
    if clave in hechos:
        return
    recalcular_tarifas_quincena_basket(u_id, fecha_ref)
    hechos.add(clave)


def olvidar_recalculos():
    """Fuerza a recalcular en la próxima vista (tras cambiar datos o precios)."""
    st.session_state["_recalculos_hechos"] = set()


# =========================================================
# 6. GESTIÓN DE USUARIOS Y FECHAS DE QUINCENA
# =========================================================
def registrar_usuario(username, nombre, password, rol="operador"):
    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO usuarios (username, nombre, password_hash, rol)
                VALUES (%s, %s, %s, %s);
            """, (username.lower().strip(), nombre.strip(), hash_password(password), rol))
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
            try:
                if cur is not None: cur.close()
            except Exception:
                pass
            cerrar_conexion(conn)
    return False, "❌ Error de conexión a BD."


def autenticar_usuario(username, password):
    """Valida la clave en Python y migra el hash viejo en el mismo inicio de sesión."""
    user_clean = username.lower().strip()
    pass_clean = password.strip()

    conn = get_db_connection()
    if not conn:
        return None

    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT id, username, nombre, rol, password_hash, password
                FROM usuarios WHERE username = %s;
            """, (user_clean,))
            fila = cur.fetchone()
        except Exception:
            # Bases antiguas sin columna 'password'
            conn.rollback()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT id, username, nombre, rol, password_hash
                FROM usuarios WHERE username = %s;
            """, (user_clean,))
            fila = cur.fetchone()

        if not fila:
            return None

        clave_plana = fila.get("password")
        coincide = verificar_password(pass_clean, fila.get("password_hash"))
        if not coincide and clave_plana and hmac.compare_digest(str(clave_plana), pass_clean):
            coincide = True
        if not coincide:
            return None

        # Migración silenciosa: pasa de SHA-256/plano a PBKDF2 con sal
        if hash_es_legado(fila.get("password_hash")) or clave_plana:
            try:
                cur.execute(
                    "UPDATE usuarios SET password_hash = %s, password = NULL WHERE id = %s;",
                    (hash_password(pass_clean), fila["id"]),
                )
                conn.commit()
            except Exception:
                conn.rollback()

        return {"id": fila["id"], "username": fila["username"], "nombre": fila["nombre"], "rol": fila["rol"]}
    except Exception as e:
        st.error(f"Error al autenticar: {e}")
        return None
    finally:
        try:
            if cur is not None: cur.close()
        except Exception:
            pass
        cerrar_conexion(conn)


def cambiar_password_usuario(user_id, nueva_password):
    conn = get_db_connection()
    if conn:
        cur = None
        try:
            cur = conn.cursor()
            nuevo_hash = hash_password(nueva_password)
            try:
                cur.execute(
                    "UPDATE usuarios SET password_hash = %s, password = NULL WHERE id = %s;",
                    (nuevo_hash, user_id),
                )
            except Exception:
                conn.rollback()
                cur = conn.cursor()
                cur.execute("UPDATE usuarios SET password_hash = %s WHERE id = %s;", (nuevo_hash, user_id))
            conn.commit()
            return True, "✅ Contraseña actualizada correctamente."
        except Exception as e:
            conn.rollback()
            return False, f"❌ Error al actualizar contraseña: {e}"
        finally:
            try:
                if cur is not None: cur.close()
            except Exception:
                pass
            cerrar_conexion(conn)
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
        return df
    except Exception as e:
        st.error(f"Error al cargar usuarios: {e}")
        return pd.DataFrame()
    finally:
        cerrar_conexion(conn)


def obtener_rango_quincena(fecha_ref, numero_quincena=None):
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


RANGOS_PERIODO = [
    "Todos los Registros",
    "1. 1.ª Quincena (Días 1 al 15)",
    "2. 2.ª Quincena (Días 16 al final de mes)",
    "Quincena Anterior",
    "Este Mes Completo",
    "Rango de Fechas Personalizado",
]


def selector_periodo(clave, titulo):
    """Dibuja el filtro de quincena/periodo y devuelve (fecha_inicio, fecha_fin)."""
    hoy = hoy_local()
    seleccion = st.sidebar.selectbox(titulo, RANGOS_PERIODO, key=clave)

    if "1. 1.ª Quincena" in seleccion:
        return obtener_rango_quincena(hoy, numero_quincena=1)
    if "2. 2.ª Quincena" in seleccion:
        return obtener_rango_quincena(hoy, numero_quincena=2)
    if seleccion == "Quincena Anterior":
        if hoy.day <= 15:
            primer_dia_mes_actual = date(hoy.year, hoy.month, 1)
            ultimo_dia_mes_pasado = primer_dia_mes_actual - timedelta(days=1)
            return obtener_rango_quincena(ultimo_dia_mes_pasado, numero_quincena=2)
        return obtener_rango_quincena(hoy, numero_quincena=1)
    if seleccion == "Este Mes Completo":
        fin_mes = date(hoy.year, 12, 31) if hoy.month == 12 else date(hoy.year, hoy.month + 1, 1) - timedelta(days=1)
        return date(hoy.year, hoy.month, 1), fin_mes
    if seleccion == "Rango de Fechas Personalizado":
        col_desde, col_hasta = st.sidebar.columns(2)
        with col_desde:
            f_ini = st.date_input("Desde", value=hoy - timedelta(days=30), key=f"{clave}_desde")
        with col_hasta:
            f_fin = st.date_input("Hasta", value=hoy, key=f"{clave}_hasta")
        if f_ini > f_fin:
            st.sidebar.warning("⚠️ 'Desde' es posterior a 'Hasta'. Se invirtieron las fechas.")
            f_ini, f_fin = f_fin, f_ini
        return f_ini, f_fin
    return date(2020, 1, 1), date(2035, 12, 31)


# =========================================================
# 7. MANEJO DE SESIÓN Y AUTENTICACIÓN
# =========================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_info" not in st.session_state:
    st.session_state.user_info = None

if not st.session_state.authenticated:
    st.markdown("<h1 style='text-align: center; color: #00AAFF;'>💻 ESAM ANALYTICS 360°</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #7A90A8;'>Plataforma Profesional de Estadísticas y Control Operativo</p>", unsafe_allow_html=True)

    tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrar Usuario"])

    with tab_login:
        st.subheader("Ingreso de Operadores")
        with st.form("form_login"):
            user_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Entrar al Sistema", use_container_width=True)

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

    st.sidebar.markdown("""
        <div style='text-align: center; padding: 10px 0;'>
            <h2 style='color: #00AAFF; margin-bottom: 0; font-family: "Rajdhani", sans-serif;'>💻 ESAM ANALYTICS</h2>
            <p style='color: #7A90A8; font-size: 0.8rem; letter-spacing: 2px;'>360° STATS PRO</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.write(f"👤 **Analista:** {user_name}")
    
    opciones_menu_list = [
        "📊 Panel General y Estadísticas",
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
    # MÓDULO: PANTALLA PRINCIPAL
    # =========================================================
    if opcion_menu == "📊 Panel General y Estadísticas":
        st.title("📊 Panel General y Análisis Estadístico 360°")
        
        target_user_id = user_id
        opcion_label = f"mis datos ({user_name})"

        if es_admin:
            df_usrs = obtener_todos_los_usuarios()
            if not df_usrs.empty:
                opciones_u = {"🌐 CONSOLIDADO GLOBAL (TODOS LOS USUARIOS)": 0}
                for _, r_u in df_usrs.iterrows():
                    opciones_u[f"👤 {r_u['nombre']} (@{r_u['username']})"] = r_u['id']
                
                st.sidebar.markdown("---")
                st.sidebar.subheader("👑 Selector de Analista")
                u_seleccionado = st.sidebar.selectbox("Ver Panel General de:", list(opciones_u.keys()))
                target_user_id = opciones_u[u_seleccionado]
                opcion_label = u_seleccionado

        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 Filtro por Quincena y Periodo")

        f_ini, f_fin = selector_periodo("gen_periodo", "Seleccionar Periodo:")

        # Recálculo automático de quincena (una sola vez por sesión)
        recalcular_si_hace_falta(target_user_id, f_ini)

        st.caption(f"Mostrando análisis operativo de: **{opcion_label}** | Periodo: **{f_ini.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}**")

        df_b_all = pd.DataFrame()
        df_beis_all = pd.DataFrame()
        conn_gen = get_db_connection()
        total_g_basket = 0.0
        total_g_beisbol = 0.0
        total_juegos_b = 0
        total_lotes_beisbol = 0
        total_pich_b = 0
        tiempo_promedio_seg = None
        juegos_con_tiempo = 0

        if conn_gen:
            try:
                if target_user_id == 0:
                    df_b_all = pd.read_sql_query("SELECT tarifa, tiempo_ejecucion, fecha FROM partidos WHERE fecha BETWEEN %s AND %s;", conn_gen, params=(f_ini, f_fin))
                    df_beis_all = pd.read_sql_query("SELECT cantidad, fecha FROM picheos WHERE fecha BETWEEN %s AND %s;", conn_gen, params=(f_ini, f_fin))
                else:
                    df_b_all = pd.read_sql_query("SELECT tarifa, tiempo_ejecucion, fecha FROM partidos WHERE usuario_id = %s AND fecha BETWEEN %s AND %s;", conn_gen, params=(target_user_id, f_ini, f_fin))
                    df_beis_all = pd.read_sql_query("SELECT cantidad, fecha FROM picheos WHERE usuario_id = %s AND fecha BETWEEN %s AND %s;", conn_gen, params=(target_user_id, f_ini, f_fin))

                if not df_b_all.empty:
                    total_g_basket = float(df_b_all["tarifa"].sum())
                    total_juegos_b = len(df_b_all)

                    # Tiempo promedio real de los partidos cargados con tiempo
                    tiempos_b = [
                        t for t in (parsear_tiempo_a_segundos(v) for v in df_b_all["tiempo_ejecucion"])
                        if t is not None
                    ]
                    if tiempos_b:
                        tiempo_promedio_seg = sum(tiempos_b) / len(tiempos_b)
                        juegos_con_tiempo = len(tiempos_b)

                if not df_beis_all.empty:
                    total_pich_b = int(df_beis_all["cantidad"].sum())
                    total_lotes_beisbol = len(df_beis_all)
                    precio_b_u = obtener_tasas_globales()["precio_beisbol"]
                    total_g_beisbol = total_pich_b * precio_b_u

            except Exception as e:
                st.error(f"Error al calcular totales: {e}")
            finally:
                cerrar_conexion(conn_gen)

        total_ganancias_general = total_g_basket + total_g_beisbol
        total_registros_brutos = total_juegos_b + total_lotes_beisbol

        promedio_basket = (total_g_basket / total_juegos_b) if total_juegos_b > 0 else 0.00
        tasas_cur = obtener_tasas_globales()

        # TARJETAS PRINCIPALES
        col_mg1, col_mg2, col_mg3, col_mg4, col_mg5 = st.columns(5)
        col_mg1.metric("💰 Total Acumulado", f"${total_ganancias_general:,.2f}", "📈 Rendimiento Alza")
        col_mg2.metric("🏀 Básquetbol Total", f"${total_g_basket:,.2f}", f"🔺 {total_juegos_b} partidos")
        col_mg3.metric("⚾ Béisbol Total", f"${total_g_beisbol:,.2f}", f"🔺 {total_pich_b:,} picheos")
        col_mg4.metric("📊 Cargas Totales", f"{total_registros_brutos} ops", "🟢 Sistema Óptimo")
        col_mg5.metric("⏱️ Tiempo Promedio", formatear_segundos(tiempo_promedio_seg), f"⏱️ {juegos_con_tiempo} partidos con tiempo")

        st.markdown("---")
        
        # VISUALIZACIÓN GRÁFICA REAL
        col_g1, col_g2 = st.columns([1, 1])

        with col_g1:
            st.subheader("📊 Distribución de Ingresos por Deporte")
            if total_ganancias_general > 0:
                data_pie = pd.DataFrame({
                    'Deporte': ['Básquetbol', 'Béisbol'],
                    'Ingresos': [total_g_basket, total_g_beisbol]
                })
                fig_pie = px.pie(data_pie, values='Ingresos', names='Deporte', 
                                 color_discrete_sequence=['#00AAFF', '#00FFCC'],
                                 hole=0.4)
                fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#E8EFF8')
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Registra datos en Básquetbol o Béisbol para el periodo seleccionado para generar gráficos.")

        with col_g2:
            st.subheader("📈 Análisis y Desglose Operativo")
            df_desglose = pd.DataFrame({
                "Disciplina": ["🏀 Básquetbol", "⚾ Béisbol"],
                "Unidades Registradas": [f"{total_juegos_b} partidos", f"{total_pich_b:,} picheos"],
                "Promedio por Carga": [f"${promedio_basket:.2f} / partido", f"${tasas_cur['precio_beisbol']:.3f} / picheo"],
                "Total USD": [f"${total_g_basket:,.2f}", f"${total_g_beisbol:,.2f}"]
            })
            st.dataframe(df_desglose, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("📈 Evolución Diaria del Periodo")
        series_diarias = []
        if not df_b_all.empty:
            tmp_b = df_b_all.copy()
            tmp_b["fecha"] = pd.to_datetime(tmp_b["fecha"])
            series_diarias.append(
                tmp_b.groupby("fecha").agg({"tarifa": "sum"}).rename(columns={"tarifa": "🏀 Básquetbol ($)"})
            )
        if not df_beis_all.empty:
            tmp_p = df_beis_all.copy()
            tmp_p["fecha"] = pd.to_datetime(tmp_p["fecha"])
            tmp_p["usd"] = tmp_p["cantidad"].astype(float) * tasas_cur["precio_beisbol"]
            series_diarias.append(
                tmp_p.groupby("fecha").agg({"usd": "sum"}).rename(columns={"usd": "⚾ Béisbol ($)"})
            )
        if series_diarias:
            df_serie = pd.concat(series_diarias, axis=1).fillna(0.0).sort_index()
            df_serie["Total ($)"] = df_serie.sum(axis=1)
            fig_serie = px.bar(
                df_serie,
                x=df_serie.index,
                y=[c for c in df_serie.columns if c != "Total ($)"],
                barmode="stack",
                color_discrete_sequence=["#00AAFF", "#00FFCC"],
                labels={"value": "Ingresos (USD)", "x": "Fecha", "variable": "Deporte"},
            )
            fig_serie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#E8EFF8", legend_title_text="",
            )
            st.plotly_chart(fig_serie, use_container_width=True)
            st.caption(
                f"Mejor día: **${df_serie['Total ($)'].max():,.2f}** | "
                f"Días con actividad: **{len(df_serie)}** | "
                f"Promedio diario: **${df_serie['Total ($)'].mean():,.2f}**"
            )
        else:
            st.info("Sin movimientos en el periodo seleccionado para graficar la evolución.")

        if es_admin and target_user_id == 0:
            st.markdown("---")
            st.subheader("👥 Auditoría General de Operadores en Sistema (Filtrado por Periodo)")
            conn_det = get_db_connection()
            if conn_det:
                try:
                    df_det = pd.read_sql_query("""
                        SELECT 
                            u.id AS "ID",
                            u.username AS "Usuario",
                            u.nombre AS "Nombre Completo",
                            COUNT(DISTINCT p.id) AS "Partidos Basket",
                            COALESCE(SUM(p.tarifa), 0.00) AS "USD Basket",
                            COALESCE(SUM(pi.cantidad), 0) AS "Total Picheos",
                            (COALESCE(SUM(pi.cantidad), 0) * (SELECT valor FROM configuracion_global WHERE clave='precio_beisbol')) AS "USD Béisbol"
                        FROM usuarios u
                        LEFT JOIN partidos p ON u.id = p.usuario_id AND p.fecha BETWEEN %s AND %s
                        LEFT JOIN picheos pi ON u.id = pi.usuario_id AND pi.fecha BETWEEN %s AND %s
                        GROUP BY u.id, u.username, u.nombre
                        ORDER BY u.id ASC;
                    """, conn_det, params=(f_ini, f_fin, f_ini, f_fin))
                    df_tiempos_det = pd.read_sql_query("""
                        SELECT u.id AS uid, p.tiempo_ejecucion
                        FROM usuarios u
                        JOIN partidos p ON u.id = p.usuario_id AND p.fecha BETWEEN %s AND %s;
                    """, conn_det, params=(f_ini, f_fin))

                    if not df_det.empty:
                        df_det["Ganancia Total ($)"] = df_det["USD Basket"] + df_det["USD Béisbol"]

                        promedios_t = {}
                        if not df_tiempos_det.empty:
                            for uid, grupo in df_tiempos_det.groupby("uid"):
                                segs = [
                                    t for t in (parsear_tiempo_a_segundos(v) for v in grupo["tiempo_ejecucion"])
                                    if t is not None
                                ]
                                promedios_t[uid] = formatear_segundos(sum(segs) / len(segs)) if segs else "—"
                        df_det["Tiempo Promedio"] = df_det["ID"].map(promedios_t).fillna("—")

                        st.dataframe(df_det, use_container_width=True, hide_index=True)

                        csv_det = df_det.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            "📥 Exportar Auditoría Consolidada (CSV)",
                            data=csv_det,
                            file_name=f"esam_auditoria_{f_ini}_al_{f_fin}.csv",
                            mime="text/csv",
                        )
                except Exception as e:
                    st.error(f"Error cargando detalle de usuarios: {e}")
                finally:
                    cerrar_conexion(conn_det)

    # =========================================================
    # MÓDULO 1: BÁSQUETBOL (RECÁLCULO RETROACTIVO GARANTIZADO)
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

        f_ini, f_fin = selector_periodo("basket_periodo", "Seleccionar Periodo:")

        # Recálculo automático de quincena (una sola vez por sesión)
        recalcular_si_hace_falta(target_b_user_id, f_ini)

        st.info(f"📅 **Periodo Evaluado:** Del **{f_ini.strftime('%d/%m/%Y')}** al **{f_fin.strftime('%d/%m/%Y')}**")

        with st.expander("➕ Registrar Nuevo Partido de Básquetbol", expanded=False):
            col_m1, _ = st.columns([2, 2])
            with col_m1:
                modalidad_sel = st.radio("Modalidad:", ["🏀 Quincenal Estándar", "⚡ En Vivo Normal", "🔥 En Vivo NBA"])

            cf1, cf2, cf3 = st.columns(3)
            with cf1: fecha_p = st.date_input("Fecha", value=hoy_local(), key="b_fecha")
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
                tarifa_calc = tasas_v["tramo_1"]

            if st.button("💾 Guardar Partido", use_container_width=True):
                tiempo_val = (tiempo_p or "").strip()
                segundos_t = parsear_tiempo_a_segundos(tiempo_val) if tiempo_val else None
                if not codigo_p.strip():
                    st.warning("Ingrese el código del partido.")
                elif tiempo_val and segundos_t is None:
                    st.error("⏱️ Tiempo inválido. Usa el formato HH:MM:SS (ejemplo: 01:42:15).")
                else:
                    tiempo_guardar = formatear_segundos(segundos_t) if segundos_t is not None else ""
                    conn_s = get_db_connection()
                    if conn_s:
                        cur_s = None
                        guardado = False
                        try:
                            cur_s = conn_s.cursor()
                            cur_s.execute("""
                                INSERT INTO partidos (usuario_id, codigo_partido, fecha, tiempo_ejecucion, tarifa, tipo_partido)
                                VALUES (%s, %s, %s, %s, %s, %s);
                            """, (user_id, codigo_p.strip(), fecha_p, tiempo_guardar, tarifa_calc, t_guardar))
                            conn_s.commit()
                            guardado = True
                        except Exception as e:
                            conn_s.rollback()
                            st.error(f"❌ No se pudo guardar el partido: {e}")
                        finally:
                            try:
                                if cur_s is not None: cur_s.close()
                            except Exception:
                                pass
                            cerrar_conexion(conn_s)

                        if guardado:
                            if t_guardar == "quincenal":
                                recalcular_tarifas_quincena_basket(user_id, fecha_p)
                            olvidar_recalculos()
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
            cerrar_conexion(conn_q)
        else:
            df_basket = pd.DataFrame()

        st.markdown(f"### 📋 Registros de Básquetbol ({f_ini.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')})")
        if not df_basket.empty:
            total_ganancias = df_basket["tarifa"].astype(float).sum()
            col_k1, col_k2, col_k3 = st.columns(3)
            col_k1.metric("🏀 Total Partidos Quincena", len(df_basket), "📈 Actividad Alta")
            col_k2.metric("💵 Total Ganancias Quincena", f"${total_ganancias:.2f}", "🔺 En Alza")
            col_k3.metric("📅 Rango Evaluado", f"{f_ini.strftime('%d/%m')} - {f_fin.strftime('%d/%m/%Y')}")

            st.dataframe(df_basket, use_container_width=True, hide_index=True)

            with st.expander("🛠️ Modificar, Corregir o Eliminar Cargas de Básquetbol"):
                tab_eb1, tab_eb2 = st.tabs(["✏️ Modificar / Corregir Partido", "🗑️ Eliminar Partido"])
                
                with tab_eb1:
                    list_ids_b = df_basket["id"].tolist()
                    id_edit_b = st.selectbox("Seleccione el ID del partido a corregir:", list_ids_b, key="sel_edit_b")
                    
                    row_b = df_basket[df_basket["id"] == id_edit_b].iloc[0]
                    with st.form("form_edit_b"):
                        fe_b = st.date_input("Fecha", value=pd.to_datetime(row_b["fecha"]).date())
                        cod_b = st.text_input("Código de Partido", value=str(row_b["codigo_partido"]))
                        t_b = st.text_input("Tiempo de Ejecución", value=str(row_b["tiempo_ejecucion"]))
                        tar_b = st.number_input("Tarifa ($)", value=float(row_b["tarifa"]), step=0.50)
                        
                        if st.form_submit_button("💾 Guardar Correcciones"):
                            t_b_limpio = (t_b or "").strip()
                            segs_edit = parsear_tiempo_a_segundos(t_b_limpio) if t_b_limpio else None
                            if t_b_limpio and segs_edit is None:
                                st.error("⏱️ Tiempo inválido. Usa el formato HH:MM:SS (ejemplo: 01:42:15).")
                            else:
                                tiempo_edit = formatear_segundos(segs_edit) if segs_edit is not None else ""
                                conn_eb = get_db_connection()
                                if conn_eb:
                                    cur_eb = None
                                    try:
                                        cur_eb = conn_eb.cursor()
                                        cur_eb.execute("UPDATE partidos SET fecha=%s, codigo_partido=%s, tiempo_ejecucion=%s, tarifa=%s WHERE id=%s;", (fe_b, cod_b, tiempo_edit, tar_b, id_edit_b))
                                        conn_eb.commit()
                                    except Exception as e:
                                        conn_eb.rollback()
                                        st.error(f"❌ No se pudo modificar el partido: {e}")
                                    finally:
                                        try:
                                            if cur_eb is not None: cur_eb.close()
                                        except Exception:
                                            pass
                                        cerrar_conexion(conn_eb)

                                    recalcular_tarifas_quincena_basket(user_id, fe_b)
                                    olvidar_recalculos()
                                    st.cache_data.clear()
                                    st.success("✅ Partido modificado y quincena recalculada con éxito.")
                                    st.rerun()

                with tab_eb2:
                    id_del_b = st.selectbox("Seleccione el ID del partido a eliminar:", df_basket["id"].tolist(), key="sel_del_b")
                    confirmo_del_b = st.checkbox("Confirmo que deseo eliminar este partido", key="conf_del_b")
                    if st.button("🚨 Confirmar y Eliminar Partido", use_container_width=True, disabled=not confirmo_del_b):
                        conn_db = get_db_connection()
                        if conn_db:
                            cur_db = None
                            fecha_borrada = hoy_local()
                            try:
                                cur_db = conn_db.cursor()
                                cur_db.execute("SELECT fecha FROM partidos WHERE id = %s;", (id_del_b,))
                                r_f = cur_db.fetchone()
                                fecha_borrada = r_f[0] if r_f else hoy_local()

                                cur_db.execute("DELETE FROM partidos WHERE id = %s;", (id_del_b,))
                                conn_db.commit()
                            except Exception as e:
                                conn_db.rollback()
                                st.error(f"❌ No se pudo eliminar el partido: {e}")
                            finally:
                                try:
                                    if cur_db is not None: cur_db.close()
                                except Exception:
                                    pass
                                cerrar_conexion(conn_db)

                            recalcular_tarifas_quincena_basket(user_id, fecha_borrada)
                            olvidar_recalculos()
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
    # MÓDULO 2: BÉISBOL
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

        f_ini, f_fin = selector_periodo("beisbol_periodo", "Seleccionar Periodo:")

        st.info(f"📅 **Periodo Evaluado Béisbol:** Del **{f_ini.strftime('%d/%m/%Y')}** al **{f_fin.strftime('%d/%m/%Y')}**")

        with st.expander("➕ Registrar Lote de Picheos", expanded=False):
            p1, p2, p3 = st.columns(3)
            with p1: f_pich = st.date_input("Fecha", value=hoy_local(), key="p_fich")
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
                """, conn_pb, params=(f_ini, f_fin))
            else:
                df_picheos = pd.read_sql_query("""
                    SELECT id, fecha, id_control, cantidad 
                    FROM picheos 
                    WHERE usuario_id = %s AND fecha BETWEEN %s AND %s
                    ORDER BY fecha DESC, id DESC;
                """, conn_pb, params=(target_beis_user_id, f_ini, f_fin))
            cerrar_conexion(conn_pb)
        else:
            df_picheos = pd.DataFrame()

        st.markdown(f"### 📋 Listado de Picheos ({f_ini.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')})")
        if not df_picheos.empty:
            total_p = df_picheos["cantidad"].sum()
            precio_u = obtener_tasas_globales()["precio_beisbol"]
            total_dolares = total_p * precio_u

            cp1, cp2, cp3 = st.columns(3)
            cp1.metric("⚾ Total Picheos Quincena", f"{total_p:,}", "📈 Volumen Alto")
            cp2.metric("💵 USD Estimado", f"${total_dolares:,.2f}", f"@ ${precio_u}/u")
            cp3.metric("📅 Lotes Registrados", len(df_picheos), "🟢 Estable")

            st.dataframe(df_picheos, use_container_width=True, hide_index=True)

            with st.expander("🛠️ Modificar, Corregir o Eliminar Lotes de Picheos"):
                tab_ep1, tab_ep2 = st.tabs(["✏️ Modificar / Corregir Lote", "🗑️ Eliminar Lote"])
                
                with tab_ep1:
                    list_ids_p = df_picheos["id"].tolist()
                    id_edit_p = st.selectbox("Seleccione el ID del lote a corregir:", list_ids_p, key="sel_edit_p")
                    
                    row_p = df_picheos[df_picheos["id"] == id_edit_p].iloc[0]
                    with st.form("form_edit_p"):
                        fe_p = st.date_input("Fecha", value=pd.to_datetime(row_p["fecha"]).date())
                        id_c_p = st.text_input("ID Control / Partido", value=str(row_p["id_control"]))
                        cant_p = st.number_input("Cantidad de Picheos", value=int(row_p["cantidad"]), step=1, min_value=1)
                        
                        if st.form_submit_button("💾 Guardar Correcciones"):
                            conn_ep = get_db_connection()
                            if conn_ep:
                                cur_ep = conn_ep.cursor()
                                cur_ep.execute("UPDATE picheos SET fecha=%s, id_control=%s, cantidad=%s WHERE id=%s;", (fe_p, id_c_p, int(cant_p), id_edit_p))
                                conn_ep.commit()
                                cur_ep.close()
                                conn_ep.close()
                                st.cache_data.clear()
                                st.success("✅ Lote de picheos modificado y corregido con éxito.")
                                st.rerun()

                with tab_ep2:
                    id_del_p = st.selectbox("Seleccione el ID del lote a eliminar:", df_picheos["id"].tolist(), key="sel_del_p")
                    confirmo_del_p = st.checkbox("Confirmo que deseo eliminar este lote", key="conf_del_p")
                    if st.button("🚨 Confirmar y Eliminar Lote", use_container_width=True, disabled=not confirmo_del_p):
                        conn_dp = get_db_connection()
                        if conn_dp:
                            cur_dp = None
                            try:
                                cur_dp = conn_dp.cursor()
                                cur_dp.execute("DELETE FROM picheos WHERE id = %s;", (id_del_p,))
                                conn_dp.commit()
                                st.cache_data.clear()
                                st.success("🗑️ Lote de picheos eliminado correctamente.")
                                st.rerun()
                            except Exception as e:
                                conn_dp.rollback()
                                st.error(f"❌ No se pudo eliminar el lote: {e}")
                            finally:
                                try:
                                    if cur_dp is not None: cur_dp.close()
                                except Exception:
                                    pass
                                cerrar_conexion(conn_dp)

            csv_b = df_picheos.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Exportar Reporte Quincenal de Béisbol (CSV)",
                data=csv_b,
                file_name=f"esam_beisbol_quincena_{f_ini}_al_{f_fin}.csv",
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
                cb1, cb2, cb3, cb4, cb5 = st.columns(5)
                with cb1: nt1 = st.number_input("Tramo 1 (1 - 11 partidos)", value=tasas_actuales["tramo_1"], step=0.25)
                with cb2: nt2 = st.number_input("Tramo 2 (12 - 14 partidos)", value=tasas_actuales["tramo_2"], step=0.25)
                with cb3: nt3 = st.number_input("Tramo 3 (15 - 26 partidos)", value=tasas_actuales["tramo_3"], step=0.25)
                with cb4: nt4 = st.number_input("Tramo 4 (27 - 29 partidos)", value=tasas_actuales["tramo_4"], step=0.25)
                with cb5: nt5 = st.number_input("Tramo 5 (30+ partidos)", value=tasas_actuales["tramo_5"], step=0.25)

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
                    actualizar_tasa_global("tasa_tramo_5", nt5)
                    actualizar_tasa_global("tasa_en_vivo_normal", n_norm)
                    actualizar_tasa_global("tasa_en_vivo_nba", n_nba)
                    olvidar_recalculos()
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
    # MÓDULO: SEGURIDAD Y CREDENCIALES (INTELIGENTE)
    # =========================================================
    elif opcion_menu == "🔐 Seguridad y Contraseñas":
        st.title("🔐 Gestión de Seguridad y Contraseñas")

        if es_admin:
            st.caption("👑 MODO ADMINISTRADOR: Puedes cambiar la contraseña de cualquier operador sin saber la clave anterior.")
            df_usrs_pass = obtener_todos_los_usuarios()
            
            if not df_usrs_pass.empty:
                opciones_u_pass = {}
                for _, r_u in df_usrs_pass.iterrows():
                    opciones_u_pass[f"👤 {r_u['nombre']} (@{r_u['username']})"] = r_u['id']
                
                u_pass_sel = st.selectbox("Selecciona el usuario al que deseas cambiarle la contraseña:", list(opciones_u_pass.keys()))
                user_id_target = opciones_u_pass[u_pass_sel]

                with st.form("form_cambiar_pass_admin"):
                    pass_nueva = st.text_input("Escribe la Nueva Contraseña para este Usuario", type="password")
                    pass_conf = st.text_input("Confirmar Nueva Contraseña", type="password")

                    submit_pass = st.form_submit_button("🔒 Forzar Cambio de Contraseña", use_container_width=True)

                    if submit_pass:
                        if not (pass_nueva and pass_conf):
                            st.warning("Por favor complete todos los campos.")
                        elif pass_nueva != pass_conf:
                            st.error("Las nuevas contraseñas no coinciden.")
                        elif len(pass_nueva) < 6:
                            st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                        else:
                            exito_c, msg_c = cambiar_password_usuario(user_id_target, pass_nueva)
                            if exito_c:
                                st.success(f"✅ Contraseña reescrita con éxito para {u_pass_sel}.")
                            else:
                                st.error(msg_c)
        else:
            st.caption(f"Actualiza la contraseña de tu cuenta individual — {user_name}")

            with st.form("form_cambiar_pass_user"):
                pass_vieja = st.text_input("Contraseña Actual", type="password")
                pass_nueva = st.text_input("Nueva Contraseña", type="password")
                pass_conf = st.text_input("Confirmar Nueva Contraseña", type="password")

                submit_pass = st.form_submit_button("🔒 Actualizar Mi Contraseña", use_container_width=True)

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
