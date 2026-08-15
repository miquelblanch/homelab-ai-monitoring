# Implementation Plan: Parseo de DeepSeek Compartido y Autocomprobación Sincera

**Branch**: `025-consolidar-parseo-deepseek` | **Date**: 2026-08-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/025-consolidar-parseo-deepseek/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Extraer a una función compartida, `_extraer_contenido_y_tokens()`, el
bloque de extracción de contenido/tokens (con el respaldo
`content`/`reasoning_content`) hoy duplicado entre
`diagnostico/deepseek.py::parsear_respuesta` y
`remediacion/deepseek_contenedores.py::parsear_respuesta_remediacion`.
Vive en `diagnostico/deepseek.py` — `remediacion` ya importa
directamente de ahí (`llamar_deepseek`, autorizado en
specs/021-remediacion-contenedores/research.md §2), así que no abre
ninguna dependencia nueva, solo amplía una ya existente. Además,
corrige el texto de `--help` y el docstring de `_run_selftest()` en
las tres CLIs para que digan la verdad sobre su alcance.

## Technical Context

**Language/Version**: Python 3.11, sin dependencias nuevas.

**Primary Dependencies**: Ninguna — `remediacion/deepseek_contenedores.py` ya importa de `diagnostico.deepseek` indirectamente vía `remediacion/acciones.py`; esta feature añade un segundo nombre importado del mismo módulo, no un paquete nuevo.

**Storage**: N/A.

**Testing**: Mismo runner `tests.selftest`. Ningún test parchea el bloque de extracción directamente (comprobado por grep) — los tests existentes de `test_deepseek.py` y `test_remediacion_deepseek_contenedores.py` llaman a `parsear_respuesta`/`parsear_respuesta_remediacion` como caja negra, así que siguen funcionando sin cambios.

**Target Platform**: Sin cambio.

**Project Type**: Biblioteca/CLI interna.

**Performance Goals**: N/A.

**Constraints**: Cero cambio de comportamiento observable (FR-002, SC-002); `construir_prompt`/`construir_prompt_remediacion` y la validación posterior de cada uno no se tocan (FR-003).

**Scale/Scope**: ~15 líneas de duplicación real consolidadas; 3 ficheros `cli.py` con un texto de ayuda y un docstring corregidos cada uno.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Igual que 023/024: los principios I-IX, XII rigen comportamiento en
vivo del agente — esta feature no los toca. Ningún principio de la
constitución exige verificación adicional aquí: no hay alarmas,
acciones, ni dashboard involucrados, solo una función interna de
parseo y texto de ayuda de CLI.

**Resultado: PASS, sin excepciones que registrar en Complexity Tracking.**

## Project Structure

### Documentation (this feature)

```text
specs/025-consolidar-parseo-deepseek/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md
```

### Source Code (repository root)

```text
src/diagnostico/deepseek.py
├── _extraer_contenido_y_tokens(respuesta) -> tuple[dict, int, int]  # NUEVA
│                                                                     # función privada, extrae
│                                                                     # {content|reasoning_content}
│                                                                     # + usage; lanza si la forma
│                                                                     # es inesperada, el llamador decide
└── parsear_respuesta(respuesta)  # usa la función de arriba, resto sin cambios

src/remediacion/deepseek_contenedores.py
└── parsear_respuesta_remediacion(respuesta)  # importa
                                               # diagnostico.deepseek._extraer_contenido_y_tokens,
                                               # resto sin cambios

src/diagnostico/cli.py       # texto de --help y docstring de _run_selftest() corregidos
src/inventory/cli.py         # ídem
src/remediacion/cli.py       # ídem (añade el docstring que hoy no tiene)
```

**Structure Decision**: Sin módulo nuevo — `_extraer_contenido_y_tokens`
vive en `diagnostico/deepseek.py`, no en un fichero compartido aparte.
A diferencia de 023/024, aquí no hace falta un módulo neutral: la
dependencia `remediacion → diagnostico` ya existe y ya está autorizada
(specs/021/research.md §2); añadir un nombre más a un import que ya
existe no es una decisión de arquitectura nueva, solo aplicar el
patrón ya sentado.

## Complexity Tracking

*No aplica — el Constitution Check no encontró violaciones que justificar.*
