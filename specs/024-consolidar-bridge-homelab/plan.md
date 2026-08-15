# Implementation Plan: Puente Único hacia los Scripts del Homelab

**Branch**: `024-consolidar-bridge-homelab` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/024-consolidar-bridge-homelab/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Extraer a dos módulos compartidos, nuevos y neutrales bajo `src/`
(ninguno de los tres paquetes existentes), las piezas verificadas como
duplicadas entre `diagnostico/_homelab_bridge.py`,
`inventory/_homelab_bridge.py` y `remediacion/_homelab_bridge.py`.
Cada uno de los tres ficheros existentes queda como fachada fina:
reexporta lo compartido y conserva localmente lo exclusivo de su
paquete. La partición en dos módulos (no uno) es la decisión central
de este plan — ver `research.md` §1.

## Technical Context

**Language/Version**: Python 3.11 (mismo que 023, sin dependencias nuevas)

**Primary Dependencies**: Ninguna externa. Los tres ficheros ya envuelven scripts privados del homelab (`homelab_secrets`, `heartbeat`, `docker_monitor`, `ha_monitor`) fuera de este repo, vía `sys.path` — sin cambios en ese mecanismo.

**Storage**: N/A — este refactor no toca datos, solo organización de código.

**Testing**: Mismo runner `tests.selftest` sin pytest. A diferencia de 023, **ningún test necesita reescribirse** — ver research.md §2, hallazgo clave de este plan.

**Target Platform**: Sin cambio.

**Project Type**: Biblioteca/CLI interna — tres paquetes hermanos (`diagnostico`, `inventory`, `remediacion`) bajo `src/`.

**Performance Goals**: N/A — reorganización sin cambio de comportamiento observable (FR-002, FR-006).

**Constraints**: Cero cambio de comportamiento observable para los tres paquetes (FR-002, FR-006, SC-003) — incluye no introducir ningún `import` nuevo a un script externo que un paquete no intentara ya importar hoy (research.md §1, la razón de partir en dos módulos y no uno).

**Scale/Scope**: 3 ficheros de ~150-180 líneas cada uno (493 líneas totales) → 2 módulos compartidos nuevos (pequeños) + los mismos 3 ficheros, ahora más cortos.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Igual que en 023: los principios I-IX, XII rigen comportamiento en vivo
del agente (alertas, acciones, dashboard) — esta feature no los toca,
es reorganización interna pura.

- **VII. Un Actor por Acción** — el bridge de `remediacion` expone
  `restart_container`/`breaker_decision`, la maquinaria de bajo nivel
  que ejecuta remediación. FR-003/FR-004 exigen explícitamente que la
  base compartida de `docker_critical()` no absorba ni filtre el hook
  de prueba exclusivo de remediación hacia los otros paquetes — es
  la misma garantía de aislamiento de actor, aplicada a un detalle de
  implementación. **PASS**, verificable por FR-003/SC-002.
- **X. Local por Defecto** — ninguna pieza compartida envía datos
  fuera de la máquina; el mecanismo de resolución de rutas y
  credenciales no cambia. **PASS**.

**Resultado: PASS, sin excepciones que registrar en Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/024-consolidar-bridge-homelab/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
src/
├── _homelab_bridge_common.py   # NUEVO — sys.path bootstrap, handles
│                                # homelab_secrets/docker_monitor, y las
│                                # 4 piezas que las 3 paquetes ya importan
│                                # hoy sin excepción: get_secret,
│                                # telegram_credentials,
│                                # docker_never_restart, docker_critical
│                                # (base). Importado por los 3 paquetes.
├── _homelab_bridge_heartbeat.py # NUEVO — handle heartbeat + record_heartbeat.
│                                # Solo diagnostico e inventory lo importan
│                                # — remediacion nunca ha importado heartbeat
│                                # y no debe empezar a hacerlo ahora
│                                # (research.md §1: evitar un import nuevo
│                                # que hoy no existe, aunque sea inocuo).
├── diagnostico/
│   └── _homelab_bridge.py       # Reexporta lo compartido; conserva local
│                                 # el import de ha_monitor y las 4 funciones
│                                 # de HA (exclusivas, sin cambios)
├── inventory/
│   └── _homelab_bridge.py       # Reexporta lo compartido; conserva local
│                                 # el import de ha_monitor y las funciones
│                                 # ha_monitor_*/available/read_heartbeat
│                                 # (exclusivas, sin cambios)
└── remediacion/
    └── _homelab_bridge.py       # Reexporta docker_never_restart y
                                  # telegram_credentials tal cual; docker_critical
                                  # pasa a ser un wrapper local que llama a la
                                  # base compartida y añade el hook de test
                                  # (FR-003); conserva listar_contenedores,
                                  # restart_container, breaker_decision,
                                  # recent_restart_attempts,
                                  # declarar_correccion_ia (exclusivas)
```

**Structure Decision**: Dos módulos compartidos, no uno — `_homelab_bridge_common.py`
(las 4 piezas que los tres paquetes ya necesitan hoy: homelab_secrets +
docker_monitor) y `_homelab_bridge_heartbeat.py` (la única pieza
compartida que necesita `heartbeat.py`, y que **solo** usan
diagnostico/inventory). Partir en dos, y no meterlo todo en un único
`_homelab_bridge_common.py`, es la única forma de que `remediacion`
siga sin intentar importar nunca `heartbeat.py` — algo que hoy no hace
y que FR-006/SC-003 prohíben cambiar, aunque el intento fallara sin
excepción (research.md §1 tiene el razonamiento completo: en Python,
importar un nombre de un módulo ejecuta el módulo entero, así que no
hay forma de que `remediacion` tome solo `docker_never_restart` de un
módulo que también intenta `import heartbeat` sin arrastrar ese intento
consigo). Ninguno de los dos módulos nuevos vive dentro de
`diagnostico/`, `inventory/` ni `remediacion/` — un módulo neutral
evita privilegiar a un paquete sobre otro y evita crear una dependencia
nueva de `remediacion` hacia `inventory` que hoy no existe.

## Complexity Tracking

*No aplica — el Constitution Check no encontró violaciones que justificar.*
