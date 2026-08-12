# Implementation Plan: Generalizar el Diagnóstico a los Agentes (LaunchAgents)

**Branch**: `016-diagnostico-agentes` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/016-diagnostico-agentes/spec.md`

## Summary

Generalizar `src/diagnostico/` (007, generalizado a discos en 009, HA
en 010, backups en 011, relays en 012, inventario en 013, hosts
externos en 014 y el hub de Beszel en 015) para que un `Episodio`
pueda ser también de agente (LaunchAgent): un noveno y último valor de
`origen` (`"agente"`, sin migración de esquema). **Único origen del
proyecto sin ningún modo diferido** — la evidencia en vivo lee
`launchagents_raw.txt` (el mismo fichero que ya lee
`app.py::get_launchagents()`, escrito cada 5 min por
`dump_launchagents.sh`) y replica su cálculo exacto de
`running`/`status`; no existe ninguna fuente histórica real que
consultar (research.md §2), así que `congelar` no ofrece ningún flag
`--agente-historico`. Cierra los 9 orígenes de la Central de Alarmas
que este proyecto se propuso generalizar. El gasto diario sigue siendo
un único acumulado compartido (FR-007) — `gasto.py` no cambia.
`store.py` tampoco cambia.

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a 007-015)

**Primary Dependencies**: Ninguna nueva — lectura de un fichero de
texto plano con la librería estándar (`str.split("\t")`), mismo nivel
de complejidad que el origen más simple ya construido.

**Storage**: `diagnostico.db` existente, **sin migración de esquema**
(research.md §1). Lectura de una única fuente nueva:
`launchagents_raw.txt`. Nunca escritura.

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
007-015 — nuevos casos en `test_evidencia.py` (`_agente_actual()`
contra un `launchagents_raw.txt` de prueba: agente en ejecución,
agente inactivo con código de salida normal, agente inactivo con
código de salida anómalo, `label` inexistente) y `test_deepseek.py`.

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007-015.

**Project Type**: Extensión de `src/diagnostico/` ya existente —
ningún paquete nuevo.

**Performance Goals**: Sin cambios — herramienta manual, lectura de un
fichero de texto de ~20-40 KB, instantánea.

**Constraints**: Este origen no admite ningún `MOMENTO_ISO` — el
contrato del CLI no expone `--agente-historico` en absoluto (FR-011,
research.md §2), a diferencia de todos los orígenes anteriores.

**Scale/Scope**: Igual que 007-015 — un usuario, uso manual y
esporádico. Sin línea base real ni modo diferido que validar — la
validación de Polish se centra en que el mecanismo en vivo funcione
correctamente contra agentes reales (research.md §2).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que `app.py::get_launchagents()` (Frente 1) ya calcula. |
| II. Salud por Resultado | Sí, por diseño | Reutiliza el mismo cálculo de `running`/`status` que ya usa el dashboard, nunca recalculado con otra lógica. |
| III. Estado Esperado Declarado | No aplica | El estado esperado (qué significa "sano" para un agente) ya lo declara `get_launchagents()`, este feature solo lo lee. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007-015. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre ningún agente en este feature — solo lectura. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca actúa sobre un agente (no lo reinicia, no lo recarga) — solo lectura de un fichero ya escrito por otro proceso. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007-015, ahora también para episodios de agente. |
| IX. Mejora Medida Contra la Línea Base | Sí, sin línea base real (mismo tipo de limitación aceptada que 009/010/011/015) | Sin ningún episodio real de "agente crasheado" conocido en el momento de validar — se documenta, no se inventa. |
| X. Local por Defecto | Sí, sin dato nuevo | `label`/`pid`/`exit_code` son nombres de proceso y códigos de salida del propio Mac — misma naturaleza que datos ya aceptados desde 007. |
| XI. Reproducibilidad Diferida | **Parcial, documentado explícitamente** | Se cumple para el episodio ya congelado (SC-001) — diagnosticar dos veces el mismo snapshot da la misma conclusión. **No** se cumple en el sentido de "señalar un momento pasado distinto": no existe ninguna evidencia histórica real que consultar (research.md §2) — limitación real de los datos disponibles, no una decisión de diseño evitable. Documentado aquí explícitamente en vez de forzar un mecanismo diferido ficticio o dejarlo sin mencionar. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí, con un límite explícito | FR-010 excluye explícitamente `get_monitor_heartbeats()` — mecanismo relacionado pero distinto, con su propia investigación pendiente si Miquel decide abordarlo en un feature futuro (research.md §1 de `BRIEFING.md`, "Feature 016"). |

**Resultado**: PASS, con una excepción documentada explícitamente
(Principio XI, parcial) — la primera vez en el proyecto que un
principio "DEBE" no se cumple en su sentido literal completo para un
origen, justificado por una limitación real y verificada de los datos
disponibles, no evitada por conveniencia. Mismo criterio de honestidad
ya aplicado a Principio IX en 009/010/011/015.

## Project Structure

### Documentation (this feature)

```text
specs/016-diagnostico-agentes/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md             # Contrato del CLI generalizado — supersede
│                            # la parte de `congelar` de
│                            # specs/015-diagnostico-hub-beszel/contracts/cli.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado por 009-015 y ahora por 016 — mismo paquete
├── __init__.py
├── cli.py                # + flag --agente-vivo LABEL (sin --agente-historico, FR-011)
├── model.py                # SIN CAMBIOS de esquema — `origen` ya admite 'agente' (TEXT libre desde 009);
│                             # solo se actualiza el docstring de Episodio
├── evidencia.py             # + congelar_agente_vivo, + _agente_actual (lee launchagents_raw.txt)
├── deepseek.py                # prompt generalizado una novena y última vez, sin cláusula de contenido nueva
├── gasto.py                    # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                     # SIN CAMBIOS — sin migración de esquema
└── _homelab_bridge.py            # SIN CAMBIOS — este feature no puentea ningún script

tests/selftest/
├── test_evidencia.py       # + casos de _agente_actual, congelar_agente_vivo
├── test_deepseek.py         # + caso de prompt para origen="agente"
└── (test_store.py, test_gasto.py — SIN CAMBIOS)
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — mismo razonamiento que 009-015. Es el feature
más simple de toda la serie: una sola función de evidencia, un solo
modo, sin ninguna infraestructura de subprocesos, husos horarios, ni
consultas externas.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS, con la excepción de Principio XI documentada explícitamente arriba).*
