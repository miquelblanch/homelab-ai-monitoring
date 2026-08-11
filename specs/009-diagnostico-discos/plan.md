# Implementation Plan: Generalizar el Diagnóstico a Discos

**Branch**: `009-diagnostico-discos` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-diagnostico-discos/spec.md`

## Summary

Generalizar `src/diagnostico/` (feature 007) para que un `Episodio` pueda
ser de un disco además de un contenedor: nuevo campo `origen`
(`"contenedor"` / `"disco"`), `contenedor` renombrado a `componente`
(genérico), dos funciones nuevas de evidencia (`congelar_disco_vivo`/
`congelar_disco_historico` en `evidencia.py`, reutilizando `disk_metrics`
igual que ya hace `disk_metrics_near()`), dos flags nuevos en `cli.py`
(`congelar --disco-vivo`/`--disco-historico`), y el prompt de DeepSeek
generalizado para no asumir "contenedor Docker" como único tipo de
episodio. El gasto diario sigue siendo un único acumulado compartido
(FR-007) — `gasto.py` no cambia. Migración de esquema idempotente sobre
`diagnostico.db` real (14 episodios ya persistidos por 007).

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a 007)

**Primary Dependencies**: Ninguna nueva — mismo criterio de cero
dependencias que 007.

**Storage**: `diagnostico.db` existente, con una migración de esquema
(`episodios.contenedor` → `episodios.componente` + `episodios.origen`
nuevo, con default `'contenedor'` para no invalidar las 14 filas reales
ya escritas por 007). Lectura de `homelab.db.disk_metrics` (ya usada
parcialmente por `evidencia.py::disk_metrics_near()`), nunca escritura.

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por 007
— nuevos casos para `evidencia.py` (congelar disco) y para el prompt
generalizado, sin llamada real a DeepSeek en el selftest (igual que
007).

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007 (FR-015 de 007 sigue vigente: nada
se dispara solo).

**Project Type**: Extensión de `src/diagnostico/` ya existente — ningún
paquete nuevo.

**Performance Goals**: Sin cambios respecto a 007 — herramienta manual,
no un monitor periódico.

**Constraints**: La migración de esquema DEBE ser idempotente y segura
sobre datos reales ya persistidos (14 episodios de 007) — nunca destruir
ni reinterpretar mal una fila existente. El riesgo de escritura fallida
al diagnosticar el propio disco que aloja `diagnostico.db` se acepta tal
cual (spec.md, Clarifications) — no exige ningún mecanismo nuevo.

**Scale/Scope**: Igual que 007 — un usuario, uso manual y esporádico.
Sin corpus histórico real de incidentes de disco (spec.md, Assumptions)
— la validación se apoya en `--disco-vivo` contra los 3 discos reales.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que la Central de Alarmas (006) ya calcula para discos (`disco_aviso`/`disco_critico`). |
| II. Salud por Resultado | No aplica | Sin cambios respecto a 007. |
| III. Estado Esperado Declarado | No aplica | Sin cambios respecto a 007. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre discos en este feature. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca actúa sobre ningún disco (liberar espacio, borrar ficheros...) — solo lectura. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007, ahora también para episodios de disco. |
| IX. Mejora Medida Contra la Línea Base | Parcial, limitación reconocida | No existe línea base real de incidentes de disco (spec.md, Assumptions) — la validación es contra el estado sano actual, no contra un corpus histórico como el de `beszel`. Documentado como limitación, no ocultado. |
| X. Local por Defecto | Sí, misma justificación que 007 | La evidencia de disco (uso, no contenido de ficheros) sale hacia DeepSeek con la misma justificación ya aceptada para contenedores. |
| XI. Reproducibilidad Diferida | Sí | FR-002: mismo mecanismo de snapshot congelado, ahora también para discos — `--disco-historico` reproduce un momento pasado igual que `--historico` ya hace para contenedores. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Parcial, a propósito | FR-010 acota el alcance a contenedores (ya cubierto) + discos — generalizar a los otros 7 orígenes queda para features posteriores, decisión explícita documentada en `BRIEFING.md` tras investigar qué orígenes tienen evidencia real disponible. |

**Resultado**: PASS. El único riesgo real es el Principio IX (sin línea
base histórica) — aceptado explícitamente como limitación conocida del
feature, no una laguna sin analizar.

## Project Structure

### Documentation (this feature)

```text
specs/009-diagnostico-discos/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md            # Contrato del CLI generalizado — supersede
│                          # la parte de `congelar` de specs/007-.../contracts/cli.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado — mismo paquete, sin nuevo paquete hermano
├── __init__.py
├── cli.py                # + flags --disco-vivo/--disco-historico
├── model.py               # Episodio: contenedor → componente, + campo origen
├── evidencia.py            # + congelar_disco_vivo/congelar_disco_historico,
│                            # + disk_metrics_window/disk_metrics_recientes
├── deepseek.py              # prompt generalizado (ya no asume "contenedor Docker")
├── gasto.py                 # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                  # + migración idempotente de esquema (origen/componente)
└── _homelab_bridge.py         # SIN CAMBIOS

tests/selftest/
├── test_evidencia.py       # + casos de congelar_disco_vivo/historico
├── test_deepseek.py         # + caso de prompt para origen="disco"
├── test_store.py             # + caso de migración idempotente
└── test_gasto.py              # SIN CAMBIOS
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — no se crea un paquete hermano nuevo. A
diferencia de la relación entre `inventory/` y `diagnostico/`
(research.md §7 de 007, dos features independientes que comparten
convención, no código), aquí discos y contenedores SON el mismo
concepto (un episodio, cualquiera que sea su origen) — separarlos en
paquetes distintos duplicaría el motor de hipótesis, el gasto diario y
la persistencia sin ninguna ganancia real.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
