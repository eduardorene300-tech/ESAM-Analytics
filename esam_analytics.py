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

# Estilos CSS profesionales avanzados (Diseño visual corporativo y limpio)
st.markdown("""
    <style>
    .main-header {
        font-size: 2.3rem;
        color: #1E3A8A;
        font-weight: 800;
        margin-bottom: 0px;
        letter-spacing: -0.5px;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 25px;
    }
    .metric-card {
        background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
        border: 1px solid #e2e8f0;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        margin-bottom: 15px;
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
if 'password_sistema' not in st.session_state:
    st.session_state.password_sistema = "esam2026"

if 'juegos_registrados' not in st.session_state:
    # Base de datos inicial de ejemplo con especificaciones detalladas por deporte
    st.session_state.juegos_registrados = pd.DataFrame([
        {
            "ID Juego": "GAME-001",
            "Fecha": date(2026, 10, 15),
            "Deporte": "Béisbol",
            "Equipo Local": "Leones del Caracas",
            "Equipo Visitante": "Navegantes del Magallanes",
            "Picheos/Eventos": 285,
            "Detalle Técnico": "Pitch logging completo, conteo de lanzamientos y strikes",
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
            "Detalle Técnico": "Synergy tracking de posesiones, tiros y jugadas",
            "Monto USD": round(310 * 0.024, 3),
            "Estado": "Completado"
        }
    ])

# ==========================================
# FUNCIONES AUXILIARES Y DE CÁLCULO
# ==========================================
def calcular_pago(cantidad_eventos, tarifa=None):
    if tarifa is None:
        tarifa = st.session_state.tarifa_global
    return round(cantidad_eventos * tarifa, 3)

def exportar_datos_sistema(df):
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
        "📊 Panel General y Ganancias", 
        "📝 Registrar Juego", 
        "⚾ Béisbol: Análisis y Registros", 
        "🏀 Básquetbol: Análisis y Registros", 
        "📈 Métricas y Filtros", 
        "🔍 Búsqueda Avanzada", 
        "🔐 Seguridad y Credenciales",
        "⚙️ Configuración"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info(f"Tarifa activa: **${st.session_state.tarifa_global} USD** / evento")

# ==========================================
# MÓDULO 1: PANEL GENERAL Y GANANCIAS
# ==========================================
if opcion_menu == "📊 Panel General y Ganancias":
    st.markdown('<p class="main-header">Panel de Control y Ganancias</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Marcador global consolidado de rendimiento financiero y jornadas analizadas en ambos deportes</p>', unsafe_allow_html=True)
    
    df = st.session_state.juegos_registrados
    
    # Tarjetas de marcadores superiores profesionales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Juegos", len(df))
    with col2:
        total_picheos = int(df["Picheos/Eventos"].sum()) if not df.empty else 0
        st.metric("Total Eventos / Picheos", f"{total_picheos:,}")
    with col3:
        total_ganancias = float(df["Monto USD"].sum()) if not df.empty else 0.0
        st.metric("Ganancias Totales Acumuladas", f"${total_ganancias:,.2f} USD")
    with col4:
        promedio_picheos = int(df["Picheos/Eventos"].mean()) if not df.empty else 0
        st.metric("Promedio p/ Juego", f"{promedio_picheos}")

    st.markdown("---")
    st.markdown("### 📋 Historial Completo de Jornadas Registradas")
    if not df.empty:
        st.dataframe(df, use_container_width=True)
        
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
        st.warning("No hay juegos registrados en la base de datos actualmente.")

# ==========================================
# MÓDULO 2: REGISTRAR JUEGO
# ==========================================
elif opcion_menu == "📝 Registrar Juego":
    st.markdown('<p class="main-header">Registro de Nuevo Juego</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ingresa los datos técnicos, conteo y especificaciones del deporte analizado</p>', unsafe_allow_html=True)

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

        detalle_tecnico = st.text_area("Especificaciones / Notas Técnicas del Partido", placeholder="Ej: Cobertura completa de lanzamientos, verificación de jugadas con Synergy...")

        monto_calculado = calcular_pago(picheos_eventos)
        st.info(f"💵 **Monto estimado a cobrar:** ${monto_calculado:.3f} USD (Calculado a${st.session_state.tarifa_global} por unidad)")

        btn_guardar = st.form_submit_button("💾 Guardar y Registrar Juego")

        if btn_guardar:
            if not id_juego.strip() or not equipo_local.strip() or not equipo_visitante.strip():
                st.error("Por favor completa todos los campos obligatorios.")
            else:
                nuevo_juego = {
                    "ID Juego": id_juego.upper(),
                    "Fecha": fecha_juego,
                    "Deporte": deporte,
                    "Equipo Local": equipo_local,
                    "Equipo Visitante": equipo_visitante,
                    "Picheos/Eventos": int(picheos_eventos),
                    "Detalle Técnico": detalle_tecnico if detalle_tecnico else "Sin especificaciones adicionales",
                    "Monto USD": monto_calculado,
                    "Estado": "Completado"
                }
                st.session_state.juegos_registrados = pd.concat(
                    [st.session_state.juegos_registrados, pd.DataFrame([nuevo_juego])],
                    ignore_index=True
                )
                st.success(f"✅ ¡Juego {id_juego.upper()} registrado exitosamente! Monto: ${monto_calculado:.2f} USD.")

# ==========================================
# MÓDULO 3: BÉISBOL (ESPECIFICACIONES)
# ==========================================
elif opcion_menu == "⚾ Béisbol: Análisis y Registros":
    st.markdown('<p class="main-header">Módulo Especializado en Béisbol</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Gestión exclusiva, estadísticas y registros específicos de partidos de béisbol</p>', unsafe_allow_html=True)

    df = st.session_state.juegos_registrados
    df_beisbol = df[df["Deporte"] == "Béisbol"] if not df.empty else pd.DataFrame()

    if not df_beisbol.empty:
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.metric("Total Juegos de Béisbol", len(df_beisbol))
        with col_b2:
            gan_beisbol = float(df_beisbol["Monto USD"].sum())
            st.metric("Ingresos Generados (Béisbol)", f"${gan_beisbol:,.2f} USD")

        st.markdown("### 📋 Listado de Partidos de Béisbol Analizados")
        st.dataframe(df_beisbol, use_container_width=True)
    else:
        st.info("No hay registros de béisbol almacenados actualmente en el sistema.")

# ==========================================
# MÓDULO 4: BÁSQUETBOL (ESPECIFICACIONES)
# ==========================================
elif opcion_menu == "🏀 Básquetbol: Análisis y Registros":
    st.markdown('<p class="main-header">Módulo Especializado en Básquetbol</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Gestión exclusiva, seguimiento de posesiones y registros de básquetbol</p>', unsafe_allow_html=True)

    df = st.session_state.juegos_registrados
    df_basquet = df[df["Deporte"] == "Básquetbol"] if not df.empty else pd.DataFrame()

    if not df_basquet.empty:
        col_bk1, col_bk2 = st.columns(2)
        with col_bk1:
            st.metric("Total Juegos de Básquetbol", len(df_basquet))
        with col_bk2:
            gan_basquet = float(df_basquet["Monto USD"].sum())
            st.metric("Ingresos Generados (Básquetbol)", f"${gan_basquet:,.2f} USD")

        st.markdown("### 📋 Listado de Partidos de Básquetbol Analizados")
        st.dataframe(df_basquet, use_container_width=True)
    else:
        st.info("No hay registros de básquetbol almacenados actualmente en el sistema.")

# ==========================================
# MÓDULO 5: MÉTRICAS Y FILTROS
# ==========================================
elif opcion_menu == "📈 Métricas y Filtros":
    st.markdown('<p class="main-header">Métricas y Ganancias por Periodo</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Filtra tus registros mediante rangos de fechas específicos</p>', unsafe_allow_html=True)

    df = st.session_state.juegos_registrados

    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        b_inicio = st.date_input("Fecha Inicial", value=date(2026, 1, 1))
    with col_filtro2:
        b_ffin = st.date_input("Fecha Final", value=date(2035, 12, 31))

    if not df.empty:
        df_temp = df.copy()
        df_temp['Fecha_dt'] = pd.to_datetime(df_temp['Fecha'])
        mask = (df_temp['Fecha_dt'] >= pd.to_datetime(b_inicio)) & (df_temp['Fecha_dt'] <= pd.to_datetime(b_ffin))
        df_filtrado = df_temp.loc[mask]

        st.markdown(f"#### Resultados financieros entre {b_inicio} y {b_ffin}")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Juegos Filtrados", len(df_filtrado))
        with col_m2:
            pich_filt = int(df_filtrado["Picheos/Eventos"].sum()) if not df_filtrado.empty else 0
            st.metric("Eventos del Periodo", f"{pich_filt:,}")
        with col_m3:
            mont_filt = float(df_filtrado["Monto USD"].sum()) if not df_filtrado.empty else 0.0
            st.metric("Ingresos del Periodo", f"${mont_filt:,.2f} USD")

        st.dataframe(df_filtrado.drop(columns=['Fecha_dt'], errors='ignore'), use_container_width=True)

        if not df_filtrado.empty:
            st.markdown("#### 📊 Gráfico de Rendimiento Financiero")
            st.bar_chart(data=df_filtrado, x="ID Juego", y="Monto USD")
    else:
        st.info("No hay registros disponibles para procesar métricas.")

# ==========================================
# MÓDULO 6: BÚSQUEDA AVANZADA
# ==========================================
elif opcion_menu == "🔍 Búsqueda Avanzada":
    st.markdown('<p class="main-header">Búsqueda Rápida de Registros</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Localiza juegos por ID, equipo o deporte de forma instantánea</p>', unsafe_allow_html=True)

    df = st.session_state.juegos_registrados

    if not df.empty:
        criterio = st.text_input("🔍 Término de búsqueda:", placeholder="Ej: Leones, Básquetbol, GAME-001")
        
        if criterio:
            mask = df.astype(str).apply(lambda col: col.str.contains(criterio, case=False, na=False)).any(axis=1)
            df_resultados = df[mask]
            st.markdown(f"**Se encontraron {len(df_resultados)} coincidencia(s):**")
            st.dataframe(df_resultados, use_container_width=True)
        else:
            st.info("Introduce un término en el campo de arriba para filtrar la base de datos.")
    else:
        st.warning("No hay registros disponibles para realizar búsquedas.")

# ==========================================
# MÓDULO 7: SEGURIDAD Y CREDENCIALES
# ==========================================
elif opcion_menu == "🔐 Seguridad y Credenciales":
    st.markdown('<p class="main-header">Gestión de Seguridad y Claves</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Modifica o recupera la contraseña de acceso del sistema</p>', unsafe_allow_html=True)

    with st.form("form_seguridad"):
        st.markdown("#### Cambio de Clave de Acceso")
        clave_actual = st.text_input("Contraseña Actual", type="password", placeholder="Introduce tu clave actual")
        nueva_clave = st.text_input("Nueva Contraseña", type="password", placeholder="Introduce la nueva clave")
        confirmar_clave = st.text_input("Confirma la Nueva Contraseña", type="password", placeholder="Repite la nueva clave")
        
        btn_cambiar = st.form_submit_button("🔒 Actualizar Contraseña")
        
        if btn_cambiar:
            if clave_actual != st.session_state.password_sistema:
                st.error("❌ La contraseña actual no es correcta.")
            elif not nueva_clave or nueva_clave != confirmar_clave:
                st.error("❌ Las nuevas contraseñas no coinciden o están vacías.")
            else:
                st.session_state.password_sistema = nueva_clave
                st.success("✅ ¡Contraseña actualizada exitosamente con altos estándares de seguridad!")

    st.markdown("---")
    with st.expander("❓ ¿Olvidaste tu contraseña o necesitas recuperación?"):
        st.markdown(f"""
        Si necesitas recuperar tu clave de acceso en este entorno local, la contraseña maestra actual configurada es:  
        `{st.session_state.password_sistema}`  
        *Guarda esta clave en un lugar seguro.*
        """)

# ==========================================
# MÓDULO 8: CONFIGURACIÓN
# ==========================================
elif opcion_menu == "⚙️ Configuración":
    st.markdown('<p class="main-header">Configuración del Sistema</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Personaliza parámetros globales de operador y tarifas</p>', unsafe_allow_html=True)

    with st.form("form_config"):
        nuevo_usuario = st.text_input("Nombre del Analista", value=st.session_state.user)
        nueva_tarifa = st.number_input("Tarifa estándar por picheo/evento (USD)", value=float(st.session_state.tarifa_global), format="%.3f")
        
        btn_guardar_config = st.form_submit_button("💾 Guardar Cambios")
        if btn_guardar_config:
            st.session_state.user = nuevo_usuario
            st.session_state.tarifa_global = nueva_tarifa
            st.success("✅ Configuración general guardada con éxito.")

    st.markdown("---")
    st.markdown("### ⚠️ Zona de Mantenimiento")
    if st.button("🗑️ Vaciar y Eliminar Todos los Registros"):
        st.session_state.juegos_registrados = pd.DataFrame(columns=[
            "ID Juego", "Fecha", "Deporte", "Equipo Local", "Equipo Visitante", "Picheos/Eventos", "Detalle Técnico", "Monto USD", "Estado"
        ])
        st.warning("Se han eliminado todos los registros almacenados en la base de datos temporal.")
