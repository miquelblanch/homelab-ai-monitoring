# Implementation Plan: Remediación Automática — Primera Pieza (Rotación de Logs)

**Branch**: `019-remediacion-automatica` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-remediacion-automatica/spec.md`

## Summary

Primera pieza del Frente 2 que estaba sin empezar: un paquete nuevo
`src/remediacion/`, independiente de `src/diagnostico/`, con un único
tipo de acción cerrado (`rotar_log`) y un interruptor manual/automático
por tipo de acción que Miquel controla desde el CLI, con historial
visible y sin ninguna condición previa más que su propia decisión
(FR-001 a FR-004). La condición se evalúa de forma determinista
(tamaño de fichero por encima de un umbral) sobre una lista cerrada de
2 logs reales, sin pasar por el motor DeepSeek — no hay hoy ningún
`causa_probable` real contra el que validar esa vía (research.md §1,
BRIEFING.md "Feature 019"). Toda rotación es reversible sin pérdida de
datos (FR-009/FR-010): renombra, nunca trunca ni borra, y deshacer
nunca sobreescribe lo escrito después de la rotación.

## Technical Context

**Language/Version**: Python 3.11 (mismo runtime que `src/diagnostico/` y `src/inventory/`)

**Primary Dependencies**: Ninguna nueva — `sqlite3`, `pathlib`, `os` de
la librería estándar. Sin llamada a ningún LLM (FR-013) — a diferencia
de `src/diagnostico/`, este paquete no usa `urllib`/DeepSeek.

**Storage**: Base nueva, `remediacion.db` (mismo patrón sqlite que
`diagnostico.db`, ubicación configurable vía variable de entorno,
por defecto junto a `diagnostico.db`). Dos tablas:
`configuracion_accion` (modo por tipo de acción) e
`intentos_remediacion` (historial). Sin relación de esquema con
`diagnostico.db` — paquetes independientes (research.md §2).

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
`diagnostico`/`inventory` — logs de prueba en un directorio temporal,
nunca los reales de `~/Library/Logs/`. La validación en vivo final sí
opera sobre los logs reales (`quickstart.md`), con copia de seguridad
antes de cada paso irreversible-si-algo-fallara.

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — mismo target que el resto del repo. `rotar_log` actúa sobre
`~/Library/Logs/`, fuera de `/Volumes/FastData/`, primera vez que este
repo toca esa ruta.

**Project Type**: Paquete nuevo en `src/` — primer paquete del
Frente 2 de remediación, junto a `inventory` (Frente 1) y
`diagnostico` (Frente 2, diagnóstico).

**Performance Goals**: Sin objetivo nuevo — herramienta manual, opera
sobre 2 ficheros como mucho, instantánea.

**Constraints**: Cero pérdida de datos en ninguna rotación ni en
ningún deshacer (FR-009/FR-010, SC-003/SC-004) — la propiedad de
diseño más importante de esta feature, verificada explícitamente en
`research.md §4`. Ningún tipo de acción empieza en automático
(FR-002). Ninguna acción sobre un componente crítico (FR-012). Ninguna
notificación ni superficie de dashboard (FR-014).

**Scale/Scope**: Un usuario (Miquel), uso manual y esporádico —
mismo perfil que `diagnostico.cli`. Un único tipo de acción, 2 logs
reales vigilados.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — actúa sobre una condición que él mismo comprueba, no sobre una alarma ya calculada por otro origen. |
| II. Salud por Resultado | No aplica | No declara salud de ningún componente. |
| III. Estado Esperado Declarado | Sí | El umbral de tamaño por log ES el estado esperado declarado para este origen nuevo — research.md §3. |
| IV. Diagnóstico Previo a la Acción | Sí, en el sentido genérico del principio, no el del artefacto `Diagnostico` de 007-017 | "Ninguna acción sin un diagnóstico que la justifique" se cumple aquí con una causa conocida y verificada en el momento (el fichero supera el umbral porque nada lo rota) — comprobación determinista, no una hipótesis de IA. Distinción documentada explícitamente (research.md §1) porque este proyecto usa "diagnóstico" en dos sentidos y hoy no hay ningún `causa_probable` real del motor DeepSeek con el que validar la otra vía — mismo tipo de aclaración ya hecha para el Principio XI en 016. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, es el núcleo del feature | Un único tipo de acción (`rotar_log`), declarado aquí, sobre una lista cerrada de 2 logs — ninguna ejecución sobre nada fuera de esa lista (FR-005). |
| VI. Reversibilidad Escrita | Sí, es el núcleo del feature | Rollback escrito y verificado antes de implementar (research.md §4): renombrar, nunca truncar ni borrar; deshacer nunca sobreescribe lo escrito después de la rotación. |
| VII. Un Actor por Acción | Sí | Este feature no toca nada que ya remedie otro componente — `docker_monitor.py` sigue remediando contenedores, sin relación con `rotar_log`. El cambio de modo es siempre decisión de Miquel, nunca autopromovido (FR-003, spec.md User Story 3). |
| VIII. Registro de Acciones e Hipótesis | Sí, extendido de hipótesis a acciones | Cada propuesta y cada ejecución se registra con su desenlace real (FR-011) — mismo espíritu que `diagnostico.db`, ahora para acciones ejecutadas de verdad, no solo hipótesis formuladas. |
| IX. Mejora Medida Contra la Línea Base | Sí, sin línea base real (mismo tipo de limitación aceptada que 009/010/011/015/016/017) | Sin ningún intento de remediación real anterior — se documenta, no se inventa. |
| X. Local por Defecto | Sí | Nombres de fichero y tamaños del propio Mac — misma naturaleza que datos ya aceptados desde 007. |
| XI. Reproducibilidad Diferida | No aplica de la misma forma que en `diagnostico` | Este paquete no "diagnostica episodios" — evalúa una condición actual y actúa. No hay modo diferido que ofrecer ni que echar en falta. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-014: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí, con un alcance explícitamente mínimo | Un único tipo de acción de los varios candidatos del barrido de agosto (research.md §5) — el resto queda fuera, documentado, no olvidado. |
| Modelo Operacional B | Sí, generalizado explícitamente | El modelo ya distinguía "autónomo en la lista cerrada" de "todo lo demás espera aprobación" — este feature añade que **estar en la lista cerrada no basta por sí solo**: cada tipo de acción, aunque esté en la lista, empieza en modo manual (propuesta) hasta que Miquel decide activarlo (FR-002/FR-003). Aclaración de Modelo B, no una contradicción — documentada en research.md §1. |

**Resultado**: PASS, con dos aclaraciones de principios existentes
documentadas explícitamente (Principio IV, sentido genérico vs.
artefacto de 007-017; Modelo B, la lista cerrada es necesaria pero no
suficiente para actuar sola) — mismo criterio de honestidad ya
aplicado a Principio XI en 016.

## Project Structure

### Documentation (this feature)

```text
specs/019-remediacion-automatica/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md              # Contrato del CLI nuevo — remediacion.cli
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/remediacion/          # paquete NUEVO — primera pieza del Frente 2 de remediación
├── __init__.py             # docstring del módulo
├── model.py                 # ConfiguracionAccion, IntentoRemediacion; MODOS, ESTADOS
├── store.py                   # persistencia sqlite en remediacion.db
├── acciones.py                  # comprobar/ejecutar/deshacer rotar_log — lista cerrada de logs
└── cli.py                        # comprobar · pendientes · aprobar · rechazar · modo · historial · deshacer · --selftest

tests/selftest/
├── test_remediacion_store.py     # persistencia, migraciones, historial
├── test_remediacion_acciones.py  # comprobar/ejecutar/deshacer contra logs de prueba (nunca los reales)
└── (test_evidencia.py, test_deepseek.py — SIN CAMBIOS, paquete independiente)
```

**Structure Decision**: paquete nuevo, hermano de `diagnostico` e
`inventory`, sin dependencia de ninguno de los dos (research.md §2) —
mismo patrón de aislamiento que ya separa `inventory` de `diagnostico`
desde el principio del proyecto.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS, con dos aclaraciones de principios existentes documentadas explícitamente arriba).*
