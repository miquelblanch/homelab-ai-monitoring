# Implementation Plan: Clasificación de Remediación en Inventario, con DeepSeek Evaluando también Contenedores Críticos

**Branch**: `022-clasificacion-remediacion` | **Date**: 2026-08-14 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-clasificacion-remediacion/spec.md`

## Summary

Dos piezas, construidas sobre lo que ya existe (019/020/021), sin
crear ningún paquete ni tabla nueva:

1. **Extender `comprobar_reiniciar_contenedor()`** (`src/remediacion/acciones.py`)
   para que también evalúe los 12 contenedores críticos —hoy
   excluidos por completo (FR-006 de 021)— con una diferencia
   estructural, no de configuración: para un contenedor crítico, el
   modo es siempre `"manual"`, impuesto en código, nunca leído de
   `configuracion_contenedor` ni cambiable por CLI. `NEVER_RESTART`
   (`frigate`) sigue totalmente excluido, sin cambios.
2. **Ampliar `escribir_snapshot()`** con un bloque `contenedores[]`
   —clasificación derivada (Manual/Automática/IA) y el intento
   vigente si lo hay, por contenedor— para que el dashboard (repo
   privado, fuera de este repositorio) pueda pintar la columna de
   Inventario y el estado real en Alarmas sin montar `remediacion.db`
   directamente — mismo patrón ya usado para los logs desde 020.

La clasificación en sí (Manual/Automática/IA) es una función pura,
sin estado propio: se deriva en el momento de generar el snapshot a
partir de `configuracion_accion`/`configuracion_contenedor` y de
`docker_critical()`/`docker_never_restart()`, ya existentes — no hay
ninguna tabla ni campo nuevo que la persista de forma independiente
(FR-002).

## Technical Context

**Language/Version**: Python 3.11 (mismo runtime que el resto del repo).

**Primary Dependencies**: Ninguna nueva. Reutiliza `sqlite3`,
`pathlib`, `json` de la librería estándar, y las mismas tres
importaciones ya aceptadas de `diagnostico` desde 021
(`evidencia.congelar_vivo`, `deepseek.llamar_deepseek`, `gasto`) — sin
ampliar esa lista.

**Storage**: `remediacion.db` (ya existente) — **sin tablas nuevas**.
`configuracion_contenedor` e `intentos_reinicio` (021) se reutilizan
tal cual; la única diferencia de comportamiento es que ahora también
reciben filas para contenedores críticos, con la salvedad de que
`configuracion_contenedor.modo` para un crítico nunca se consulta al
decidir ejecución (siempre forzado a `"manual"` en código — ver
Constitution Check, Principio VII) ni se deja escribir como
`"automatico"` (guarda nueva en `store.set_modo_contenedor`).

**Testing**: `tests/selftest/`, mismo runner. Casos nuevos:
`comprobar_reiniciar_contenedor` con un crítico caído (debe crear
`pendiente`, nunca ejecutar), intento de fijar modo automático sobre
un crítico (debe rechazarse), `escribir_snapshot` con contenedores
críticos y no críticos mezclados. DeepSeek y `restart_container`
siempre mockeados, mismo principio que 021.

**Target Platform**: macOS (Mac Mini M4 Pro), igual que el resto del
repo.

**Project Type**: Extensión de `src/remediacion/` (paquete ya
existente) — no se crea ningún paquete nuevo. Los cambios de interfaz
(columna en Inventario, estado en Alarmas) viven en el dashboard
privado (`homelab-dashboard/scripts/app.py`, fuera de este
repositorio) — mismo patrón que 019/020/021, documentado aquí pero no
versionado en este repo público.

**Performance Goals**: Sin objetivo nuevo — la evaluación de críticos
añade como mucho 12 contenedores a un bucle que ya recorre 39 cada 5
min.

**Constraints**: Ningún contenedor crítico puede tener nunca modo
`"automatico"` ni ejecutarse sin aprobación explícita de Miquel ese
mismo día (FR-008, NO NEGOCIABLE — Principio VII enmendado). `frigate`
(`NEVER_RESTART`) sigue excluido de cualquier evaluación (FR-007). El
gasto de DeepSeek para críticos cuenta contra el mismo presupuesto
diario que ya comparten diagnóstico (007) y remediación de no críticos
(021) — sin límite aparte (FR-015).

**Scale/Scope**: 12 contenedores críticos añadidos a la población ya
evaluada (26 no críticos, sin cambios) — 38 contenedores en total con
alguna forma de evaluación; el resto de categorías del inventario
(cientos de componentes) solo ganan una etiqueta derivada, sin
evaluación de ningún tipo.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | Sí, vía `docker_monitor.py`, no vía `remediacion` | La persistencia de la alerta sobre un crítico caído la sigue garantizando el aviso ya existente de `docker_monitor.py` ("contenedor crítico caído", sin ningún cambio de este feature) — no un aviso nuevo o reutilizado dentro de `remediacion`. Comprobado contra el código real: `acciones.py` no notifica nada al crear un intento `pendiente` (solo `_notificar_fallo_automatico`/`_notificar_sin_accion`/`_notificar_cortacircuito`/`_notificar_sin_evaluar_persistente`, ninguna en la creación de `pendiente`). **Importante para quien implemente**: no añadir aquí un aviso nuevo de "propuesta pendiente" pensando que hace falta para este principio — haría que dos actores avisaran sobre el mismo crítico caído, violando el propio Principio VII (un único actor, `docker_monitor.py`, vigila y avisa de críticos). Corregido en esta fila tras `/speckit-analyze` (hallazgo F2, 2026-08-14) — la redacción anterior atribuía la garantía a "el mismo mecanismo que 021", inexacto. |
| II. Salud por Resultado | Sí | Sin cambios respecto a 021 — un reinicio (crítico o no) se verifica contra `running` real, nunca contra el código de salida. |
| III. Estado Esperado Declarado | Sí | `running and healthy` sigue siendo el estado esperado; sin cambios. |
| IV. Diagnóstico Previo a la Acción | Sí, mismo matiz que 021 | DeepSeek evalúa evidencia real de cada contenedor crítico antes de proponer — nunca una condición ciega. Mismo alcance limitado ya documentado en 021 (pregunta "¿aplica esta acción?", no "causa probable" formal). |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí | Ninguna acción nueva — sigue siendo `reiniciar_contenedor`/`rotar_log`, las mismas dos de 019/021. Ampliar la *población* evaluada no amplía la *lista* de acciones. |
| VI. Reversibilidad Escrita | Igual que 021, documentado | Un reinicio de crítico tiene la misma falta de rollback real que uno no crítico (FR-016 de 021) — sin excepción nueva que declarar. |
| VII. Un Actor por Acción | Sí, tras la enmienda de esta sesión (constitution.md v2.1.0) | `docker_monitor.py` sigue siendo, sin ningún cambio, el único actor de vigilancia y aviso de los críticos. `remediacion`/DeepSeek asume una responsabilidad distinta y nueva —analizar y proponer, nunca ejecutar sin aprobación— que el principio enmendado reconoce explícitamente como no competitiva. La garantía NO NEGOCIABLE (ningún crítico se reinicia sin aprobación explícita) se refuerza en código con una guarda estructural: `configuracion_contenedor.modo` nunca se lee para un contenedor de `docker_critical()`, y `store.set_modo_contenedor()` rechaza `"automatico"` para uno — dos capas, no una sola. |
| VIII. Registro de Acciones e Hipótesis | Sí | Cada evaluación sobre un crítico (con o sin acción recomendada) se registra en `intentos_reinicio` igual que para no críticos — mismo mecanismo, población ampliada. |
| IX. Mejora Medida Contra la Línea Base | No aplica nueva línea base | Sin línea base propia para "evaluación de críticos" — no existía nada equivalente antes de esta feature con lo que comparar. |
| X. Local por Defecto | Sí, extensión de una justificación ya aceptada | Enviar evidencia de un contenedor crítico a la API de DeepSeek es la misma naturaleza de dato ya justificada para no críticos (021) y diagnóstico (007) — mismo proveedor, misma justificación, población ampliada. |
| XI. Reproducibilidad Diferida | No aplica | Evaluación en vivo únicamente, mismo criterio que 021. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí, indirectamente | La columna de Inventario y el estado en Alarmas no calculan ninguna alarma nueva (FR-014) — leen configuración y estado ya calculados; no hay riesgo de duplicado/ausencia nuevo introducido por este plan. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | La clasificación cubre el 100% del inventario (FR-001/SC-002), no una selección — para las categorías sin acción real, es honesta ("Manual") en vez de omitir la columna. |
| Modelo Operacional B | Sí, reforzado para críticos | Para un contenedor crítico, el modelo B se aplica sin la vía "autónoma": toda acción reversible y de bajo riesgo sigue permitiendo autonomía solo para no críticos; un crítico es, por definición de este plan, siempre "espera aprobación humana explícita" — sin excepción posible. |

**Resultado**: PASS. Ninguna violación nueva — la única pieza que
podría parecer una (extender DeepSeek a críticos) queda cubierta por
la enmienda ya ratificada de Principio VII (constitution.md v2.1.0),
con dos guardas estructurales en código (no solo en configuración) que
sostienen la garantía NO NEGOCIABLE. Sin excepciones que registrar en
Complexity Tracking más allá de las dos ya heredadas y documentadas de
021 (reversibilidad de un reinicio, e importar de `diagnostico`) — no
se reabren aquí porque este plan no cambia esa relación, solo amplía
la población sobre la que ya se aplica.

**Re-chequeo tras Fase 1** (research.md, data-model.md,
contracts/cli.md, quickstart.md): **PASS confirmado.** El diseño
concreto no introduce ninguna tabla, campo persistido o dependencia
que no estuviera ya prevista arriba; la guarda de `set_modo_contenedor`
(research.md §2) y el forzado de modo en `evaluar_contenedor`
(research.md §1) son las dos únicas piezas de código nuevas que tocan
la garantía NO NEGOCIABLE, y ambas están descritas explícitamente en
la fila VII de la tabla.

**Re-chequeo tras `/speckit-tasks` + `/speckit-analyze`** (2026-08-14):
**PASS confirmado, sin violación de constitución** — `/speckit-analyze`
no encontró ningún incumplimiento de un principio MUST. Sí encontró
que la fila I de esta tabla justificaba mal *cómo* se cumple (hallazgo
F2): decía que la persistencia de la alerta la daba "el mismo
mecanismo que 021" dentro de `remediacion`, cuando en realidad la da
el aviso ya existente de `docker_monitor.py`, ajeno a este feature —
corregido directamente en la fila I. Riesgo real que evita la
corrección: sin ella, alguien podría implementar T012 añadiendo un
aviso nuevo de "propuesta pendiente" en `remediacion` creyendo que
hace falta para Principio I, y crear sin querer un segundo actor
avisando del mismo crítico caído — violación de Principio VII. Los
otros 4 hallazgos (F1, E1, C1, E2) son de trazabilidad/cobertura, sin
relación con la constitución — ver `tasks.md`, `data-model.md` y
`contracts/cli.md` para sus correcciones.

## Project Structure

### Documentation (this feature)

```text
specs/022-clasificacion-remediacion/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md          # Phase 1 output
├── contracts/               # Phase 1 output
│   └── cli.md                  # Extensión del contrato de remediacion.cli + snapshot JSON
└── tasks.md                      # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/remediacion/                       # paquete YA EXISTENTE (019/021) — se extiende, no se crea
├── acciones.py                           # comprobar_reiniciar_contenedor(): ya no excluye críticos,
│                                            los evalúa con modo forzado "manual" (nueva rama, misma
│                                            función evaluar_contenedor(), sin duplicar lógica);
│                                            escribir_snapshot(): + bloque contenedores[] (clasificación
│                                            derivada + intento vigente por contenedor)
├── clasificacion.py                      # NUEVO — módulo pequeño y puro: clasificar_contenedor(),
│                                            clasificar_log(); sin estado propio, sin I/O (FR-002)
├── store.py                              # set_modo_contenedor(): + guarda que rechaza "automatico"
│                                            para un contenedor de docker_critical()
├── _homelab_bridge.py                    # docker_critical(): + REMEDIACION_TEST_FORZAR_CRITICO
│                                            (hook de pruebas, research.md §1b) — docker_never_restart()
│                                            sin cambios, ambos ya expuestos desde 021
└── cli.py                                # contenedores: + flag --incluir-criticos; modo-contenedor:
                                             mensaje de error legible cuando la guarda de store.py (T003)
                                             rechaza un crítico (contracts/cli.md) — añadido tras
                                             /speckit-analyze (hallazgo F1, 2026-08-14): faltaba en la
                                             primera versión de este árbol pese a que contracts/cli.md
                                             y tasks.md (T015) ya lo tocaban

