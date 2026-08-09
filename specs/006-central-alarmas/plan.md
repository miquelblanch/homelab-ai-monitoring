# Implementation Plan: Central de Alarmas del Homelab

**Branch**: `006-central-alarmas` | **Date**: 2026-08-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-central-alarmas/spec.md`

## Summary

Una pestaña nueva "Alarmas" en el dashboard ya existente que unifica,
en una sola lista ordenada por gravedad, las condiciones de fallo que
10 orígenes ya calculan hoy por separado (contenedores, Home Assistant,
backup, latidos de monitores, relays, hosts externos, hub de Beszel,
agentes/crons, discos, inventario de cobertura). Enfoque técnico: una
función nueva `get_active_alarms()` en `homelab-dashboard/scripts/app.py`
que lee las funciones de origen que ya existen, clasifica cada
condición contra un catálogo estático `ALARM_TYPES` (explicación +
remediación + nivel, texto fijo por tipo, sin IA — FR-015), agrupa
cascadas del mismo `(origen, tipo)` por encima de un umbral (FR-013), y
expone el resultado en `/api/data`. Sin base de datos ni fichero nuevo,
sin script nuevo, sin cambios en `src/inventory/` (público) — solo una
ampliación de `app.py`, mismo patrón que las features 002 y 003.

## Technical Context

**Language/Version**: Python 3.11 (backend de `app.py`, FastAPI ya
desplegado) + JavaScript vanilla ya embebido en la misma plantilla HTML
— mismos dos lenguajes que ya usa el fichero, ninguno nuevo.

**Primary Dependencies**: Ninguna nueva. Solo lectura de los ficheros y
llamadas que las funciones de origen ya existentes usan
(`docker_monitor_state.json`, `ha_monitor_state.json`,
`.backup-heartbeat`, latidos de `heartbeat.py`, `socat_relays.json`,
`beszel_hosts.json`, `launchagents_raw.txt`, `df` para discos,
`inventario.json`).

**Storage**: N/A — `get_active_alarms()` no persiste nada; se recalcula
en cada petición a `/api/data`, igual que `get_external_hosts()` o
`get_beszel_hub_status()`.

**Testing**: Sin suite automática — `app.py` no tiene tests en este
repo privado (mismo criterio que features 002/003). Validación manual
por `quickstart.md`.

**Target Platform**: El contenedor Docker ya desplegado del dashboard
(`homelab-dashboard`) — ningún entorno nuevo.

**Project Type**: Ampliación de un servicio web que ya existe — sin
proyecto ni script nuevo que estructurar.

**Performance Goals**: Sin objetivo explícito distinto del resto del
dashboard — `get_active_alarms()` solo añade lecturas de fichero ya
baratas (los mismos ficheros que las otras 9 pestañas ya leen en cada
carga) y una clasificación en memoria sobre como mucho unos cientos de
elementos; no introduce ninguna llamada de red nueva.

**Constraints**: FR-015 — cero llamadas a servicios de IA/LLM, cero
tokens de API, en esta fase. FR-009 — ninguna acción de la pestaña
puede mutar el estado del homelab (solo lectura, sin endpoints POST
nuevos).

**Scale/Scope**: 10 orígenes ya existentes, 19 tipos de alarma
distintos en el catálogo inicial (`data-model.md`),
sobre un total de ~780 componentes vigilados (línea base actual:
0 brechas, `inventario.json` #75) — mismo orden de magnitud que el
resto del dashboard, sin generalizar a más.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Repasado principio por principio contra `.specify/memory/constitution.md`
v1.2.0. Sin violaciones — no hace falta rellenar Complexity Tracking.

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | Sí | `get_active_alarms()` se recalcula en cada carga (cada 15 s, mismo ciclo que el resto del dashboard) mientras la condición persista — no hay "solo se avisa una vez", no hay deduplicación por cambio de estado (FR-001, FR-010). |
| II. Salud por Resultado | Sí | No introduce ninguna noción nueva de salud — reutiliza literalmente el resultado (`ok`/`motivo`/`down_since`) que cada una de las 9 funciones de origen ya calcula (FR-002). |
| III. Estado Esperado Declarado | N/A | Este feature no declara ningún estado esperado nuevo — presenta condiciones que los 10 orígenes ya declaran y vigilan por su cuenta. |
| IV. Diagnóstico Previo a la Acción | N/A | Sin ninguna acción correctiva — FR-009 lo prohíbe explícitamente en este feature. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | N/A | Sin acciones — cumplimiento por ausencia, igual que features 002/003. |
| VI. Reversibilidad Escrita | N/A | Sin acciones que revertir. |
| VII. Un Actor por Acción | Sí | La pestaña no reinicia ni corrige nada — `docker_monitor.py` y el resto de monitores siguen siendo los únicos actores (FR-009). |
| VIII. Registro de Acciones e Hipótesis | N/A | No formula hipótesis de causa raíz ni ejecuta acciones que registrar — la agrupación de FR-013 es una regla de presentación (mismo `(origen, tipo)`), no una hipótesis de causa. |
| IX. Mejora Medida Contra la Línea Base | Sí | `SC-001`/`SC-005` se verifican comparando el recuento de la pestaña Alarmas contra la suma real de condiciones de fallo de los 10 orígenes — mismo criterio de verificación cruzada que ya usan features 002/003. |
| X. Local por Defecto | Sí | FR-015: ningún dato de diagnóstico sale de la máquina — sin LLM, sin token de API, sin servicio externo nuevo. |
| XI. Reproducibilidad Diferida | N/A | No diagnostica episodios ni formula hipótesis de causa — solo agrega y clasifica señales ya calculadas por otros. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí | FR-008/FR-010 garantizan que ninguna alarma real queda oculta (ni por tipo sin texto, ni por ausencia de alarmas) — razón de ser del feature entero. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | No añade vigilancia nueva (FR-002) — unifica la cobertura que el Frente 1 (features 001-006 previos) ya cerró, para que "esto es todo lo que está roto" sea una pregunta con una sola respuesta, no seis. |

## Project Structure

### Documentation (this feature)

```text
specs/006-central-alarmas/
├── plan.md              # Este fichero (/speckit-plan)
├── research.md          # Fase 0 (/speckit-plan)
├── data-model.md        # Fase 1 (/speckit-plan)
├── quickstart.md         # Fase 1 (/speckit-plan)
├── contracts/             # Fase 1 (/speckit-plan)
│   └── api-alarms.md
└── tasks.md               # Fase 2 (/speckit-tasks — no lo crea /speckit-plan)
```

### Source Code (repository root)

Mismo patrón de límite de repo que features 001-003: el código que
corre en la máquina del homelab vive **fuera de este repositorio**
(privado). Este feature no toca nada **dentro** de este repo público
— a diferencia de feature 003, no hace falta tocar
`src/inventory/evaluate.py`, porque el origen "inventario de
cobertura" se consume tal cual desde `inventario.json` (ya lo lee
`get_inventory()`), sin cambiar cómo se calculan las brechas.

```text
# Fuera de este repo — /Volumes/FastData/homelab/docker/homelab-dashboard/ (privado)

