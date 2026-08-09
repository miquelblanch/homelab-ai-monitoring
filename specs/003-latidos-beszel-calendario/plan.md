# Implementation Plan: Latido Propio — Recordatorios de Nextcloud y Beszel (Hub)

**Branch**: `003-latidos-beszel-calendario` | **Date**: 2026-08-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-latidos-beszel-calendario/spec.md`

## Summary

Dos piezas de la infraestructura de monitorización del homelab no tienen
señal propia. Enfoque técnico: (1) una llamada a `heartbeat.write()` al
final de `bautista-calendar.sh`, con `detail` limitado a tres etiquetas
fijas para no interpolar contenido de calendario sin escapar
(`research.md` §1); (2) ampliar el `scripts/beszel_hosts_monitor.py` que
ya existe (feature 002) para capturar también `updated` de los 3 sistemas
que Beszel vigila, y una función nueva en `app.py` que decide, al leer,
si los 3 han perdido frescura a la vez (`research.md` §3-§5). Ninguna
pieza es un script nuevo ni una base de datos nueva — las dos son
extensiones de mecanismos que feature 001 y feature 002 ya dejaron
construidos.

## Technical Context

**Language/Version**: Python 3.11 (el bloque inline que se añade a
`bautista-calendar.sh`, y la ampliación de `beszel_hosts_monitor.py`) +
Bash (el propio `bautista-calendar.sh`, sin cambiar de intérprete) — mismos
lenguajes que ya usa cada fichero, ninguno nuevo.

**Primary Dependencies**: Solo librería estándar (`sqlite3`, `json`,
`datetime`) — mismo patrón "sin dependencias externas" que el resto del
homelab y que feature 002.

**Storage**: `beszel_hosts.json` (ya existe, feature 002) y el fichero de
latido de `heartbeat.py` (ya existe, mecanismo general del homelab) —
ninguno de los dos cambia de ubicación ni de mecanismo de escritura,
solo de contenido. Ver `data-model.md`.

**Testing**: `--selftest` ampliado en `beszel_hosts_monitor.py` (parseo
de `updated` y la decisión "3 de 3 viejos") — mismo patrón que feature
002 ya estableció en ese fichero. Sin test automático para el cambio en
`bautista-calendar.sh` (bash, sin suite propia en el homelab); se valida
con `quickstart.md`, igual que el resto de scripts bash del proyecto
(`dump_socat_status.py` es la excepción Python sin test, no la norma).

**Target Platform**: macOS (LaunchAgents ya existentes,
`bautista-calendar.sh` y `beszel_hosts_monitor.py`) + el contenedor
Docker ya desplegado del dashboard (`app.py`) — mismos dos entornos que
feature 002, ninguno nuevo.

**Project Type**: dos extensiones pequeñas sobre infraestructura que ya
existe — sin script nuevo, sin proyecto nuevo que estructurar.

**Performance Goals**: sin objetivo explícito (Outstanding de bajo
impacto, igual que feature 002) — la ampliación de
`beszel_hosts_monitor.py` añade una columna a una consulta SQL que ya se
hacía, sin coste adicional apreciable.

**Constraints**: el `detail` del latido de recordatorios NUNCA debe
llevar contenido derivado de los eventos del calendario (`research.md`
§1, inyección de comandos) — es la única restricción de seguridad nueva
de este feature. Ninguna acción correctiva (`FR-006`); ninguna
credencial nueva.

**Scale/Scope**: 1 cron diario, 3 sistemas vigilados por Beszel — mismo
orden de magnitud que feature 002, sin generalizar a más.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Repasado principio por principio contra `.specify/memory/constitution.md`
v1.2.0. Sin violaciones — no hace falta rellenar Complexity Tracking.

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | Sí | Los dos latidos se reemiten cada ciclo mientras el mecanismo esté vivo; si el cron de recordatorios deja de correr, o Beszel se queda sin datos frescos, el dashboard lo sigue mostrando así en cada carga, no solo en el primer cambio de estado. |
| II. Salud por Resultado | Sí | Núcleo de `FR-004`: un dato de Beszel viejo no cuenta como "sano" — se calcula al leer, no se asume del último valor escrito. |
| III. Estado Esperado Declarado | N/A | Este feature no declara estados esperados nuevos — expone si dos procesos ya existentes (el cron, el sondeo de Beszel) siguen produciendo resultado. |
| IV. Diagnóstico Previo a la Acción | N/A | Sin acciones correctivas (`FR-006`) — solo visualización. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | N/A | Sin acciones — cumplimiento por ausencia. |
| VI. Reversibilidad Escrita | N/A | Sin acciones que revertir. |
| VII. Un Actor por Acción | Sí | Ni el latido de recordatorios ni la comprobación de Beszel reinician ni corrigen nada. |
| VIII. Registro de Acciones e Hipótesis | N/A | No formula hipótesis de causa raíz ni ejecuta acciones que registrar. |
| IX. Mejora Medida Contra la Línea Base | Sí | `SC-003` se verifica relanzando el inventario — las 2 brechas de `infra_monitorizacion` (Beszel hub) e `integracion` (Recordatorios de Nextcloud) que contaba la línea de base deben desaparecer. |
| X. Local por Defecto | Sí | Sin credenciales ni integración remota nueva — mismo acceso local (Docker/volumen, `heartbeat.py`) que ya usa el resto del homelab. |
| XI. Reproducibilidad Diferida | N/A | No diagnostica incidentes — solo expone si dos procesos siguen produciendo resultado. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí | Razón de ser de `FR-004`: la condición "un sistema individual sin dato fresco" no se duplica como "el hub está roto" — ya tiene su propia alarma en el panel de hosts externos de feature 002. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | Cierra 2 de las 2 brechas reales que quedaban tras feature 002 (`BRIEFING.md`), y el propio mecanismo nuevo hereda su latido (`FR-008`, reutilizando el de `beszel-hosts` en vez de crear uno sin vigilar). |

## Project Structure

### Documentation (this feature)

```text
specs/003-latidos-beszel-calendario/
├── plan.md              # Este fichero (/speckit-plan)
├── research.md          # Fase 0 (/speckit-plan)
├── data-model.md         # Fase 1 (/speckit-plan)
├── quickstart.md         # Fase 1 (/speckit-plan)
├── contracts/             # Fase 1 (/speckit-plan)
│   └── ficheros.md
└── tasks.md               # Fase 2 (/speckit-tasks — no lo crea /speckit-plan)
```

### Source Code (repository root)

Mismo patrón de límite de repo que feature 001 y feature 002: el código
que corre en la máquina del homelab vive **fuera de este repositorio**
(privado). Lo único que este feature toca **dentro** de este repo es
`src/inventory/evaluate.py` — y solo porque, igual que pasó con
`host_externo` al cerrar feature 002 (ver `tasks.md` de esa feature,
sección Notes), sus dos categorías siguen codificando a mano que estas
brechas "no llegan al dashboard". Anticiparlo aquí evita que sea otra
vez un hallazgo de última hora durante la validación de `SC-003`.

```text
# Fuera de este repo — /Volumes/FastData/homelab/ (privado)

