# Implementation Plan: Triaje de Brechas `entidad_ha` — Ajustes, Automatizaciones y Frigate

**Branch**: `004-triage-entidad-ha` | **Date**: 2026-08-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-triage-entidad-ha/spec.md`

## Summary

Tres piezas sobre la misma pregunta ("¿esta entidad de HA tiene un
estado esperado declarado y vigilado de verdad?"), con un hallazgo de
diseño central descubierto en `research.md` §4: el modelo actual de
`entidad_ha` en `evaluate.py` confunde "está en la lista de checks" con
"está sano ahora mismo" — para que las automatizaciones y Frigate
cuenten como brecha cuando incumplen su estado esperado (como pide
`spec.md`), hace falta que `esta_vigilado` refleje el resultado en vivo
del check, no solo su membresía. Enfoque técnico: 17 checks
`entity_state` y 33 `entity_available` (con una comprobación nueva de
"¿está `frigate` corriendo?") en `ha_monitor.py` (ya existe, se amplía);
`evaluate.py` pasa a leer el resultado real de cada check desde
`ha_monitor_state.json`; un tipo de brecha nuevo (`condicion_incumplida`)
para no confundir "nunca vigilado" con "vigilado y fallando"; y la regla
de `entity_category` como una extensión de `is_intentional()` en
`sources.py`/`evaluate.py`, con las excepciones ya acordadas.

## Technical Context

**Language/Version**: Python 3.11 (script privado `ha_monitor.py`, sin
cambio de intérprete) + Python de este repo (`src/inventory/`) — mismos
lenguajes que ya usa cada fichero.

**Primary Dependencies**: Solo librería estándar — `subprocess` para
comprobar si `frigate` está corriendo (mismo patrón "sin dependencias
externas" que `docker_monitor.py`/`beszel_hosts_monitor.py`). Sin
credenciales nuevas: `ha_monitor.py` ya tiene `HA_URL`/`HA_TOKEN`.

**Storage**: `ha_monitor_state.json` (ya existe, ampliado con 50 claves
nuevas, mismo esquema `{ok, down_since, label, motivo, detail}`) — sin
fichero nuevo, sin base de datos propia.

**Testing**: Sin test automático nuevo para `ha_monitor.py` (bash/Python
sin suite propia en el homelab, igual que el resto de monitores);
`test_docker_monitor.py`/`inventory.cli --selftest` ya cubren la lógica
de este repo — se amplía `--selftest` con casos para el tipo de brecha
nuevo y la regla de `entity_category`. Validación de extremo a extremo
con `quickstart.md`.

**Target Platform**: macOS (LaunchAgent existente de `ha_monitor.py`,
sin cambio de cadencia — sigue a 15 min) + este repo (CLI de inventario,
sin servicio nuevo).

**Project Type**: ampliación de dos scripts que ya existen — sin
proyecto nuevo, sin dashboard nuevo (ver Constraints).

**Performance Goals**: sin objetivo explícito. El único coste nuevo es
un `docker inspect frigate` por ciclo de `ha_monitor.py` (cada 15 min),
cacheado una vez por ejecución para no repetirlo en las 33 comprobaciones
de Frigate (`research.md` §3).

**Constraints**: FR-009 — ninguna acción correctiva ni cambio de
configuración de HA/Frigate/automatizaciones. Explícitamente **sin
cambios en `docker/homelab-dashboard/scripts/app.py`**: el recuento
"Domótica X/Y" ya suma todas las claves de `ha_monitor_state.json` sin
filtrar por las listas fijas de IDs (`research.md` §5), así que
`llega_a_dashboard="si"` es honesto sin tocar el dashboard.

**Scale/Scope**: 50 checks nuevos en `ha_monitor.py` (17 + 33), sobre un
total que pasa de 15 a 65 — mismo orden de magnitud que el resto del
fichero, sin generalizar el mecanismo más allá de lo que pide `spec.md`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Repasado principio por principio contra `.specify/memory/constitution.md`
v1.2.0. Sin violaciones — no hace falta rellenar Complexity Tracking.

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | Sí | `ha_monitor.py` ya reemite el latido y el aviso en cada cambio de estado para todos sus checks — los 50 nuevos heredan ese comportamiento sin código adicional. |
| II. Salud por Resultado | Sí | Núcleo de este feature: `esta_vigilado` pasa a reflejar el resultado real del check (`ok`), no solo si existe una entrada en `CHECKS` — `research.md` §4. |
| III. Estado Esperado Declarado | Sí | Declara por primera vez un esperado explícito para las 17 automatizaciones (`on`) y las 33 entidades de Frigate (disponible mientras el contenedor corre) — antes no tenían ninguno. |
| IV. Diagnóstico Previo a la Acción | N/A | Sin acciones correctivas (FR-008). |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | N/A | Sin acciones — cumplimiento por ausencia. |
| VI. Reversibilidad Escrita | N/A | Sin acciones que revertir. |
| VII. Un Actor por Acción | Sí | Ningún check nuevo reinicia ni corrige nada — solo lee y reporta. |
| VIII. Registro de Acciones e Hipótesis | N/A | No formula hipótesis de causa raíz. |
| IX. Mejora Medida Contra la Línea Base | Sí | `SC-001` se verifica relanzando el inventario — 309 brechas `entidad_ha` deben bajar en al menos 115. |
| X. Local por Defecto | Sí | Sin credenciales nuevas, sin integración remota nueva — reutiliza `HA_URL`/`HA_TOKEN` ya existentes y `docker inspect` local. |
| XI. Reproducibilidad Diferida | N/A | No diagnostica incidentes — expone si un estado ya declarado se cumple o no. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí | El recuento "Domótica X/Y" pasa a incluir 50 componentes más sin ambigüedad — ningún cambio de duplicado (no se toca `app.py`, `research.md` §5). |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | Cierra 165 de las 309 brechas `entidad_ha` restantes tras 002/003, con las 5 excepciones de seguridad y la cola larga documentadas como pendiente explícito, no ignoradas en silencio. |

## Project Structure

### Documentation (this feature)

```text
specs/004-triage-entidad-ha/
├── plan.md              # Este fichero (/speckit-plan)
├── research.md          # Fase 0 (/speckit-plan)
├── data-model.md         # Fase 1 (/speckit-plan)
├── quickstart.md         # Fase 1 (/speckit-plan)
├── contracts/             # Fase 1 (/speckit-plan)
│   └── ficheros.md
└── tasks.md               # Fase 2 (/speckit-tasks — no lo crea /speckit-plan)
```

### Source Code (repository root)

Mismo límite de repo que 001-003: el script que corre en la máquina del
homelab vive **fuera de este repositorio** (privado). Este feature toca
también, y por primera vez de forma central, el modelo de datos de este
repo público (`model.py`) — no solo `evaluate.py`/`sources.py` como 002.

```text
# Fuera de este repo — /Volumes/FastData/homelab/ (privado)