tests/selftest/
├── test_remediacion_clasificacion.py     # NUEVO — clasificacion.py, función pura, casos de tabla
├── test_remediacion_acciones.py          # + comprobar_reiniciar_contenedor con crítico caído,
│                                            escribir_snapshot con bloque contenedores[]
├── test_remediacion_store.py             # + guarda de set_modo_contenedor sobre un crítico,
│                                            + intento_reinicio_vigente con la ventana configurable
└── test_remediacion_cli.py               # NUEVO para 022 — --incluir-criticos, mensaje de error de
                                             modo-contenedor sobre un crítico (hallazgo E1, 2026-08-14)

# Fuera de este repositorio (dashboard privado, mismo patrón que 019/020/021):
# homelab-dashboard/scripts/app.py — columna "remediación" en la pestaña Inventario
# (join entre get_inventory() y el nuevo bloque contenedores[]/logs[] del snapshot,
# con "Manual" por defecto para toda categoría sin ese bloque) y estado real de
# remediación en la pestaña Alarmas para contenedor_caido/contenedor_caido_critico
# y las alarmas de log — sin tocar ALARM_TYPES (006) ni la pestaña Correcciones
# (008/021), que es un mecanismo distinto (historial de alarmas YA resueltas,
# no clasificación prospectiva ni estado de una propuesta pendiente).
```

**Structure Decision**: extiende `src/remediacion/` — un módulo nuevo,
pequeño y puro (`clasificacion.py`), cero tablas nuevas, cero paquetes
nuevos. El trabajo de interfaz (columna de Inventario, estado en
Alarmas) es responsabilidad del dashboard privado, fuera de este
repositorio — documentado en `contracts/cli.md` (forma del JSON que
consume) y en `research.md`, no implementado aquí.

## Complexity Tracking

*Sin violaciones nuevas que justificar — ver "Resultado" del
Constitution Check. Las dos excepciones ya conocidas (reversibilidad
de un reinicio; import de `diagnostico` desde `remediacion`) se
heredan de 021 sin cambios y no se repiten aquí.*
