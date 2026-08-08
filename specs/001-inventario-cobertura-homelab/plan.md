# Implementation Plan: Inventario Sistemático de Cobertura del Homelab

**Branch**: `001-inventario-cobertura-homelab` | **Date**: 2026-08-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-inventario-cobertura-homelab/spec.md`

## Summary

Un inventario repetible y a demanda que recorre todo lo que compone el
homelab — contenedores, integraciones, entidades de Home Assistant, los dos
hosts externos (Uptime Kuma, AdGuard Home), Hermes/Bautista, el canal de
Telegram y la propia infraestructura de monitorización — y para cada
elemento responde si tiene estado esperado declarado, si se vigila de
verdad, y si un fallo llegaría al dashboard. Enfoque técnico: un script
Python 3.11 sin dependencias externas, siguiendo al pie de la letra las
convenciones ya establecidas por `docker_monitor.py`/`ha_monitor.py`/
`metrics_db.py` (stdlib, SQLite, `homelab_secrets.py`, patrón
`--selftest`), que persiste cada ejecución sin límite de tiempo y entrega
por los dos canales que ya existen: Telegram (reutilización directa) y el
dashboard, que exige una pequeña extensión de su propio código
(`docker/homelab-dashboard/scripts/app.py`) porque —comprobado leyendo el
código real, no asumido— no lee genéricamente lo que se deje en su carpeta
de datos, solo tiene lectores fijos para un puñado de ficheros concretos.
Sigue sin ser una interfaz nueva (`FR-018`): es una sección más en el único
panel que ya existe. No usa LangGraph: `BRIEFING.md` ya describe el
inventario y el grafo de diagnóstico como dos frentes independientes.

## Technical Context

**Language/Version**: Python 3.11 — mismo runtime que exige el resto de
LaunchAgents del homelab (Regla 10 del `CLAUDE.md` general); ver
`research.md` §1.

**Primary Dependencies**: Solo librería estándar (`sqlite3`, `subprocess`,
`urllib`, `json`, `pathlib`) — mismo patrón "sin dependencias externas" que
`docker_monitor.py`/`ha_monitor.py`/`metrics_db.py`. Sin LangGraph: este
feature es el frente de inventario, independiente del grafo de diagnóstico
(`BRIEFING.md`). Ver `research.md` §1 y §3.

**Storage**: SQLite — tablas nuevas junto a `homelab.db`, en
`docker/homelab-orchestrator/data/` (mismo directorio, cubierto por el
backup nocturno). Ver `research.md` §2 y `data-model.md`.

**Testing**: patrón de autocomprobación propio del homelab (`--selftest`,
lógica pura contra una BD temporal, sin Docker/HA/Telegram reales) — mismo
patrón que `metrics_db.py` y `test_docker_monitor.py`, sin `pytest`.

**Target Platform**: macOS, el mismo Mac Mini que ejecuta el resto de
monitores — script invocado a demanda (`FR-014`), sin exigir un
LaunchAgent para funcionar aunque pueda colgarse de uno más adelante.

**Project Type**: CLI de un solo proyecto, escrita como paquete Python
importable (no solo un script suelto) para que el futuro grafo de
LangGraph pueda reutilizar la lógica de las tres preguntas sin duplicarla —
ver "Project Structure" más abajo.

**Performance Goals**: sin objetivo explícito en el spec (categoría
"Outstanding" de bajo impacto tras `/speckit-clarify`). Se fija un
objetivo modesto no vinculante: una ejecución completa en el orden de
minutos, no horas, dado el volumen esperado (~40 contenedores + un puñado
de integraciones + entidades de HA, del orden de cientos).

**Constraints**: no debe modificar nada del homelab bajo ninguna
circunstancia (`FR-016`); ninguna función debe lanzar excepción hacia el
proceso que lo invoque (mismo principio "a prueba de fallos" que
`metrics_db.py`/`heartbeat.py`); nada de credenciales hardcodeadas (Regla 1
del `CLAUDE.md` general — se reutiliza `homelab_secrets.py`).

**Scale/Scope**: del orden de 40 contenedores, un puñado de integraciones,
2 hosts externos, Hermes + Telegram, la infraestructura de monitorización
propia, y entidades de Home Assistant (potencialmente cientos) — ver
Edge Cases del spec sobre el volumen de entidades HA.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Repasado principio por principio contra `.specify/memory/constitution.md`
v1.2.0. Sin violaciones — no hace falta rellenar Complexity Tracking.
*(Filas I, VIII y XI afinadas de "Parcial" a "N/A" tras `/speckit-analyze`,
2026-08-07 — hallazgos C1 y C2: un NO NEGOCIABLE marcado "Parcial" sin
resolución clara es una zona gris que vale la pena evitar.)*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | N/A | Este feature no ejecuta de forma programada en v1 (`FR-014`, a demanda) — no hay una condición persistente que re-emitir mientras exista, porque no hay "mientras" sin ejecución continua. Si en el futuro se cuelga de un LaunchAgent con cadencia regular, este principio pasa a aplicar de verdad y esta fila hay que revisarla. Convertir una brecha en alerta persistente sigue siendo del feature de corrección posterior, no de este. |
| II. Salud por Resultado | Sí | `FR-008`/`FR-009` registran el resultado real de la vigilancia, no si un proceso está "vivo" — `data-model.md`, tabla `hallazgos`. |
| III. Estado Esperado Declarado | Sí | Núcleo del feature (`FR-007`); caducidad a 90 días fijada en Clarification 3. |
| IV. Diagnóstico Previo a la Acción | N/A | No hay acción: `FR-016` prohíbe cualquier corrección. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | N/A | Sin acciones — cumplimiento trivial por ausencia, no por lista vacía definida. |
| VI. Reversibilidad Escrita | N/A | Sin acciones que revertir. |
| VII. Un Actor por Acción | Sí | El inventario no reinicia ni corrige nada — `docker_monitor.py` sigue siendo el único actor de remediación. |
| VIII. Registro de Acciones e Hipótesis | N/A (hipótesis) / Sí (registro) | No formula hipótesis de causa raíz — eso es del grafo, no aplica aquí. Sí registra cada ejecución y cada brecha con su contexto de forma permanente (`data-model.md`, tablas `ejecuciones`/`brechas`). |
| IX. Mejora Medida Contra la Línea Base | Sí | `SC-002` compara contra los 11 problemas del barrido 2026-08-01. |
| X. Local por Defecto | Sí | Sin dependencias externas nuevas; hosts externos identificados por software, no por IP (spec, Assumptions); lectura directa de ficheros/DB locales en vez de una integración remota nueva. |
| XI. Reproducibilidad Diferida | N/A (diagnóstico) / Sí (espíritu) | No diagnostica incidentes concretos — eso es el grafo, no aplica aquí. Sí conserva todas las ejecuciones sin límite (`FR-017`) para comparar cualquier punto pasado, que es la parte de este principio que le toca a un feature de auditoría. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí | El JSON que entrega este feature es informativo, no una alarma nueva del dashboard (`contracts/entrega.md`) — no duplica ni compite con las alarmas que ya generan los monitores existentes. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | Es la razón de ser de este feature — recorre todo el homelab por método, no por lista elegida a mano (`FR-001` a `FR-006`). |

## Project Structure

### Documentation (this feature)

```text
specs/001-inventario-cobertura-homelab/
├── plan.md              # Este fichero (/speckit-plan)
├── research.md          # Fase 0 (/speckit-plan)
├── data-model.md         # Fase 1 (/speckit-plan)
├── quickstart.md         # Fase 1 (/speckit-plan)
├── contracts/            # Fase 1 (/speckit-plan)
│   ├── cli.md
│   └── entrega.md
└── tasks.md              # Fase 2 (/speckit-tasks — no lo crea /speckit-plan)
```

### Source Code (repository root)

Opción de proyecto único (CLI), sin frontend/backend separados — no hay
interfaz web en este feature (`FR-018`).

```text
src/
└── inventory/
    ├── __init__.py
    ├── cli.py            # punto de entrada, contrato en contracts/cli.md
    ├── sources.py         # adaptadores de lectura: docker ps/inspect, API de HA
    │                      # + registro de entidades, launchctl, socat_relays.json,
    │                      # homelab.db (solo lectura)
    ├── model.py            # Componente, Hallazgo, Brecha, Ejecución (data-model.md)
    ├── identity.py          # emparejamiento por identificador estable (research.md §3)
    ├── evaluate.py           # las tres preguntas + caducidad a 90 días + intencionados
    ├── diff.py                # brechas nuevas vs conocidas entre ejecuciones (FR-015)
    ├── store.py                # persistencia SQLite, append-only (data-model.md)
    └── deliver.py               # Telegram + JSON del dashboard (contracts/entrega.md)