scripts/
└── ha_monitor.py                      # modificado:
    ├── CHECKS                         #   + 17 entradas entity_state
    │                                   #     (automatizaciones)
    │                                   #   + 33 entradas entity_available
    │                                   #     con requires_container
    │                                   #     (Frigate)
    └── check_status()                 #   + comprobación requires_container
                                        #     (docker inspect, cacheado)

# Dentro de este repo — src/inventory/ (feature 001, público)

src/inventory/model.py
└── TIPOS_BRECHA                       # + "condicion_incumplida"

src/inventory/sources.py
└── ha_entity_components() (sin cambio de lectura — entity_category
    ya viaja en meta desde feature 001)
    ├── ENTIDAD_HA_EXCEPCIONES_SEGURIDAD    # constante nueva (5 ids)
    ├── _ENTIDAD_HA_FRIGATE_FALLBACK         # constante nueva (33 ids,
    │                                        #   solo se usa si la lista
    │                                        #   en vivo está vacía)
    └── entidad_ha_frigate()                 # función nueva — prioriza
                                              #   la lista en vivo del
                                              #   puente, cae al fallback
                                              #   (hallazgo M1, ver
                                              #   research.md)

src/inventory/evaluate.py
├── is_intentional()                   # + regla entity_category,
│                                        #   usa sources.entidad_ha_frigate()
├── _vigilancia_entidad_ha()           # cambia: lee resultado real de
│                                        #   ha_monitor_check_result(),
│                                        #   no solo membresía
└── classify_gap()/gap_context()       # + rama condicion_incumplida

src/inventory/_homelab_bridge.py
├── ha_monitor_check_result()          # función nueva — lee
│                                        #   ha_monitor_state.json,
│                                        #   mapea entity_id → id de check
└── ha_monitor_conditional_entities()  # función nueva — entity_id con
                                        #   requires_container en CHECKS
                                        #   (vacío antes de desplegar US3)
```

**Structure Decision**: sin proyecto nuevo, sin script nuevo — un
fichero privado ampliado (`ha_monitor.py`) y cuatro ficheros de este
repo ya existentes tocados con precisión (un valor de enum, dos listas
de exclusión, una función de puente nueva, y el cambio de contrato de
`esta_vigilado` documentado explícitamente en `research.md` §4 en vez
de descubrirlo durante `/speckit-implement` como pasó en 002.

## Complexity Tracking

Sin violaciones de la Constitution Check — tabla no aplicable.

## Post-Design Constitution Check

*Re-chequeo tras la Fase 1 (`data-model.md`, `contracts/`,
`quickstart.md`).*

Sin cambios respecto a la tabla de arriba. Dos decisiones de diseño que
podrían haber introducido una violación se revisaron explícitamente y
no lo hacen:

- Cambiar `esta_vigilado` para que refleje el resultado real (en vez de
  membresía) aplica a los 15 checks `entidad_ha` ya existentes, no solo
  a los 50 nuevos — no es una ampliación de alcance no pedida (Principio
  IX): se comprobó en vivo que los 15 están en `ok` ahora mismo, así que
  no mueve la línea base existente, y hace el modelo más correcto para
  toda la categoría en vez de dejar una inconsistencia a medias.
- El nuevo campo `requires_container` en `ha_monitor.CHECKS` no es una
  segunda vía de comprobar si un contenedor está arriba (que violaría
  Principio X moviendo lógica fuera del mecanismo ya establecido en
  feature 001) — es una lectura local de `docker inspect`, mismo patrón
  ya usado por `docker_monitor.py`/`beszel_hosts_monitor.py`, no una
  reimplementación.
- `entidad_ha_frigate()` con fallback (añadido tras `/speckit-analyze`,
  hallazgo M1) tampoco introduce una segunda fuente de verdad duradera:
  mientras el fallback es la única lista disponible, es exactamente el
  mismo dato que se declara en `ha_monitor.CHECKS` en cuanto se
  despliega User Story 3 — dos copias solo durante la ventana de
  despliegue parcial, no de forma permanente (Principio IX, mejora
  medida sin regresión).

Gate superado. Listo para `/speckit-tasks`.