scripts/app.py                          # modificado:
├── ALARM_TYPES                         #   nuevo — diccionario estático,
│                                        #   id de tipo → {nivel, explicacion,
│                                        #   remediacion} (data-model.md)
├── ALARM_GROUP_THRESHOLD               #   nuevo — constante, valor 5 (research.md §3)
├── get_active_alarms()                 #   nueva — lee las 9 funciones de
│                                        #   origen ya existentes, clasifica
│                                        #   contra ALARM_TYPES, agrupa
│                                        #   cascadas, ordena por nivel +
│                                        #   antigüedad
├── collect() / endpoint /api/data      #   + clave "alarms" (contracts/api-alarms.md)
└── HTML/render()                       #   + pestaña nueva "Alarmas" en
                                          #     #top-nav y su <section id="alarmas">,
                                          #     mismo patrón que las 6 pestañas
                                          #     existentes (ver Inventario/Domótica)
```

**Structure Decision**: sin proyecto nuevo, sin script nuevo — una
función y un diccionario más en el único servicio web que ya existe,
mismo criterio que features 002/003. Más simple que feature 003: no
hace falta tocar el repo público, porque ningún origen de este feature
necesita una regla de evaluación nueva — los 10 ya la tienen.

## Complexity Tracking

Sin violaciones de la Constitution Check — tabla no aplicable.

## Post-Design Constitution Check

*Re-chequeo tras la Fase 1 (`data-model.md`, `contracts/`, `quickstart.md`).*

Sin cambios respecto a la tabla de arriba. Dos decisiones de diseño que
podrían haber introducido una violación se revisaron explícitamente y
no lo hacen:

- Que `ALARM_TYPES` vaya a fijar un **nivel de gravedad por tipo**
  (`data-model.md`) no es una declaración de "estado esperado" nueva
  (Principio III sigue N/A) — es una clasificación de presentación
  sobre una condición de fallo que el origen ya declaró como tal; no
  cambia qué cuenta como sano o no.
- Que `get_active_alarms()` agrupe alarmas (FR-013) filtrando el
  resultado de las 9 funciones de origen no viola el Principio XII
  (cero ausencias): la entrada agrupada sigue representando el 100%
  de las condiciones reales (con su recuento, `SC-005`), no las oculta
  — agrupar visualmente no es lo mismo que omitir.

Gate superado. Listo para `/speckit-tasks`.
