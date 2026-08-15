# Implementation Plan: Evidencia de Diagnóstico Organizada por Origen

**Branch**: `023-evidencia-por-origen` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-evidencia-por-origen/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Partir `src/diagnostico/evidencia.py` (1.864 líneas, diez orígenes de
evidencia mezclados) en un paquete `diagnostico/evidencia/` con un módulo por
origen más un módulo de mecanismo compartido, preservando exactamente la
superficie pública actual (`from diagnostico import evidencia;
evidencia.congelar_vivo(...)`) mediante una fachada en `__init__.py` que
reexporta lo que los tres consumidores reales usan hoy. Los tests de
`tests/selftest/test_evidencia.py` (1.638 líneas) se dividen en paralelo, un
fichero por origen, importando su submódulo directamente en vez de alcanzar
funciones privadas a través de la fachada.

## Technical Context

**Language/Version**: Python 3.11 (mismo que el resto del repo — `python3 --version` → 3.11.4; sin dependencias nuevas)

**Primary Dependencies**: Ninguna externa. Solo librería estándar (`sqlite3`, `subprocess`, `json`, `pathlib`, `zoneinfo`) y los paquetes hermanos ya existentes del propio repo (`inventory.diff`, `inventory.store`, `inventory.model` — usados solo por el origen "inventario"; `diagnostico._homelab_bridge`, `diagnostico.model`, `diagnostico.store` — usados por varios orígenes)

**Storage**: SQLite (`homelab.db`, fuera de este repo, leído sin modo `ro` — decisión ya tomada en `research.md` de 007) y ficheros planos (logs de backup, estado de relays vía `_homelab_bridge`). Sin cambios: este refactor no toca cómo ni qué se lee, solo dónde vive el código que lo hace.

**Testing**: Runner propio sin pytest (`tests/selftest`, patrón `test_*` + `check(label, cond)`, descubierto por `pkgutil`). Sí usa `unittest.mock.patch.object` para sustituir funciones internas del módulo — punto crítico del refactor, ver `research.md`.

**Target Platform**: Mismo proceso Python que hoy invoca `PYTHONPATH=src python3 -m diagnostico.cli` — sin cambio de plataforma.

**Project Type**: Biblioteca/CLI interna — tres paquetes hermanos (`diagnostico`, `inventory`, `remediacion`) bajo `src/`, sin frontend.

**Performance Goals**: N/A — reorganización de código sin cambio de comportamiento observable ni de ruta de ejecución (FR-002).

**Constraints**: Cero cambio de comportamiento observable (FR-002, SC-004); ningún origen existente se modifica al añadir uno nuevo (FR-003); el mecanismo compartido no se duplica (FR-004).

**Scale/Scope**: 1 fichero de 1.864 líneas → ~10 módulos de origen + 1 módulo de mecanismo compartido + 1 fachada; 1 fichero de test de 1.638 líneas → ~10 ficheros de test, mismo criterio de partición.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Los principios I, II, III, V, VI, VII, VIII, IX, XII rigen el comportamiento
en vivo del agente de diagnóstico/remediación (alertas, acciones, dashboard)
— esta feature no toca ninguno: no añade ni quita alarmas, acciones ni
lógica de decisión, solo reorganiza dónde vive el código existente.

Dos principios sí aplican, como condición a preservar, no a construir:

- **XI. Reproducibilidad Diferida** — cada origen que hoy tiene variante
  `congelar_<origen>_historico` debe seguir siendo reproducible contra el
  mismo episodio pasado tras la reorganización. FR-002/SC-004 ya lo exigen
  explícitamente. **PASS** — el refactor no toca la lógica de ningún origen,
  solo su ubicación.
- **XIII. Cobertura Sistemática** — los diez orígenes de evidencia cubren
  hoy los nueve mecanismos generalizados por 006-central-alarmas más
  latidos (017). Ninguno puede perderse ni fusionarse por accidente al
  partir el fichero. FR-001/FR-003 ya lo exigen. **PASS** — Key Entities
  enumera los diez explícitamente y SC-001 hace la incorporación de
  orígenes nuevos verificable.

**Resultado: PASS, sin excepciones que registrar en Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/023-evidencia-por-origen/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/
├── evidencia/                    # antes evidencia.py (1.864 líneas)
│   ├── __init__.py               # fachada: reexporta la superficie pública actual
│   ├── _compartido.py            # mecanismo compartido real (research.md §2): conexión BD, docker_logs_tail, _docker_bin
│   ├── contenedor.py             # congelar_vivo / congelar_historico (feature 007)
│   ├── disco.py                  # congelar_disco_vivo / _historico (009)
│   ├── ha.py                     # congelar_ha_vivo / _historico (010)
│   ├── backup.py                 # congelar_backup_vivo / _historico (011)
│   ├── relay.py                  # congelar_relay_vivo / _historico (012)
│   ├── inventario.py             # congelar_inventario_vivo / _historico (013)
│   ├── host_externo.py           # congelar_host_externo_vivo / _historico (014)
│   ├── hub_beszel.py             # congelar_hub_beszel_vivo / _historico (015)
│   ├── agente.py                 # congelar_agente_vivo — solo vivo (016)
│   └── latido.py                 # congelar_latido_vivo — solo vivo (017)
├── _homelab_bridge.py            # sin cambios — fuera de alcance (ver Assumptions)
├── cli.py                        # sin cambios de comportamiento — sigue llamando evidencia.congelar_*
├── deepseek.py                   # sin cambios de comportamiento — sigue llamando evidencia.nombres_relay_evidenciados/listar_nombres_relay
├── model.py
└── store.py

tests/selftest/
├── test_evidencia_contenedor.py  # antes: primer tramo de test_evidencia.py
├── test_evidencia_disco.py
├── test_evidencia_ha.py
├── test_evidencia_backup.py
├── test_evidencia_relay.py
├── test_evidencia_inventario.py
├── test_evidencia_host_externo.py
├── test_evidencia_hub_beszel.py
├── test_evidencia_agente.py
└── test_evidencia_latido.py
```

**Structure Decision**: Paquete `diagnostico/evidencia/` con un módulo por
origen (mismo criterio de partición que `data-model.md`) más `_compartido.py`
para lo que de verdad usan varios orígenes a la vez (ver `research.md` para
qué es y qué no es "compartido"). `__init__.py` actúa como fachada de
compatibilidad: reexporta exactamente los nombres que hoy usan los tres
consumidores reales (`cli.py`, `remediacion/acciones.py`, `deepseek.py`), así
que ninguno de los tres cambia una sola línea — es la forma de cumplir FR-002
con el menor radio de cambio posible, en vez de reescribir sus imports.
`tests/selftest/` se reorganiza con el mismo criterio (FR-007), y cada test
importa y parchea su propio submódulo directamente en vez de alcanzar
funciones privadas a través de la fachada (ver `research.md`, riesgo de
`patch.object` roto).

## Complexity Tracking

*No aplica — el Constitution Check no encontró violaciones que justificar.*

## Constitution Check — repaso posterior al diseño (Fase 1)

`research.md` y `data-model.md` no introdujeron nada que el repaso inicial
no contemplara: ningún origen se fusiona, ninguno pierde su variante
histórica más allá de lo que ya era cierto hoy (agente y latido, sin
histórico real desde su feature original), y la fachada de
`contracts/fachada-evidencia.md` existe precisamente para que XI y XIII
sigan cumpliéndose de forma verificable. **Se confirma PASS, sin cambios
respecto al repaso inicial.**