scripts/
├── bautista-calendar.sh              # modificado — + heartbeat.write()
│                                       #   al final, detail de 3 etiquetas fijas
└── beszel_hosts_monitor.py            # modificado (feature 002) — la consulta
                                        #   SQL suma `updated`; build_payload()
                                        #   añade `hub_systems` con todos los
                                        #   sistemas, no solo los 2 canónicos

docker/homelab-orchestrator/data/
└── beszel_hosts.json                 # sin script nuevo — mismo fichero de
                                        #   feature 002, con la clave nueva
                                        #   `hub_systems`

docker/homelab-dashboard/
└── scripts/app.py                     # modificado:
    ├── MONITOR_JOBS                   #   + entrada "bautista-calendar"
    ├── MONITOR_INFO                   #   + descripción "bautista-calendar"
    ├── get_beszel_hub_status()        #   nueva función — decide sano/no-sano
    │                                   #   por antigüedad de hub_systems
    ├── collect()                      #   + beszel_hub
    └── HTML/render()                  #   + fila "Beszel (hub)" en la tabla
                                        #     "Estado de los monitores"
                                        #     (mismo patrón que "Backup diario")

# Dentro de este repo — src/inventory/ (feature 001, público)

src/inventory/evaluate.py
└── evaluate_component()               # modificado:
    ├── categoría "integracion"        #   "Recordatorios de Nextcloud" pasa
    │                                   #   de hardcode a `_vigilancia_por_heartbeat`
    │                                   #   sobre el job "bautista-calendar"
    └── categoría "infra_monitorizacion" # "Beszel (hub)" pasa de hardcode a
                                          #   leer beszel_hosts.json (vía
                                          #   _homelab_bridge.py, función nueva)
                                          #   y aplicar la misma regla de
                                          #   "3 de 3 viejos" que app.py
```

**Structure Decision**: sin proyecto nuevo, sin script nuevo — dos
ficheros existentes ampliados (`bautista-calendar.sh`,
`beszel_hosts_monitor.py`) y un parche más al único servicio web que ya
existe, mismo criterio que feature 002. La única novedad de estructura
frente a 001/002 es que este feature sí toca código dentro de este repo
público (`evaluate.py`) desde el propio plan, en vez de descubrirlo
durante `/speckit-implement` como pasó en feature 002.

## Complexity Tracking

Sin violaciones de la Constitution Check — tabla no aplicable.

## Post-Design Constitution Check

*Re-chequeo tras la Fase 1 (`data-model.md`, `contracts/`, `quickstart.md`).*

Sin cambios respecto a la tabla de arriba. Una decisión de diseño que
podría haber introducido una violación se revisó explícitamente y no lo
hace:

- Calcular `sano` del hub en el momento de leer (`app.py`), en vez de
  persistir un booleano al escribir (`beszel_hosts_monitor.py`), no es
  una declaración de estado esperado nueva (Principio III sigue N/A,
  ver tabla) — es la misma decisión de diseño que feature 002 ya tomó
  para `generated_at`, aplicada al mismo fichero.
- Que `evaluate.py` necesite lógica nueva para "Beszel (hub)" (leer
  `beszel_hosts.json` y aplicar la regla de 3-de-3) en vez de un simple
  latido, en vez de reutilizar tal cual `_vigilancia_por_heartbeat`, no
  es una violación de Principio X (Local por Defecto): sigue siendo
  lectura local de un fichero que ya existe, solo con una regla de
  decisión distinta a la de los demás monitores basados en latido.

Gate superado. Listo para `/speckit-tasks`.
