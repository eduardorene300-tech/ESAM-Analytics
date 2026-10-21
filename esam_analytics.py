import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import io

# ==========================================
# CONFIGURACIÓN DE LA PÁGINA Y ESTILOS UI/UX
# ==========================================
st.set_page_config(
    page_title="ESAM Analytics - Plataforma Deportiva",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para mejorar la interfaz
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# GESTIÓN DE ESTADO (SESSION STATE)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = True
if 'user' not in st.session_state:
    st.session_state.user = "Analista Deportivo"
if 'juegos_registrados' not in st.session_state:
    # Datos de prueba iniciales
    st.session_state.juegos_registrados = pd.DataFrame([
        {
            "ID Juego": "GAME-001",
            "Fecha": date(2026, 10, 15),
            "Deporte": "Béisbol",
            "Equipo Local": "Leones",
            "Equipo Visitante": "Navegantes",
            "Picheos/Eventos": 285,
            "Monto USD": 285 * 0.024,
            "Estado": "Completado"
        },
        {
            "ID Juego": "GAME-002",
            "Fecha": date(2026, 10, 18),
            "Deporte": "Básquetbol",
            "Equipo Local": "Lakers",
            "Equipo Visitante": "Celtics",
            "Picheos/Eventos": 310,
            "Monto USD": 310 * 0.024,
            "Estado": "Completado"
        }
    ])

# ==========================================
# FUNCIONES AUXILIARES Y DE CÁLCULO
# ==========================================
def calcular_pago(cantidad_eventos, tarifa=0.024):
    """Calcula el pago total en USD según el número de picheos/eventos analizados."""
    return round(cantidad_eventos * tarifa, 3)

def exportar_a_excel(df):
    """Genera un archivo Excel en memoria para descarga."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Analitica')
    return output.getvalue()

# ==========================================
# BARRA LATERAL (NAVEGACIÓN)
# ==========================================
st.sidebar.image("https://img.icons8.com/color/96/baseball.png", width=70)
st.sidebar.title("ESAM Analytics")
st.sidebar.markdown(f"**Usuario:** {st.session_state.user}")
st.sidebar.markdown("---")

opcion_menu = st.sidebar.radio(
    "Menú Principal",
    ["📊 Panel General", "📝 Registrar Juego", "📈 Métricas y Ganancias", "⚙️ Configuración"]
)

st.sidebar.markdown("---")
st.sidebar.info("Tarifa estándar: **$0.024 USD** por picheo/evento")

# ==========================================
# MÓDULO 1: PANEL GENERAL
# ==========================================
if opcion_menu == "📊 Panel General":
    st.markdown('<p class="main-header">Panel de Control de Analítica</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Resumen general de juegos analizados y rendimiento acumulado</p>', unsafe_allow_html=True)
    
    df = st.session_state.juegos_registrados
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Juegos", len(df))
    with col2:
        total_picheos = df["Picheos/Eventos"].sum() if not df.empty else 0
        st.metric("Total Picheos/Eventos", f"{total_picheos:,}")
    with col3:
        total_ganancias = df["Monto USD"].sum() if not df.empty else 0.0
        st.metric("Ganancias Total ($)", f"${total_ganancias:.2f}")
    with col4:
        promedio_picheos = df["Picheos/Eventos"].mean() if not df.empty else 0
        st.metric("Promedio p/ Juego", f"{promedio_picheos:.0f}")

    st.markdown("### 📋 Registro Reciente de Juegos")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
        excel_data = exportar_a_excel(df)
        st.download_button(
            label="📥 Exportar Reporte a Excel",
            data=excel_data,
            file_name=f"ESAM_Analytics_Reporte_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("No hay juegos registrados en el sistema.")

# ==========================================
# MÓDULO 2: REGISTRAR JUEGO
# ==========================================
elif opcion_menu == "📝 Registrar Juego":
    st.markdown('<p class="main-header">Registro de Nuevo Juego</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ingresa la información técnica de la jornada analizada</p>', unsafe_allow_html=True)

    with st.form("form_registro_juego", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            fecha_juego = st.date_input("Fecha del Juego", value=date.today())
            deporte = st.selectbox("Deporte", ["Béisbol", "Básquetbol"])
            equipo_local = st.text_input("Equipo Local", placeholder="Ej: Leones")
        with col_f2:
            id_juego = st.text_input("Código / ID del Juego", placeholder="Ej: GAME-003")
            picheos_eventos = st.number_input("Cantidad de Picheos / Eventos", min_value=1, value=250, step=1)
            equipo_visitante = st.text_input("Equipo Visitante", placeholder="Ej: Navegantes")

        monto_calculado = calcular_pago(picheos_eventos)
        st.info(f"💵 **Monto estimado a cobrar:** ${monto_calculado:.3f} USD (Calculado a $0.024/unidad)")

        btn_guardar = st.form_submit_button("💾 Guardar Registro")

        if btn_guardar:
            if not id_juego or not equipo_local or not equipo_visitante:
                st.error("Por favor completa todos los campos requeridos.")
            else:
                nuevo_juego = {
                    "ID Juego": id_juego,
                    "Fecha": fecha_juego,
                    "Deporte": deporte,
                    "Equipo Local": equipo_local,
                    "Equipo Visitante": equipo_visitante,
                    "Picheos/Eventos": picheos_eventos,
                    "Monto USD": monto_calculado,
                    "Estado": "Completado"
                }
                st.session_state.juegos_registrados = pd.concat(
                    [st.session_state.juegos_registrados, pd.DataFrame([nuevo_juego])],
                    ignore_index=True
                )
                st.success(f"✅ Juego {id_juego} registrado exitosamente con un monto de ${monto_calculado:.2f} USD.")

# ==========================================
# MÓDULO 3: MÉTRICAS Y GANANCIAS
# ==========================================
elif opcion_menu == "📈 Métricas y Ganancias":
    st.markdown('<p class="main-header">Métricas Financieras y Rendimiento</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Filtra tus registros para analizar ingresos y proyección</p>', unsafe_allow_html=True)

    df = st.session_state.juegos_registrados

    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        b_inicio = st.date_input("Fecha Inicial", value=date(2026, 1, 1))
    with col_filtro2:
        # Línea 712 ajustada y corregida con sintaxis válida
        b_ffin = st.date_input("Fecha Final", value=date(2035, 12, 31))

    if not df.empty:
        # Convertir campo fecha a datetime para filtrado correcto
        df['Fecha_dt'] = pd.to_datetime(df['Fecha'])
        mask = (df['Fecha_dt'] >= pd.to_datetime(b_inicio)) & (df['Fecha_dt'] <= pd.to_datetime(b_ffin))
        df_filtrado = df.loc[mask]

        st.markdown(f"#### Resultados entre {b_inicio} y {b_ffin}")
        st.dataframe(df_filtrado.drop(columns=['Fecha_dt'], errors='ignore'), use_container_width=True)

        if not df_filtrado.empty:
            st.bar_chart(data=df_filtrado, x="ID Juego", y="Monto USD")
    else:
        st.info("No hay datos disponibles para generar gráficas.")

# ==========================================
# MÓDULO 4: CONFIGURACIÓN
# ==========================================
elif opcion_menu == "⚙️ Configuración":
    st.markdown('<p class="main-header">Configuración del Sistema</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Parámetros globales y mantenimiento de datos</p>', unsafe_allow_html=True)

    st.text_input("Nombre del Analista", value=st.session_state.user)
    st.number_input("Tarifa por picheo/evento (USD)", value=0.024, format="%.3f", disabled=True)

    if st.button("🗑️ Limpiar Todos los Datos Registrados"):
        st.session_state.juegos_registrados = pd.DataFrame(columns=[
            "ID Juego", "Fecha", "Deporte", "Equipo Local", "Equipo Visitante", "Picheos/Eventos", "Monto USD", "Estado"
        ])
        st.warning("Se han eliminado todos los registros almacenados temporalmente.")
