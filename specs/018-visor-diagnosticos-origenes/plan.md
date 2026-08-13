# Implementation Plan: Generalizar el Visor de Diagnósticos a los 9 Orígenes Restantes

**Branch**: `018-visor-diagnosticos-origenes` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/018-visor-diagnosticos-origenes/spec.md`

## Summary

Arregla el emparejamiento roto de `contenedor` (bug real, `WHERE
contenedor = ?` contra un esquema migrado a `componente`+`origen` en
009) y generaliza `get_diagnostico_para_alarma()` — que hoy solo
servía a contenedor — a una función única,
`get_diagnostico_para_origen(origen, identidad, down_since=None)`, que
sirve a los 10 orígenes de `get_active_alarms()`. Sin `down_since`
(8 de los 10 orígenes: disco, backup, relay, inventario, host externo,
hub de Beszel, agente, latido), toma el episodio más reciente de
`(origen, identidad)` sin ventana — no hay ancla temporal real que
comparar. Con `down_since` (contenedor, HA), aplica la misma
tolerancia de 30 min ya validada por 008. Los crons de Hermes y las
alarmas agrupadas nunca llevan diagnóstico (FR-006/FR-007). Sin
cambios de frontend — `diagnosticoHtml(a)` ya es agnóstica al origen.

## Technical Context

**Language/Version**: Python 3.11 (mismo runtime que el resto de
`app.py`, sin excepción)

**Primary Dependencies**: Ninguna nueva. `sqlite3` (ya usado en `app.py`
para `diagnostico.db` desde 008, mismo patrón `mode=ro`).

**Storage**: Lectura de solo lectura contra `diagnostico.db`
(`/data/diagnostico.db`, ya montado — mismo volumen que 008). Ninguna
escritura nueva.

**Testing**: Este repo (`homelab-ai-monitoring`) no contiene `app.py`
— vive en `/Volumes/FastData/homelab/docker/homelab-dashboard/`, sin
control de versiones (mismo caso que 002/006/008). La validación es
manual contra el dashboard real (`quickstart.md`) más una comprobación
programática mínima del emparejamiento por origen (research.md §3),
ejecutable con `python3 -c` contra `diagnostico.db` real, sin levantar
el contenedor. Antes de cualquier edición se hace copia de seguridad
de `app.py` (research.md §5) — no hay `git diff` ni revert fácil para
este fichero.

**Target Platform**: Contenedor Docker `homelab-dashboard` (macOS
host, OrbStack) — mismo target que 008. Reconstrucción con `docker
compose up -d --build` tras el cambio (no está en la lista de
contenedores críticos que exigen aprobación explícita).

**Project Type**: Extensión de una aplicación web ya existente. No
añade ningún paquete a `src/` de este repo — todo el cambio vive en
`homelab-dashboard/scripts/app.py`, fuera de este repositorio (mismo
patrón que 002/006/008).

**Performance Goals**: Sin objetivo nuevo — el emparejamiento se
calcula sobre, como mucho, unas pocas decenas de alarmas y episodios,
en cada petición a `/api/data`, mismo patrón sin caché que 008.

**Constraints**: Cero escritura sobre `diagnostico.db` (FR-011). Cero
disparo de diagnósticos nuevos (FR-010). Un episodio de una caída
anterior ya resuelta NUNCA se muestra como si fuera de la actual, para
los 2 orígenes con ancla temporal (FR-003). Los crons de Hermes y las
alarmas agrupadas nunca llevan diagnóstico (FR-006/FR-007). Cada
origen se resuelve en su propio `try/except` — el patrón que ya usa
`get_active_alarms()` para las alarmas mismas (FR-009: un origen roto
no debe tumbar los demás).

**Scale/Scope**: Un usuario (Miquel), lectura ocasional del dashboard.
Sin límite de volumen nuevo — el ya existente de `diagnostico.db` (17
episodios reales al escribir este plan).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — muestra diagnósticos ya calculados por el motor sobre alarmas que 006 ya clasificó. |
| II. Salud por Resultado | No aplica | No declara salud de ningún componente nuevo. |
| III. Estado Esperado Declarado | No aplica | No añade nada nuevo a vigilar — es un visor sobre features ya cerradas. |
| IV. Diagnóstico Previo a la Acción | No aplica | Sin ninguna acción en este feature (FR-010/011). |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción que ejecutar — estrictamente de lectura. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | No aplica | No actúa sobre ningún componente del homelab. |
| VIII. Registro de Acciones e Hipótesis | Ya cumplido por 007-017 | No registra nada nuevo — expone lo que `diagnostico.db` ya registra para los 10 orígenes. |
| IX. Mejora Medida Contra la Línea Base | No aplica | No introduce ningún mecanismo de detección nuevo. |
| X. Local por Defecto | Sí | Ningún dato sale de la máquina — lectura interna, servida al navegador de Miquel en la LAN. |
| XI. Reproducibilidad Diferida | No aplica | No calcula ningún diagnóstico — solo muestra los que el motor ya calculó y persistió. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí, es el riesgo central — y la motivación de User Story 1 | El bug de contenedor es en sí mismo una violación activa de este principio (research.md §1); este feature la corrige, y generaliza el mismo cuidado (ventana de tolerancia donde hay ancla real, "más reciente sin ventana" donde no, nunca inventar una que la evidencia no tiene) a los 9 orígenes restantes. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí, con un límite explícito | Generaliza la superficie de lectura a 9 de los 10 orígenes ya cubiertos por el motor; los crons de Hermes quedan fuera explícitamente (FR-006/FR-012) — mecanismo sin origen en `diagnostico.py`, no una omisión silenciosa. |

**Resultado**: PASS. El principio con riesgo real es el XII (NO
NEGOCIABLE) — el propio motivo de este feature es corregir una
violación activa suya y evitar introducir otras nuevas al generalizar.
Sin violaciones que justificar en Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/018-visor-diagnosticos-origenes/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── api-diagnostico.md   # Supersede el contrato de 008 (solo contenedor)
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (fuera de este repo)

```text
/Volumes/FastData/homelab/docker/homelab-dashboard/scripts/app.py
  ├── get_diagnostico_para_origen(origen, identidad, down_since=None)  # NUEVO
  │     — sustituye a get_diagnostico_para_alarma() (008); arregla el
  │       WHERE contenedor= roto y generaliza el emparejamiento
  ├── HOSTS_EXTERNOS_CANONICO   # NUEVO — mapeo nombre de pantalla → nombre
  │     canónico, mismo valor que evidencia.py::HOSTS_EXTERNOS (014)
  ├── get_active_alarms()      # se modifican las 10 ramas de origen para
  │     pasar la identidad real (no siempre la etiqueta de pantalla) y,
  │     donde aplica, down_since — la rama "agentes"/crons no cambia
  ├── /api/data                 # "alarms[].diagnostico" ya existía (008);
  │     ahora se puebla también para los 9 orígenes restantes
  └── (JS de la pestaña #alarmas)  # SIN CAMBIOS — diagnosticoHtml(a) ya
        es agnóstica al origen (research.md §2)
```

**Structure Decision**: no se crea ningún paquete nuevo en `src/` de
este repo — mismo patrón que 002/006/008, todo el cambio vive en
`homelab-dashboard/scripts/app.py`, fuera de este repositorio pero
documentado aquí igual que los otros tres.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
