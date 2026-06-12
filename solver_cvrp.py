"""
solver_cvrp.py
================================================================
Resolutor del problema CVRP (Vehicle Routing Problem con
Capacidad) para Florida Bebidas - Provincia de Cartago.

Implementa EXACTAMENTE la misma formulacion del modelo AMPL
(cvrp_cartago.mod), usando PuLP + CBC (solver de codigo abierto
disponible en Streamlit Cloud sin licencias).

Restricciones modeladas:
  1) Conservacion de flujo:      Camion entra - Camion sale = 0
  2) Acumulacion de carga:       Entradas - Salidas = Demanda del canton
  3) Big-M para eliminar subtours y acotar cuantos camiones salen
  4) Capacidad maxima por camion: Q = 24 pallets
================================================================
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

import pandas as pd
import pulp


@dataclass
class CVRPResult:
    status: str
    objective_km: float
    arcs: list[tuple[int, int]]
    routes: list[list[int]]
    route_loads: list[float]
    route_km: list[float]
    n_vehicles: int


def _extract_routes(arcs: list[tuple[int, int]], depot: int = 0) -> list[list[int]]:
    """Reconstruye las rutas (secuencias de nodos) a partir de los arcos x[i,j]=1."""
    next_node = {}
    for i, j in arcs:
        if i == depot:
            continue
        next_node[i] = j

    starts = [j for (i, j) in arcs if i == depot]
    routes = []
    for start in starts:
        route = [depot, start]
        current = start
        while current != depot:
            nxt = next_node.get(current)
            if nxt is None:
                break
            route.append(nxt)
            if nxt == depot:
                break
            current = nxt
        routes.append(route)
    return routes


def solve_cvrp(
    demand: dict[int, float],
    dist: dict[tuple[int, int], float],
    capacity: float = 24,
    n_vehicles_max: int | None = None,
    time_limit_s: int = 60,
    msg: bool = False,
) -> CVRPResult:
    """
    Resuelve el CVRP de dos indices con eliminacion de subtours via
    variable de carga acumulada u_i (formulacion Big-M), idéntico al
    modelo AMPL.

    Parameters
    ----------
    demand : dict {nodo: demanda}, sin incluir el deposito (nodo 0)
    dist   : dict {(i, j): distancia_km}
    capacity : capacidad maxima por camion (pallets)
    n_vehicles_max : flota maxima disponible (None = sin cota explicita,
                      se usa una cota natural por demanda total / capacidad)
    """
    clientes = sorted(demand.keys())
    nodos = [0] + clientes
    total_demand = sum(demand.values())

    if n_vehicles_max is None:
        n_vehicles_max = max(1, int((total_demand / capacity) + len(clientes)))

    big_m = capacity + max(demand.values())

    prob = pulp.LpProblem("CVRP_Cartago", pulp.LpMinimize)

    # Variables x[i,j]
    arcs = [(i, j) for i in nodos for j in nodos if i != j]
    x = pulp.LpVariable.dicts("x", arcs, cat="Binary")

    # Variables u[i] (carga acumulada) para clientes
    u = pulp.LpVariable.dicts("u", clientes, lowBound=0, upBound=capacity)

    # Objetivo: minimizar distancia total
    prob += pulp.lpSum(dist[(i, j)] * x[(i, j)] for (i, j) in arcs)

    # (R1) Cada cliente tiene exactamente una entrada
    for j in clientes:
        prob += pulp.lpSum(x[(i, j)] for i in nodos if i != j) == 1

    # (R2) Cada cliente tiene exactamente una salida
    for i in clientes:
        prob += pulp.lpSum(x[(i, j)] for j in nodos if j != i) == 1

    # (R3) Conservacion de flujo: entrada - salida = 0
    for i in clientes:
        entrada = pulp.lpSum(x[(j, i)] for j in nodos if j != i)
        salida = pulp.lpSum(x[(i, j)] for j in nodos if j != i)
        prob += entrada - salida == 0

    # (R4) Flota: salidas del deposito <= K, entradas == salidas
    salidas_dep = pulp.lpSum(x[(0, j)] for j in clientes)
    entradas_dep = pulp.lpSum(x[(i, 0)] for i in clientes)
    prob += salidas_dep <= n_vehicles_max
    prob += entradas_dep == salidas_dep

    # (R5) Acumulacion de carga (Big-M, elimina subtours)
    for i in nodos:
        for j in clientes:
            if i == j:
                continue
            if i == 0:
                # arco desde el deposito
                prob += u[j] >= demand[j] - big_m * (1 - x[(0, j)])
            else:
                prob += u[j] >= u[i] + demand[j] - big_m * (1 - x[(i, j)])

    # (R6) Capacidad: demanda_i <= u_i <= Q
    for i in clientes:
        prob += u[i] >= demand[i]
        prob += u[i] <= capacity

    # Resolver
    solver = pulp.PULP_CBC_CMD(msg=msg, timeLimit=time_limit_s)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]

    chosen_arcs = [(i, j) for (i, j) in arcs if pulp.value(x[(i, j)]) is not None and pulp.value(x[(i, j)]) > 0.5]
    routes = _extract_routes(chosen_arcs, depot=0)

    route_loads = [sum(demand[node] for node in r if node != 0) for r in routes]
    route_km = [sum(dist[(r[k], r[k + 1])] for k in range(len(r) - 1)) for r in routes]

    objective_value = pulp.value(prob.objective) or 0.0

    return CVRPResult(
        status=status,
        objective_km=objective_value,
        arcs=chosen_arcs,
        routes=routes,
        route_loads=route_loads,
        route_km=route_km,
        n_vehicles=len(routes),
    )


def build_dist_dict(dist_matrix: pd.DataFrame) -> dict[tuple[int, int], float]:
    """Convierte un DataFrame (filas/columnas = nodos) en dict {(i,j): km}."""
    d = {}
    for i in dist_matrix.index:
        for j in dist_matrix.columns:
            if i != j:
                d[(int(i), int(j))] = float(dist_matrix.loc[i, j])
    return d