tests/
└── selftest/
    ├── test_identity.py    # emparejamiento por identificador estable
    ├── test_evaluate.py     # caducidad, clasificación de brechas, intencionados
    └── test_diff.py           # nuevas vs conocidas, retención sin purga
```

**Structure Decision**: proyecto único bajo `src/inventory/` como paquete
Python importable, no un script suelto — para que un futuro feature (el
grafo de diagnóstico de `BRIEFING.md`) pueda importar `evaluate.py`/
`sources.py` sin duplicar la lógica de las tres preguntas. `cli.py` es la
única puerta de entrada actual (`contracts/cli.md`); nada impide que un
LaunchAgent o un botón futuro del dashboard llamen al mismo paquete más
adelante, sin cambiar esta estructura.

**Nota de límite del repo**: el cambio en el dashboard (`get_inventory()` +
sección nueva en `app.py`, `contracts/entrega.md`) vive en
`docker/homelab-dashboard/scripts/app.py`, **fuera de este repositorio** —
es un fichero de la infraestructura privada del homelab, igual que
`docker_monitor.py` o `ha_monitor.py` ya lo son (spec, Assumptions). Este
repo (`homelab-ai-monitoring`, público) no incluye una copia de
`app.py`; `tasks.md` debe reflejar ese cambio como un parche a aplicar
sobre la máquina del homelab, no como un fichero que viva dentro de
`src/`.

## Complexity Tracking

Sin violaciones de la Constitution Check — tabla no aplicable.

## Post-Design Constitution Check

*Re-chequeo tras la Fase 1 (`data-model.md`, `contracts/`, `quickstart.md`).*

Sin cambios respecto a la tabla de arriba. Dos decisiones de diseño que
podrían haber introducido una violación se revisaron explícitamente y no la
introducen:

- El JSON de `contracts/entrega.md` hacia el dashboard **no** es una alarma
  nueva (Principio XII) — es un panel informativo; las alarmas siguen
  saliendo únicamente de los monitores existentes.
- Las tablas `append-only` de `data-model.md` (Clarification 2) no
  contradicen la regla de `homelab.db` sobre no purgar sin saber lo que se
  hace — al contrario, es la misma disciplina aplicada a una tabla con
  política de retención propia y explícita.

Gate superado. Listo para `/speckit-tasks`.
