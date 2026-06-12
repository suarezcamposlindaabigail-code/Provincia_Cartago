"""
app.py
================================================================
Florida Bebidas · Distribucion Nacional · CVRP Provincia de Cartago
Curso II-1122 · Clase 12 · Flujos de Redes · UCR Sede Alajuela

App de Streamlit que resuelve el problema de ruteo de vehiculos
con capacidad (CVRP) para los 8 cantones de Cartago, minimizando
los kilometros totales recorridos por la flota.

Restricciones del modelo:
  - Camion entra - Camion sale = 0           (conservacion de flujo)
  - Entradas - Salidas = Demanda del canton  (balance de carga)
  - Big-M para acotar/eliminar subtours
  - Capacidad maxima por camion = 24 pallets
================================================================
"""

import folium
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_folium import st_folium

from solver_cvrp import build_dist_dict, solve_cvrp

# ----------------------------------------------------------------
# CONFIGURACION GENERAL DE LA PAGINA
# ----------------------------------------------------------------
st.set_page_config(
    page_title="Florida Bebidas · CVRP Cartago",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------
# ESTILOS (CSS personalizado)
# ----------------------------------------------------------------
PRIMARY = "#1F3864"      # azul institucional
ACCENT = "#C99A1F"       # dorado / mostaza
GREEN = "#2E7D32"
RED = "#C0392B"
LIGHT_BG = "#EAF1FB"

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: #F7F9FC;
    }}
    .main-header {{
        background: linear-gradient(135deg, {PRIMARY} 0%, #2A4A7F 100%);
        padding: 1.6rem 2rem;
        border-radius: 14px;
        color: white;
        margin-bottom: 1.2rem;
        box-shadow: 0 4px 14px rgba(31,56,100,0.25);
    }}
    .main-header h1 {{
        margin: 0;
        font-size: 2.0rem;
        font-weight: 800;
        letter-spacing: 0.5px;
    }}
    .main-header p {{
        margin: 0.3rem 0 0 0;
        font-size: 1.0rem;
        opacity: 0.9;
    }}
    .badge {{
        display: inline-block;
        background-color: {ACCENT};
        color: {PRIMARY};
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 1.5px;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
    }}
    .section-card {{
        background-color: white;
        border-radius: 14px;
        padding: 1.4rem 1.6rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        border: 1px solid #E3E9F2;
        margin-bottom: 1.2rem;
    }}
    .kpi-box {{
        background-color: {LIGHT_BG};
        border-radius: 12px;
        padding: 1rem 1.2rem;
        text-align: center;
        border: 1px solid #D6E2F5;
    }}
    .kpi-value {{
        font-size: 1.8rem;
        font-weight: 800;
        color: {PRIMARY};
    }}
    .kpi-label {{
        font-size: 0.85rem;
        color: #5A6B85;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }}
    .footer-note {{
        text-align: center;
        color: #8A97AC;
        font-size: 0.8rem;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #E3E9F2;
    }}
    .route-pill {{
        display: inline-block;
        background-color: {LIGHT_BG};
        border: 1px solid #D6E2F5;
        border-radius: 999px;
        padding: 0.15rem 0.7rem;
        margin: 0.1rem;
        font-size: 0.85rem;
        color: {PRIMARY};
        font-weight: 600;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------
# HEADER
# ----------------------------------------------------------------
st.markdown(
    """
    <div class="main-header">
        <span class="badge">CVRP · Bloque 03 · Trabajo Grupal</span>
        <h1>🚚 Distribución Nacional Florida Bebidas — Provincia de Cartago</h1>
        <p>Ruteo óptimo de camiones (24 pallets) desde el CD de Cartago hacia los 8 cantones,
        minimizando los kilómetros totales recorridos por la flota.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------
# DATOS BASE (Caso original — Cartago)
# ----------------------------------------------------------------
CANTONES = {
    1: "Cartago",
    2: "Paraíso",
    3: "La Unión",
    4: "Jiménez",
    5: "Turrialba",
    6: "Alvarado",
    7: "Oreamuno",
    8: "El Guarco",
}

# Demanda por producto (caso base, slide "Provincia: Cartago")
DEMANDA_PRODUCTOS_BASE = pd.DataFrame(
    {
        "nodo": [1, 2, 3, 4, 5, 6, 7, 8],
        "Cantón": [CANTONES[i] for i in range(1, 9)],
        "Imperial": [62, 24, 37, 7, 31, 6, 18, 17],
        "Pilsen": [31, 12, 19, 4, 15, 3, 9, 9],
        "Tropical": [31, 12, 19, 4, 15, 3, 9, 9],
    }
)
DEMANDA_PRODUCTOS_BASE["Demanda total"] = (
    DEMANDA_PRODUCTOS_BASE["Imperial"]
    + DEMANDA_PRODUCTOS_BASE["Pilsen"]
    + DEMANDA_PRODUCTOS_BASE["Tropical"]
)

# Matriz de distancias (km) - nodo 0 = CD Cartago
DIST_MATRIX_BASE = pd.DataFrame(
    [
        [0, 0, 9, 10, 34, 34, 20, 6, 6],
        [0, 0, 9, 10, 34, 34, 20, 6, 6],
        [9, 9, 0, 19, 26, 28, 13, 7, 12],
        [10, 10, 19, 0, 45, 43, 29, 14, 11],
        [34, 34, 26, 45, 0, 20, 21, 31, 37],
        [34, 34, 28, 43, 20, 0, 15, 29, 40],
        [20, 20, 13, 29, 21, 15, 0, 14, 25],
        [6, 6, 7, 14, 31, 29, 14, 0, 12],
        [6, 6, 12, 11, 37, 40, 25, 12, 0],
    ],
    index=range(0, 9),
    columns=range(0, 9),
)

# Coordenadas aproximadas (centroides) para el mapa
COORDS = {
    0: (9.8644, -83.9194, "CD Cartago (depósito)"),
    1: (9.8644, -83.9194, "Cartago"),
    2: (9.8378, -83.8625, "Paraíso"),
    3: (9.9167, -84.0167, "La Unión"),
    4: (9.8000, -83.7833, "Jiménez"),
    5: (9.9020, -83.6711, "Turrialba"),
    6: (9.8956, -83.7794, "Alvarado"),
    7: (9.8961, -83.8500, "Oreamuno"),
    8: (9.7833, -83.9333, "El Guarco"),
}

CAPACIDAD_CAMION = 24  # pallets

# Paleta de colores para distinguir rutas en el mapa
ROUTE_COLORS = [
    "#C0392B", "#1F77B4", "#2E7D32", "#8E44AD",
    "#D68910", "#16A085", "#E74C3C", "#34495E",
]

# ----------------------------------------------------------------
# FUNCIONES AUXILIARES
# ----------------------------------------------------------------
def total_demand_from_products(df_prod: pd.DataFrame) -> dict[int, float]:
    """Devuelve dict {nodo: demanda_total} a partir de un df de productos."""
    return {
        int(row["nodo"]): float(row["Imperial"] + row["Pilsen"] + row["Tropical"])
        for _, row in df_prod.iterrows()
    }


def run_solver(demand: dict[int, float], dist_df: pd.DataFrame, capacity: float, n_max=None):
    dist_dict = build_dist_dict(dist_df)
    result = solve_cvrp(demand, dist_dict, capacity=capacity, n_vehicles_max=n_max, time_limit_s=30)
    return result


def routes_table(result, cantones_map: dict[int, str], demand: dict[int, float]) -> pd.DataFrame:
    rows = []
    for idx, (route, load, km) in enumerate(zip(result.routes, result.route_loads, result.route_km), start=1):
        nombres = " → ".join(
            "CD" if n == 0 else cantones_map.get(n, str(n)) for n in route
        )
        rows.append(
            {
                "Camión / Viaje": f"Viaje {idx}",
                "Ruta": nombres,
                "Carga (pallets)": int(load),
                "Capacidad usada": f"{load}/{int(CAPACIDAD_CAMION)}",
                "Distancia (km)": round(km, 1),
            }
        )
    return pd.DataFrame(rows)


def draw_map(result, cantones_map: dict[int, str], coords: dict[int, tuple]):
    center = coords[0][:2]
    m = folium.Map(location=center, zoom_start=10, tiles="CartoDB positron")

    # Marcador del CD
    folium.Marker(
        location=coords[0][:2],
        popup="CD Cartago (depósito)",
        tooltip="Centro de Distribución",
        icon=folium.Icon(color="darkblue", icon="industry", prefix="fa"),
    ).add_to(m)

    # Marcadores de cantones
    for nodo, (lat, lon, nombre) in coords.items():
        if nodo == 0:
            continue
        folium.CircleMarker(
            location=(lat, lon),
            radius=7,
            popup=f"{nombre}",
            tooltip=nombre,
            color="#1F3864",
            fill=True,
            fill_color="#FFFFFF",
            fill_opacity=1,
            weight=2,
        ).add_to(m)
        folium.map.Marker(
            (lat, lon),
            icon=folium.DivIcon(
                html=f'<div style="font-size:11px;font-weight:700;color:#1F3864;'
                f'transform:translate(8px,-6px);white-space:nowrap;">{nombre}</div>'
            ),
        ).add_to(m)

    # Dibujar rutas en rojo (mejores rutas resultantes del CVRP)
    for idx, route in enumerate(result.routes):
        color = ROUTE_COLORS[idx % len(ROUTE_COLORS)]
        points = [coords[n][:2] for n in route]
        folium.PolyLine(
            points,
            color="#E60000",
            weight=4.5,
            opacity=0.85,
            tooltip=f"Viaje {idx + 1}",
        ).add_to(m)
        # Flechas direccionales simples (puntos intermedios)
        for k in range(len(points) - 1):
            mid = (
                (points[k][0] + points[k + 1][0]) / 2,
                (points[k][1] + points[k + 1][1]) / 2,
            )
            folium.CircleMarker(
                location=mid,
                radius=2,
                color="#E60000",
                fill=True,
                fill_opacity=1,
            ).add_to(m)

    return m


def plot_load_chart(result, cantones_map: dict[int, str]):
    fig = go.Figure()
    for idx, (route, load) in enumerate(zip(result.routes, result.route_loads), start=1):
        fig.add_trace(
            go.Bar(
                x=[f"Viaje {idx}"],
                y=[load],
                name=f"Viaje {idx}",
                marker_color=ROUTE_COLORS[(idx - 1) % len(ROUTE_COLORS)],
                text=[f"{int(load)} pal."],
                textposition="outside",
            )
        )
    fig.add_hline(
        y=CAPACIDAD_CAMION,
        line_dash="dash",
        line_color=RED,
        annotation_text=f"Capacidad máxima ({int(CAPACIDAD_CAMION)} pallets)",
        annotation_position="top left",
    )
    fig.update_layout(
        title="Carga por viaje vs. capacidad del camión",
        yaxis_title="Pallets",
        showlegend=False,
        plot_bgcolor="white",
        height=380,
        margin=dict(t=60, b=20),
    )
    return fig


# ==================================================================
# SECCIÓN 1 · CASO BASE (DATOS ESTABLECIDOS — RESOLUCIÓN DIRECTA)
# ==================================================================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown("### 📊 Sección 1 — Caso base de Cartago (datos del enunciado)")
st.markdown(
    "Esta sección utiliza **directamente los datos provistos** en la diapositiva "
    "*Provincia: Cartago* (8 cantones, demanda total 406 pallets/semana, "
    "matriz de distancias por carretera). Se resuelve el CVRP minimizando "
    "los kilómetros totales recorridos."
)

col_tab, col_kpi = st.columns([2.4, 1])

with col_tab:
    st.markdown("**Demanda por producto y cantón (pallets/semana)**")
    df_base_display = DEMANDA_PRODUCTOS_BASE.drop(columns=["nodo"]).set_index("Cantón")
    st.dataframe(
        df_base_display.style.format("{:.0f}").background_gradient(
            cmap="Blues", subset=["Demanda total"]
        ),
        use_container_width=True,
    )
    total_row = pd.DataFrame(
        {
            "Imperial": [df_base_display["Imperial"].sum()],
            "Pilsen": [df_base_display["Pilsen"].sum()],
            "Tropical": [df_base_display["Tropical"].sum()],
            "Demanda total": [df_base_display["Demanda total"].sum()],
        },
        index=["TOTAL"],
    )
    st.dataframe(total_row.style.format("{:.0f}"), use_container_width=True)

with col_kpi:
    st.markdown("**Resumen del caso**")
    st.markdown(
        f"""
        <div class="kpi-box" style="margin-bottom:0.6rem;">
            <div class="kpi-value">8</div>
            <div class="kpi-label">Cantones</div>
        </div>
        <div class="kpi-box" style="margin-bottom:0.6rem;">
            <div class="kpi-value">406</div>
            <div class="kpi-label">Pallets / semana</div>
        </div>
        <div class="kpi-box">
            <div class="kpi-value">24</div>
            <div class="kpi-label">Pallets / camión</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

if st.button("🚀 Resolver CVRP — Caso base de Cartago", type="primary", key="solve_base"):
    with st.spinner("Optimizando rutas... minimizando kilómetros totales..."):
        demand_base = total_demand_from_products(DEMANDA_PRODUCTOS_BASE)
        result_base = run_solver(demand_base, DIST_MATRIX_BASE, CAPACIDAD_CAMION)
    st.session_state["result_base"] = result_base
    st.session_state["demand_base"] = demand_base

if "result_base" in st.session_state:
    result = st.session_state["result_base"]

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-value">{result.objective_km:.1f} km</div>'
            f'<div class="kpi-label">Distancia total</div></div>',
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-value">{result.n_vehicles}</div>'
            f'<div class="kpi-label">Viajes / camiones</div></div>',
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-value">{sum(result.route_loads):.0f}</div>'
            f'<div class="kpi-label">Pallets transportados</div></div>',
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-value">{result.status}</div>'
            f'<div class="kpi-label">Estado del solver</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    col_map, col_table = st.columns([1.5, 1])

    with col_map:
        st.markdown("**🗺️ Mapa de rutas óptimas — Provincia de Cartago**")
        m = draw_map(result, CANTONES, COORDS)
        st_folium(m, width=None, height=480, returned_objects=[])

    with col_table:
        st.markdown("**📋 Detalle de viajes**")
        st.dataframe(routes_table(result, CANTONES, st.session_state["demand_base"]), use_container_width=True, hide_index=True)
        st.plotly_chart(plot_load_chart(result, CANTONES), use_container_width=True)

st.markdown("</div>", unsafe_allow_html=True)


# ==================================================================
# SECCIÓN 2 · PARÁMETROS AJUSTABLES (SIMULADOR)
# ==================================================================
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown("### 🎛️ Sección 2 — Simulador con parámetros ajustables")
st.markdown(
    "Modifique la **demanda de cada producto** (Imperial, Pilsen, Tropical) por cantón "
    "y/o la **capacidad del camión** para explorar escenarios alternativos. "
    "El modelo recalcula la demanda total por cantón automáticamente y vuelve a resolver el CVRP."
)

with st.sidebar:
    st.markdown("## 🎛️ Parámetros del simulador")
    st.markdown("Ajuste la demanda por producto y cantón:")

    capacidad_custom = st.slider(
        "Capacidad del camión (pallets)",
        min_value=10,
        max_value=40,
        value=24,
        step=1,
        help="Restricción: cada camión solo puede llevar como máximo esta cantidad de pallets.",
    )

    st.markdown("---")
    st.markdown("**Demanda por producto (pallets/semana)**")

    demanda_custom_rows = []
    for _, row in DEMANDA_PRODUCTOS_BASE.iterrows():
        st.markdown(f"**{row['Cantón']}**")
        c1, c2, c3 = st.columns(3)
        imp = c1.number_input(
            "Imperial", min_value=0, value=int(row["Imperial"]), key=f"imp_{row['nodo']}", label_visibility="visible"
        )
        pil = c2.number_input(
            "Pilsen", min_value=0, value=int(row["Pilsen"]), key=f"pil_{row['nodo']}", label_visibility="visible"
        )
        tro = c3.number_input(
            "Tropical", min_value=0, value=int(row["Tropical"]), key=f"tro_{row['nodo']}", label_visibility="visible"
        )
        demanda_custom_rows.append(
            {"nodo": int(row["nodo"]), "Cantón": row["Cantón"], "Imperial": imp, "Pilsen": pil, "Tropical": tro}
        )

    st.markdown("---")
    reset = st.button("↩️ Restaurar valores del caso base")

if reset:
    for key in list(st.session_state.keys()):
        if key.startswith(("imp_", "pil_", "tro_")):
            del st.session_state[key]
    st.rerun()

df_custom = pd.DataFrame(demanda_custom_rows)
df_custom["Demanda total"] = df_custom["Imperial"] + df_custom["Pilsen"] + df_custom["Tropical"]

col_tab2, col_kpi2 = st.columns([2.4, 1])

with col_tab2:
    st.markdown("**Tabla de demanda ajustada por producto y cantón (pallets/semana)**")
    df_custom_display = df_custom.drop(columns=["nodo"]).set_index("Cantón")
    st.dataframe(
        df_custom_display.style.format("{:.0f}").background_gradient(
            cmap="Oranges", subset=["Demanda total"]
        ),
        use_container_width=True,
    )
    total_row2 = pd.DataFrame(
        {
            "Imperial": [df_custom_display["Imperial"].sum()],
            "Pilsen": [df_custom_display["Pilsen"].sum()],
            "Tropical": [df_custom_display["Tropical"].sum()],
            "Demanda total": [df_custom_display["Demanda total"].sum()],
        },
        index=["TOTAL"],
    )
    st.dataframe(total_row2.style.format("{:.0f}"), use_container_width=True)

    delta_total = df_custom_display["Demanda total"].sum() - df_base_display["Demanda total"].sum()
    delta_min = max(1, int(-(-df_custom_display["Demanda total"].sum() // capacidad_custom)))  # ceil division
    st.caption(
        f"Variación vs. caso base: **{delta_total:+.0f} pallets**. "
        f"Flota mínima estimada (cota inferior): **{delta_min} camiones** "
        f"de {capacidad_custom} pallets."
    )

with col_kpi2:
    st.markdown("**Resumen del escenario**")
    st.markdown(
        f"""
        <div class="kpi-box" style="margin-bottom:0.6rem;">
            <div class="kpi-value">{df_custom_display["Demanda total"].sum():.0f}</div>
            <div class="kpi-label">Pallets / semana</div>
        </div>
        <div class="kpi-box" style="margin-bottom:0.6rem;">
            <div class="kpi-value">{capacidad_custom}</div>
            <div class="kpi-label">Pallets / camión</div>
        </div>
        <div class="kpi-box">
            <div class="kpi-value">{delta_min}</div>
            <div class="kpi-label">Flota mínima (cota)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

if st.button("🚀 Resolver CVRP — Escenario ajustado", type="primary", key="solve_custom"):
    with st.spinner("Optimizando rutas con los nuevos parámetros..."):
        demand_custom = total_demand_from_products(df_custom)
        result_custom = run_solver(demand_custom, DIST_MATRIX_BASE, capacidad_custom)
    st.session_state["result_custom"] = result_custom
    st.session_state["demand_custom"] = demand_custom

if "result_custom" in st.session_state:
    result = st.session_state["result_custom"]

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-value">{result.objective_km:.1f} km</div>'
            f'<div class="kpi-label">Distancia total</div></div>',
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-value">{result.n_vehicles}</div>'
            f'<div class="kpi-label">Viajes / camiones</div></div>',
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-value">{sum(result.route_loads):.0f}</div>'
            f'<div class="kpi-label">Pallets transportados</div></div>',
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            f'<div class="kpi-box"><div class="kpi-value">{result.status}</div>'
            f'<div class="kpi-label">Estado del solver</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    col_map2, col_table2 = st.columns([1.5, 1])

    with col_map2:
        st.markdown("**🗺️ Mapa de rutas óptimas — Escenario ajustado**")
        m2 = draw_map(result, CANTONES, COORDS)
        st_folium(m2, width=None, height=480, returned_objects=[], key="map_custom")

    with col_table2:
        st.markdown("**📋 Detalle de viajes**")
        st.dataframe(routes_table(result, CANTONES, st.session_state["demand_custom"]), use_container_width=True, hide_index=True)
        st.plotly_chart(plot_load_chart(result, CANTONES), use_container_width=True, key="chart_custom")

st.markdown("</div>", unsafe_allow_html=True)


# ==================================================================
# SECCIÓN 3 · MODELO MATEMÁTICO (referencia)
# ==================================================================
with st.expander("📐 Ver formulación matemática del modelo (CVRP — Big-M)"):
    st.markdown(
        r"""
**Conjuntos**
- $N = \{0, 1, \dots, n\}$, donde $0$ es el CD y $1..n$ son los cantones.

**Parámetros**
- $d_i$: demanda del cantón $i$ (pallets/semana)
- $c_{ij}$: distancia en km entre $i$ y $j$
- $Q = 24$: capacidad máxima del camión (pallets)
- $M = Q + \max_i d_i$: constante Big-M

**Variables**
- $x_{ij} \in \{0,1\}$: 1 si un camión viaja directo de $i$ a $j$
- $u_i \ge 0$: carga acumulada del camión al llegar al cantón $i$

**Función objetivo**
$$\min \sum_{i \in N}\sum_{j \in N,\, j\ne i} c_{ij}\, x_{ij}$$

**Restricciones**

1. *Conservación de flujo* — Camión entra − Camión sale $= 0$:
$$\sum_{j} x_{ji} - \sum_{j} x_{ij} = 0 \quad \forall i \in \text{Cantones}$$

2. *Balance de carga (Entradas − Salidas = Demanda)*:
$$u_j \ge u_i + d_j - M(1 - x_{ij}) \quad \forall i \in N,\ j \in \text{Cantones},\ i \ne j$$

3. *Capacidad del camión*:
$$d_i \le u_i \le Q \quad \forall i \in \text{Cantones}$$

4. *Flota (Big-M sobre el número de salidas del CD)*:
$$\sum_{j} x_{0j} \le K$$
        """
    )

# ----------------------------------------------------------------
# FOOTER
# ----------------------------------------------------------------
st.markdown(
    """
    <div class="footer-note">
        Florida Bebidas · CVRP Provincia de Cartago · CD Río Segundo (Cartago) ·
        Modelo basado en Clase 12 — Flujos de Redes · Prof. David Benavides · UCR Sede Alajuela · I-2026
    </div>
    """,
    unsafe_allow_html=True,
)
