# Implementation Plan: Generalizar el Diagnóstico a los Latidos de Monitores

**Branch**: `017-diagnostico-latidos` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-diagnostico-latidos/spec.md`

## Summary

Generalizar `src/diagnostico/` (007, generalizado a discos en 009, HA
en 010, backups en 011, relays en 012, inventario en 013, hosts
externos en 014, el hub de Beszel en 015 y los agentes en 016) para
que un `Episodio` pueda ser también de latido de monitor: un décimo
valor de `origen` (`"latido"`, sin migración de esquema). **Segundo
origen del proyecto sin ningún modo diferido** (el primero fue
"agente" en 016, por el mismo tipo de limitación real) — la evidencia
en vivo lee `<job>.json` de `MONITOR_HEARTBEATS_DIR` (mismo directorio
que ya lee `app.py::get_monitor_heartbeats()`) y replica su cálculo
exacto de `ok` a partir de la antigüedad del latido y el umbral propio
del job; no existe ninguna fuente histórica real que consultar
(research.md §2), así que `congelar` no ofrece ningún flag
`--latido-historico`. Cierra el décimo y último mecanismo relacionado
con la Central de Alarmas que quedaba pendiente desde 016. El gasto
diario sigue siendo un único acumulado compartido (FR-007) —
`gasto.py` no cambia. `store.py` tampoco cambia.

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a 007-016)

**Primary Dependencies**: Ninguna nueva — lectura de ficheros JSON con
la librería estándar (`json.loads`), mismo nivel de complejidad que el
origen más simple ya construido (016).

**Storage**: `diagnostico.db` existente, **sin migración de esquema**
(research.md §1). Lectura de una única fuente nueva: los 8 ficheros
`<job>.json` de `MONITOR_HEARTBEATS_DIR`. Nunca escritura.

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
007-016 — nuevos casos en `test_evidencia.py` (`_latido_actual()`
contra ficheros de prueba: latido reciente y sano, latido rancio,
fichero ausente ("sin latido"), `job` inexistente entre los 8) y
`test_deepseek.py`.

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007-016.

**Project Type**: Extensión de `src/diagnostico/` ya existente —
ningún paquete nuevo.

**Performance Goals**: Sin cambios — herramienta manual, lectura de
hasta 8 ficheros JSON de pocos cientos de bytes, instantánea.

**Constraints**: Este origen no admite ningún `MOMENTO_ISO` — el
contrato del CLI no expone `--latido-historico` en absoluto (FR-011,
research.md §2), igual que 016.

**Scale/Scope**: Igual que 007-016 — un usuario, uso manual y
esporádico. Sin línea base real ni modo diferido que validar — la
validación de Polish se centra en que el mecanismo en vivo funcione
correctamente contra latidos reales (research.md §2).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que `app.py::get_monitor_heartbeats()` (Frente 1) ya calcula. |
| II. Salud por Resultado | Sí, por diseño | Reutiliza el mismo cálculo de `ok` (antigüedad del latido vs. umbral propio del job) que ya usa el dashboard, nunca recalculado con otra lógica — el prompt se lo dice explícitamente al modelo (research.md §4). |
| III. Estado Esperado Declarado | No aplica | El estado esperado (umbral de antigüedad máxima por job) ya lo declara `app.py::MONITOR_JOBS`, este feature solo lo replica como constante de solo lectura. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007-016. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre ningún monitor en este feature — solo lectura. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca actúa sobre un monitor (no lo relanza) — solo lectura de ficheros ya escritos por `heartbeat.py`. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007-016, ahora también para episodios de latido. |
| IX. Mejora Medida Contra la Línea Base | Sí, sin línea base real (mismo tipo de limitación aceptada que 009/010/011/015/016) | Sin ningún episodio real de "latido rancio" conocido en el momento de validar — se documenta, no se inventa. |
| X. Local por Defecto | Sí, sin dato nuevo | `job`/`epoch`/`detail` son metadatos de tareas del propio Mac — misma naturaleza que datos ya aceptados desde 007. |
| XI. Reproducibilidad Diferida | **Parcial, documentado explícitamente** — igual que 016 | Se cumple para el episodio ya congelado (SC-001) — diagnosticar dos veces el mismo snapshot da la misma conclusión. **No** se cumple en el sentido de "señalar un momento pasado distinto": no existe ninguna evidencia histórica real que consultar (research.md §2) — limitación real de los datos disponibles, no una decisión de diseño evitable. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | Cierra el décimo y último mecanismo relacionado con la Central de Alarmas que quedaba pendiente explícitamente desde 016 (FR-010 de 016). FR-010 de este feature excluye explícitamente corregir la inconsistencia real entre `MONITOR_JOBS` y `DEFAULT_MANIFEST` — defecto del homelab, no de este proyecto (research.md §3). |

**Resultado**: PASS, con la misma excepción documentada explícitamente
que en 016 (Principio XI, parcial) — segunda vez en el proyecto que un
principio "DEBE" no se cumple en su sentido literal completo para un
origen, justificado por una limitación real y verificada de los datos
disponibles, no evitada por conveniencia.

## Project Structure

### Documentation (this feature)

```text
specs/017-diagnostico-latidos/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md             # Contrato del CLI generalizado — supersede
│                            # la parte de `congelar` de
│                            # specs/016-diagnostico-agentes/contracts/cli.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado por 009-016 y ahora por 017 — mismo paquete
├── __init__.py
├── cli.py                # + flag --latido-vivo JOB (sin --latido-historico, FR-011)
├── model.py                # SIN CAMBIOS de esquema — `origen` ya admite 'latido' (TEXT libre desde 009);
│                             # solo se actualiza el docstring de Episodio
├── evidencia.py             # + congelar_latido_vivo, + _latido_actual (lee <job>.json de MONITOR_HEARTBEATS_DIR)
├── deepseek.py                # + _PROMPT_CLAUSULA_LATIDO_ESTADO (mismo patrón que _PROMPT_CLAUSULA_HA_ESTADO)
├── gasto.py                    # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                     # SIN CAMBIOS — sin migración de esquema
└── _homelab_bridge.py            # SIN CAMBIOS — este feature no puentea ningún script

tests/selftest/
├── test_evidencia.py       # + casos de _latido_actual, congelar_latido_vivo
├── test_deepseek.py         # + caso de prompt para origen="latido"
└── (test_store.py, test_gasto.py — SIN CAMBIOS)
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — mismo razonamiento que 009-016. Estructuralmente
casi idéntico a 016: una sola función de evidencia, un solo modo, sin
ninguna infraestructura de subprocesos, husos horarios, ni consultas
externas — la única diferencia real es que aquí sí hay un veredicto
`ok` ya calculado que replicar (como en HA/010), mientras que 016 no lo
tenía.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS, con la excepción de Principio XI documentada explícitamente arriba).*
