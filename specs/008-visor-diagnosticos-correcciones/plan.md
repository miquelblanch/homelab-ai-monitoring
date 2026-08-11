# Implementation Plan: Visor de Diagnósticos en Alarmas

**Branch**: `008-visor-diagnosticos-correcciones` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-visor-diagnosticos-correcciones/spec.md`

## Summary

Extender la pestaña "Alarmas" del dashboard (`homelab-dashboard/scripts/app.py`,
feature 006) para que cada alarma de contenedor caído (`get_active_alarms()`)
muestre, si existe, el diagnóstico del episodio de `diagnostico.db`
(feature 007) que corresponda a la caída actual — conclusión, hipótesis
y fechas — más el gasto diario acumulado de DeepSeek visible en algún
punto de la pestaña. Sin disparador de diagnósticos nuevos, sin pestaña
nueva, sin escritura sobre `diagnostico.db` (FR-009/FR-010).
`diagnostico.db` ya está montado en el contenedor del dashboard (mismo
volumen que `inventario.db`/`homelab.db`); no hace falta infraestructura
nueva.

## Technical Context

**Language/Version**: Python 3.11 (mismo runtime que el resto de
`app.py`, sin excepción)

**Primary Dependencies**: Ninguna nueva. `sqlite3` (ya usado en `app.py`
para `speedtest.db`, mismo patrón `mode=ro`), `zoneinfo` de la librería
estándar (normalización de fechas, research.md §4), sin JS de terceros
(mismo criterio que el resto del dashboard — JS vanilla embebido en
`app.py`).

**Storage**: Lectura de solo lectura contra `diagnostico.db`
(`/data/diagnostico.db` desde el contenedor del dashboard — mismo
volumen que `inventario.db`/`homelab.db`, ya montado,
`docker-compose.yml` de `homelab-dashboard`). Ninguna escritura nueva;
`docker_monitor_state.json` (fuente de `down_since`) no cambia su
formato en disco, solo se enriquece el JSON servido por `/api/data`.

**Testing**: Este repo (`homelab-ai-monitoring`) no contiene `app.py`
— vive en `/Volumes/FastData/homelab/docker/homelab-dashboard/`, fuera
del árbol de tests de este repo (mismo caso que el resto de features de
dashboard, 002/006). La validación es manual contra el dashboard real
(`quickstart.md`) más una comprobación programática mínima del
emparejamiento (research.md §3) ejecutable con `python3 -c`, sin
levantar el dashboard completo.

**Target Platform**: Contenedor Docker `homelab-dashboard` (macOS host,
OrbStack) — mismo target que el resto de `app.py`.

**Project Type**: Extensión de una aplicación web ya existente, no un
proyecto nuevo. No añade ningún paquete a `src/` de este repo — todo el
cambio vive en `homelab-dashboard/scripts/app.py`, fuera de este
repositorio (mismo patrón que features 002/006, ver sus `plan.md`).

**Performance Goals**: No aplica un objetivo nuevo — el emparejamiento
se calcula sobre, como mucho, unas pocas decenas de alarmas y episodios
(volumen real hoy: 8 episodios, 16 diagnósticos), en cada petición a
`/api/data`, mismo patrón sin caché que el resto del endpoint.

**Constraints**: Cero escritura sobre `diagnostico.db` (FR-010). Cero
disparo de diagnósticos nuevos (FR-009). Un episodio de una caída
anterior ya resuelta NUNCA se muestra como si fuera de la caída actual
(FR-004, Clarifications Q2) — el emparejamiento por `down_since` con
tolerancia acotada (research.md §2-§3) existe precisamente para
garantizar esto.

**Scale/Scope**: Un usuario (Miquel), lectura ocasional del dashboard.
Sin límite de volumen nuevo — el ya existente de `diagnostico.db`
(uso manual y esporádico, ver `plan.md` de 007).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | Este feature no calcula ninguna alerta nueva — muestra un diagnóstico ya calculado por 007 sobre una alarma que 006 ya clasificó. |
| II. Salud por Resultado | No aplica | No declara salud de ningún componente nuevo. |
| III. Estado Esperado Declarado | No aplica | No añade nada nuevo a vigilar — es un visor sobre dos features ya cerradas. |
| IV. Diagnóstico Previo a la Acción | No aplica | No hay ninguna acción en este feature (FR-009/010). |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción que ejecutar — el visor es estrictamente de lectura. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, no hay nada que revertir. |
| VII. Un Actor por Acción | No aplica | No actúa sobre ningún contenedor. |
| VIII. Registro de Acciones e Hipótesis | Ya cumplido por 007 | Este feature no registra nada nuevo — expone lo que `diagnostico.db` ya registra (research.md §1). |
| IX. Mejora Medida Contra la Línea Base | No aplica | No introduce ningún mecanismo de detección nuevo que medir contra una línea base. |
| X. Local por Defecto | Sí | Ningún dato sale de la máquina — lectura interna entre dos bases ya locales (`diagnostico.db`, `docker_monitor_state.json`), servidas al navegador de Miquel en la LAN. |
| XI. Reproducibilidad Diferida | No aplica | No calcula ningún diagnóstico — solo muestra los que 007 ya calculó y persistió de forma reproducible. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí, es el riesgo central | El emparejamiento por `down_since` con tolerancia acotada (research.md §2-§3) y la fecha siempre visible (spec.md FR-004/FR-005, Clarifications Q1) existen precisamente para que el dashboard nunca presente el diagnóstico de una caída anterior como si fuera de la actual — ver Edge Cases y SC-006 del spec. |
| XIII. Cobertura Sistemática, No Anecdótica | No aplica | No añade cobertura de vigilancia nueva — es una superficie de lectura sobre cobertura ya existente. |

**Resultado**: PASS. El único principio con riesgo real es el XII
(NO NEGOCIABLE), y el diseño de este plan (research.md §2/§3) existe
específicamente para cumplirlo — no hay violación que justificar en
Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/008-visor-diagnosticos-correcciones/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── api-diagnostico.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (fuera de este repo)

```text
/Volumes/FastData/homelab/docker/homelab-dashboard/scripts/app.py
  ├── get_active_alarms()             # feature 006, se modifica la rama "contenedores"
  ├── get_diagnostico_para_alarma(componente, down_since)  # NUEVO
  │     — lee diagnostico.db (mode=ro), empareja por down_since (research.md §2-§3)
  ├── get_gasto_diagnostico_hoy()      # NUEVO — lee gasto_diario del día en curso
  ├── /api/data                        # amplía "alarms" con un campo `diagnostico`
  │     opcional por alarma de contenedor, y un campo nuevo `gasto_diagnostico`
  └── (JS de la pestaña #alarmas)      # pinta el bloque de diagnóstico si existe
```

**Structure Decision**: no se crea ningún paquete nuevo en `src/` de
este repo — mismo patrón que features 002/006 (dashboard-only), todo el
cambio vive en `homelab-dashboard/scripts/app.py`, fuera de este
repositorio pero documentado aquí igual que los otros dos.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
