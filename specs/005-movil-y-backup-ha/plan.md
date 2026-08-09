# Implementation Plan: Metadatos de Móvil Fuera de Alcance y Backup Propio de HA

**Branch**: `005-movil-y-backup-ha` | **Date**: 2026-08-09 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-movil-y-backup-ha/spec.md`

## Summary

Dos piezas pequeñas sobre el mecanismo que 004 ya dejó construido: (1)
`is_intentional()` gana una tercera condición barata —
`platform: mobile_app`, dato ya disponible desde feature 001, cero
lectura nueva— para las 53 entidades de la app móvil; (2) un tipo de
check nuevo en `ha_monitor.py` (`entity_age_below`) para vigilar la
antigüedad de la última copia correcta del backup propio de HA. La
novedad frente a 004: ninguna de las dos piezas toca `evaluate.py` más
allá de una condición — el modelo de `esta_vigilado`/`condicion_
incumplida` que 004 dejó ya es lo bastante general para aceptar un tipo
de check nuevo sin cambios adicionales en este repo.

## Technical Context

**Language/Version**: Python 3.11 (script privado `ha_monitor.py`) +
Python de este repo (`src/inventory/`) — mismos lenguajes que ya usa
cada fichero.

**Primary Dependencies**: Solo librería estándar — `datetime` (ya
importado en `ha_monitor.py`) para interpretar la fecha ISO 8601 del
backup. Sin credenciales nuevas.

**Storage**: `ha_monitor_state.json` (ya existe, feature 004) con una
clave nueva, mismo esquema — sin fichero nuevo.

**Testing**: Sin test automático nuevo para `ha_monitor.py` (mismo
patrón que el resto de monitores del homelab); `test_evaluate.py`/
`inventory.cli --selftest` de este repo no necesitan casos nuevos —
la condición de `is_intentional()` y el tipo de check nuevo no cambian
ninguna función que ya tenga aserciones propias más allá de las que ya
cubre 004 de forma genérica. Validación de extremo a extremo con
`quickstart.md`.

**Target Platform**: macOS (LaunchAgent existente de `ha_monitor.py`,
sin cambio de cadencia) + este repo (CLI de inventario, sin servicio
nuevo).

**Project Type**: ampliación de dos ficheros que ya existen — sin
proyecto nuevo.

**Performance Goals**: sin objetivo explícito. El check nuevo es una
consulta HTTP más a la API de HA, mismo orden de magnitud que los 66
checks ya existentes.

**Constraints**: FR-005 — ninguna acción correctiva ni cambio de
configuración de la app móvil, de ningún dispositivo, ni del sistema
de backup de HA. Sin cambios en `app.py` (mismo razonamiento que 004,
`research.md` §4).

**Scale/Scope**: 1 check nuevo en `ha_monitor.py` (67 en total), 1
condición nueva en `is_intentional()` — mismo orden de magnitud que el
resto del fichero.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Repasado principio por principio contra `.specify/memory/constitution.md`
v1.2.0. Sin violaciones — no hace falta rellenar Complexity Tracking.

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | Sí | El check nuevo hereda el mismo mecanismo de reemisión de `ha_monitor.py` que ya usan los 66 existentes. |
| II. Salud por Resultado | Sí | `entity_age_below` trata `unavailable`/`unknown` como fallo — un backup sin dato no es un backup sano (FR-004). |
| III. Estado Esperado Declarado | Sí | Declara por primera vez un esperado explícito (antigüedad < 36 h) para el backup propio de HA — antes no tenía ninguno. |
| IV. Diagnóstico Previo a la Acción | N/A | Sin acciones correctivas (FR-005). |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | N/A | Sin acciones — cumplimiento por ausencia. |
| VI. Reversibilidad Escrita | N/A | Sin acciones que revertir. |
| VII. Un Actor por Acción | Sí | Ni la regla de `mobile_app` ni el check de backup reinician ni corrigen nada. |
| VIII. Registro de Acciones e Hipótesis | N/A | No formula hipótesis de causa raíz. |
| IX. Mejora Medida Contra la Línea Base | Sí | `SC-001` se verifica relanzando el inventario — 150 brechas `entidad_ha` deben bajar en al menos 53. |
| X. Local por Defecto | Sí | Sin credenciales nuevas — reutiliza `HA_URL`/`HA_TOKEN` ya existentes. |
| XI. Reproducibilidad Diferida | N/A | No diagnostica incidentes. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí | Sin cambio de duplicado — no se toca `app.py` (`research.md` §4); el recuento agregado ya suma el check nuevo sin ambigüedad. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | Cierra 53 de las 150 brechas restantes, y añade vigilancia real donde no había ninguna (el backup propio de HA), documentando el resto como pendiente explícito. |

## Project Structure

### Documentation (this feature)

```text
specs/005-movil-y-backup-ha/
├── plan.md              # Este fichero (/speckit-plan)
├── research.md          # Fase 0 (/speckit-plan)
├── data-model.md         # Fase 1 (/speckit-plan)
├── quickstart.md         # Fase 1 (/speckit-plan)
├── contracts/             # Fase 1 (/speckit-plan)
│   └── ficheros.md
└── tasks.md               # Fase 2 (/speckit-tasks — no lo crea /speckit-plan)
```

### Source Code (repository root)

Mismo límite de repo que 001-004: `ha_monitor.py` vive fuera de este
repositorio (privado). Dentro de este repo, solo `evaluate.py` cambia
— ni `sources.py`, ni `model.py`, ni `_homelab_bridge.py` necesitan
tocarse (a diferencia de 004, que sí tocó los cuatro).

```text
# Fuera de este repo — /Volumes/FastData/homelab/ (privado)

scripts/
└── ha_monitor.py                      # modificado:
    ├── CHECKS                         #   + 1 entrada entity_age_below
    │                                   #     (backup de HA)
    └── check_status()                 #   + tipo de check nuevo
                                        #     entity_age_below

# Dentro de este repo — src/inventory/ (público)

src/inventory/evaluate.py
└── is_intentional()                   # + condición platform == "mobile_app"
                                        #   (categoría entidad_ha)
```

**Structure Decision**: sin proyecto nuevo, sin script nuevo — una
condición de una línea en una función que ya existe, y un tipo de
check nuevo en el dispatcher que ya existe. El feature más pequeño de
los cuatro implementados hasta ahora, precisamente porque reutiliza el
modelo que 004 dejó general.

## Complexity Tracking

Sin violaciones de la Constitution Check — tabla no aplicable.

## Post-Design Constitution Check

*Re-chequeo tras la Fase 1 (`data-model.md`, `contracts/`,
`quickstart.md`).*

Sin cambios respecto a la tabla de arriba. Una decisión de diseño se
revisó explícitamente y no introduce ninguna violación:

- Que `entity_age_below` reutilice los motivos `no_disponible`/
  `no_numerico`/`umbral` ya existentes en vez de inventar vocabulario
  nuevo no es una pérdida de precisión (Principio XII) — son la misma
  clase de fallo (dato ausente, dato con forma incorrecta, dato fuera
  de umbral) aplicada a un tipo de dato nuevo (fecha en vez de número),
  no un significado distinto disfrazado del mismo texto.

Gate superado. Listo para `/speckit-tasks`.
