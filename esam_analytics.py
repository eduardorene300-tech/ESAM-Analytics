import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import io

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA Y ESTILOS UI/UX
# ==========================================
st.set_page_config(
    page_title="ESAM Analytics - Plataforma Deportiva Profesional",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados avanzados para la interfaz visual
st.markdown("""
    <style>
    .main-header {
        font-size: 2.2rem;
        color: #1E3A8A;
        font-weight: 700;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 20px;
    }
    .card {
        background-color: #FFFFFF;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 15px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #1E40AF;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6B7280;
    }
    .stAlert {
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# GESTIÓN DE ESTADO GLOBAL (SESSION STATE)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = True
if 'user' not in st.session_state:
    st.session_state.user = "Eduardo Serrano"
if 'tarifa_global' not in st.session_state:
    st.session_state.tarifa_global = 0.024

if 'juegos_registrados' not in st.session_state:
    # Base de datos local en memoria con registros iniciales de prueba
    st.session_state.juegos_registrados = pd.DataFrame([
        {
            "ID Juego": "GAME-001",
            "Fecha": date(2026, 10, 15),
            "Deporte": "Béisbol",
            "Equipo Local": "Leones del Caracas",
            "Equipo Visitante": "Navegantes del Magallanes",
            "Picheos/Eventos": 285,
            "Monto USD": round(285 * 0.024, 3),
            "Estado": "Completado"
        },
        {
            "ID Juego": "GAME-002",
            "Fecha": date(2026, 10, 18),
            "Deporte": "Básquetbol",
            "Equipo Local": "Lakers",
            "Equipo Visitante": "Celtics",
            "Picheos/Eventos": 310,
            "Monto USD": round(310 * 0.024, 3),
            "Estado": "Completado"
        }
    ])

# ==========================================
# FUNCIONES AUXILIARES Y DE CÁLCULO
# ==========================================
def calcular_pago(cantidad_eventos, tarifa=None):
    """Calcula el pago total en USD según el número de picheos/eventos analizados y la tarifa activa."""
    if tarifa is None:
        tarifa = st.session_state.tarifa_global
    return round(cantidad_eventos * tarifa, 3)

def exportar_datos_sistema(df):
    """Genera un archivo Excel en memoria con manejo de respaldo automático a CSV."""
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Analitica_ESAM')
        return output.getvalue(), "excel"
    except Exception:
        output_csv = df.to_csv(index=False).encode('utf-8')
        return output_csv, "csv"

# ==========================================
# BARRA LATERAL (NAVEGACIÓN PROFESIONAL)
# ==========================================
st.sidebar.image("https://img.icons8.com/color/96/baseball.png", width=70)
st.sidebar.title("ESAM Analytics")
st.sidebar.markdown(f"**Analista:** {st.session_state.user}")
st.sidebar.markdown("---")

opcion_menu = st.sidebar.radio(
    "Menú Principal",
    [
        "📊 Panel General", 
        "📝 Registrar Juego", 
        "📈 Métricas y Ganancias", 
        "🔍 Consultas y Búsqueda", 
        "⚙️ Configuración"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info(f"Tarifa activa: **${st.session_state.tarifa_global} USD** por evento")

# ==========================================
# MÓDULO 1: PANEL GENERAL
# ==========================================
if opcion_menu == "📊 Panel General":
    st.markdown('<p class="main-header">Panel de Control de Analítica</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Resumen integral del rendimiento de análisis deportivo y métricas financieras</p>', unsafe_allow_html=True)
    
    df = st.session_state.juegos_registrados
    
    # Métricas principales superiores
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Juegos Analizados", len(df))
    with col2:
        total_picheos = int(df["Picheos/Eventos"].sum()) if not df.empty else 0
        st.metric("Total Picheos / Eventos", f"{total_picheos:,}")
    with col3:
        total_ganancias = float(df["Monto USD"].sum()) if not df.empty else 0.0
        st.metric("Ganancias Acumuladas", f"${total_ganancias:,.2f} USD")
    with col4:
        promedio_picheos = int(df["Picheos/Eventos"].mean()) if not df.empty else 0
        st.metric("Promedio x/ Juego", f"{promedio_picheos}")

    st.markdown("### 📋 Historial y Registro Reciente de Jornadas")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        # Botón de exportación inteligente
        datos_archivo, tipo_formato = exportar_datos_sistema(df)
        if tipo_formato == "excel":
            st.download_button(
                label="📥 Exportar Reporte General a Excel (.xlsx)",
                data=datos_archivo,
                file_name=f"ESAM_Analytics_Reporte_{date.today()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.download_button(
                label="📥 Exportar Reporte General a CSV (.csv)",
                data=datos_archivo,
                file_name=f"ESAM_Analytics_Reporte_{date.today()}.csv",
                mime="text/csv"
            )
    else:
        st.warning("No hay juegos registrados en el sistema actualmente.")

# ==========================================
# MÓDULO 2: REGISTRAR JUEGO
# ==========================================
elif opcion_menu == "📝 Registrar Juego":
    st.markdown('<p class="main-header">Registro de Nuevo Juego</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ingresa la información técnica y de conteo de la jornada analizada</p>', unsafe_allow_html=True)

    with st.form("form_registro_juego", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fecha_juego = st.date_input("Fecha del Juego", value=date.today())
            deporte = st.selectbox("Deporte Analizado", ["Béisbol", "Básquetbol"])
            equipo_local = st.text_input("Equipo Local", placeholder="Ej: Leones del Caracas")
        with col_f2:
            id_juego = st.text_input("Código / ID del Juego", placeholder="Ej: GAME-003")
            picheos_eventos = st.number_input("Cantidad de Picheos / Eventos", min_value=1, value=250, step=1)
            equipo_visitante = st.text_input("Equipo Visitante", placeholder="Ej: Navegantes del Magallanes")

        monto_calculado = calcular_pago(picheos_eventos)
        st.info(f"💵 **Monto estimado a cobrar:** ${monto_calculado:.3f} USD (Calculado a ${st.session_state.tarifa_global} por unidad)")

        btn_guardar = st.form_submit_button("💾 Guardar y Registrar Juego")

        if btn_guardar:
            if not id_juego.strip() or not equipo_local.strip() or not equipo_visitante.strip():
                st.error("Por favor completa todos los campos de texto obligatorios.")
            else:
                nuevo_juego = {
                    "ID Juego": id_juego.upper(),
                    "Fecha": fecha_juego,
                    "Deporte": deporte,
                    "Equipo Local": equipo_local,
                    "Equipo Visitante": equipo_visitante,
                    "Picheos/Eventos": int(picheos_eventos),
                    "Monto USD": monto_calculado,
                    "Estado": "Completado"
                }
                st.session_state.juegos_registrados = pd.concat(
                    [st.session_state.juegos_registrados, pd.DataFrame([nuevo_juego])],
                    ignore_index=True
                )
                st.success(f"✅ ¡Juego {id_juego.upper()} registrado con éxito! Monto acumulado: ${monto_calculado:.2f} USD.")

# ==========================================
# MÓDULO 3: MÉTRICAS Y GANANCIAS
# ==========================================
elif opcion_menu == "📈 Métricas y Ganancias":
    st.markdown('<p class="main-header">Métricas Financieras y Rendimiento</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Filtra por rangos de fecha y visualiza tus ingresos por periodo</p>', unsafe_allow_html=True)

    df = st.session_state.juegos_registrados

    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        b_inicio = st.date_input("Fecha Inicial del Filtro", value=date(2026, 1, 1))
    with col_filtro2:
        b_ffin = st.date_input("Fecha Final del Filtro", value=date(2035, 12, 31))

    if not df.empty:
        df_temp = df.copy()
        df_temp['Fecha_dt'] = pd.to_datetime(df_temp['Fecha'])
        mask = (df_temp['Fecha_dt'] >= pd.to_datetime(b_inicio)) & (df_temp['Fecha_dt'] <= pd.to_datetime(b_ffin))
        df_filtrado = df_temp.loc[mask]

        st.markdown(f"#### Resultados financieros entre {b_inicio} y {b_ffin}")
        
        # Sub-métricas del filtro seleccionado
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Juegos en el Periodo", len(df_filtrado))
        with col_m2:
            pich_filt = int(df_filtrado["Picheos/Eventos"].sum()) if not df_filtrado.empty else 0
            st.metric("Eventos Totales", f"{pich_filt:,}")
        with col_m3:
            mont_filt = float(df_filtrado["Monto USD"].sum()) if not df_filtrado.empty else 0.0
            st.metric("Ingresos del Periodo", f"${mont_filt:,.2f} USD")

        st.dataframe(df_filtrado.drop(columns=['Fecha_dt'], errors='ignore'), use_container_width=True)

        if not df_filtrado.empty:
            st.markdown("#### 📊 Gráfico de Ingresos por Juego")
            st.bar_chart(data=df_filtrado, x="ID Juego", y="Monto USD")
    else:
        st.info("No hay registros disponibles para procesar métricas.")

# ==========================================
# MÓDULO 4: CONSULTAS Y BÚSQUEDA
# ==========================================
elif opcion_menu == "🔍 Consultas y Búsqueda":
    st.markdown('<p class="main-header">Búsqueda Avanzada de Registros</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Encuentra juegos específicos por código, deporte o equipo</p>', unsafe_allow_html=True)

    df = st.session_state.juegos_registrados

    if not df.empty:
        criterio = st.text_input("🔍 Buscar por ID de Juego, Equipo o Deporte:", placeholder="Ej: Leones, Béisbol, GAME-001")
        
        if criterio:
            mask = df.astype(str).apply(lambda col: col.str.contains(criterio, case=False, na=False)).any(axis=1)
            df_resultados = df[mask]
            st.markdown(f"**Se encontraron {len(df_resultados)} coincidencia(s) para '{criterio}':**")
            st.dataframe(df_resultados, use_container_width=True)
        else:
            st.info("Escribe arriba cualquier término para realizar una búsqueda instantánea en la base de datos.")
    else:
        st.warning("No hay registros en la base de datos para buscar.")

# ==========================================
# MÓDULO 5: CONFIGURACIÓN
# ==========================================
elif opcion_menu == "⚙️ Configuración":
    st.markdown('<p class="main-header">Configuración del Sistema</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Personaliza tus datos de usuario, tarifas y mantenimiento de datos</p>', unsafe_allow_html=True)

    with st.form("form_config"):
        nuevo_usuario = st.text_input("Nombre del Analista", value=st.session_state.user)
        nueva_tarifa = st.number_input("Tarifa estándar por picheo/evento (USD)", value=float(st.session_state.tarifa_global), format="%.3f")
        
        btn_guardar_config = st.form_submit_button("💾 Guardar Cambios de Configuración")
        if btn_guardar_config:
            st.session_state.user = nuevo_usuario
            st.session_state.tarifa_global = nueva_tarifa
            st.success("✅ Configuración actualizada correctamente.")

    st.markdown("---")
    st.markdown("### ⚠️ Zona de Mantenimiento")
    if st.button("🗑️ Eliminar Todos los Registros de la Base de Datos"):
        st.session_state.juegos_registrados = pd.DataFrame(columns=[
            "ID Juego", "Fecha", "Deporte", "Equipo Local", "Equipo Visitante", "Picheos/Eventos", "Monto USD", "Estado"
        ])
        st.warning("Se han borrado todos los registros de la memoria de la aplicación.")
