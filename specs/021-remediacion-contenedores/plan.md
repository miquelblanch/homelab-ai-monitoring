# Implementation Plan: Remediación Asistida por DeepSeek — Contenedores

**Branch**: `021-remediacion-contenedores` | **Date**: 2026-08-13 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-remediacion-contenedores/spec.md`

## Summary

Sustituye la condición fija que se había especificado inicialmente
("contenedor no crítico caído → reinicia") por una decisión real:
para cada contenedor no crítico caído, el sistema reúne su evidencia
(reutilizando `diagnostico.evidencia.congelar_vivo()`, no una copia
nueva) y le pregunta a DeepSeek si `reiniciar_contenedor` —la única
acción de la lista cerrada aplicable a este origen— resuelve el caso.
En modo manual, esa recomendación se propone para aprobación; en
automático, se ejecuta directo, reutilizando la lógica de reinicio ya
probada de `docker_monitor.py` (verificación real post-reinicio,
cortacircuito de 3/6h) en vez de reimplementarla. `docker_monitor.py`
deja de decidir reinicios por su cuenta, pero sigue siendo la fuente
de esas funciones — no se duplican. `restart_history` queda congelada
como histórico previo al corte; los intentos nuevos viven en
`remediacion.db`. Los 12 contenedores críticos y `frigate` quedan
fuera de cualquier vía, incluida la pregunta a DeepSeek.

## Technical Context

**Language/Version**: Python 3.11 (mismo runtime que el resto del repo).

**Primary Dependencies**: `sqlite3`, `pathlib`, `urllib` de la
librería estándar. **Primera vez que `remediacion` importa de
`diagnostico`** — ver Constitution Check para la justificación
explícita de esta excepción al aislamiento de paquetes:
`diagnostico.evidencia.congelar_vivo()` (recogida de evidencia),
`diagnostico.deepseek.llamar_deepseek()` (llamada HTTP pura, sin la
lógica de negocio de hipótesis), `diagnostico.gasto` (presupuesto
diario compartido). Nunca importa `diagnostico.store`/`model` para
depender de un `causa_probable` — esa vía sigue sin usarse (research.md
§3 de este plan). Vía `remediacion._homelab_bridge` (ya existente,
research.md §11 de 019), se amplía para exponer las funciones ya
probadas de `docker_monitor.py`: `restart_container()`,
`breaker_decision()`, `CRITICAL`, `NEVER_RESTART` — mismo patrón que
`inventory._homelab_bridge.docker_critical()`.

**Storage**: `remediacion.db` (ya existente) gana dos tablas nuevas:
`configuracion_contenedor` (modo por contenedor, no por tipo de
acción — a diferencia de `configuracion_accion` de 019) e
`intentos_reinicio` (evaluación de DeepSeek + desenlace). No toca
`restart_history` (`homelab.db`, de `metrics_db.py`) — queda como
histórico congelado del período anterior al corte (research.md §5).
No escribe en `diagnostico.db` más allá de lo que ya hace
`congelar_vivo()` al reunir evidencia (episodios nuevos, mismo
mecanismo que ya usa el motor de diagnóstico).

**Testing**: `tests/selftest/`, mismo runner ya usado. La llamada real
a DeepSeek (`llamar_deepseek`) y la ejecución real de
`docker_monitor.restart_container()` se sustituyen siempre por dobles
de prueba — ningún test de `--selftest` debe llamar a la API de
DeepSeek de verdad ni reiniciar un contenedor real, mismo principio ya
aplicado al aviso de Telegram de 019 (research.md §11).

**Target Platform**: macOS (Mac Mini M4 Pro), mismo target que el
resto del repo — esta feature además requiere que `docker_monitor.py`
esté desplegado y accesible vía `HOMELAB_SCRIPTS_DIR` para las
funciones que reutiliza.

**Project Type**: Extensión de `src/remediacion/` (paquete ya
existente desde 019) — no un paquete nuevo.

**Performance Goals**: Sin objetivo nuevo — evaluación bajo demanda
(cron cada 5 min, mismo cadencia que `docker_monitor.py` hoy), sobre
como mucho 26 contenedores.

**Constraints**: Ningún contenedor crítico ni `frigate` puede recibir
una evaluación de DeepSeek ni un reinicio, en ningún caso (FR-006,
NO NEGOCIABLE). DeepSeek nunca elige fuera de la lista cerrada
(FR-003). Un fallo de la llamada a DeepSeek nunca se confunde con "no
aplica ninguna acción" (FR-015). Mismo presupuesto diario que
`diagnostico` (FR-013/014).

**Scale/Scope**: 26 contenedores no críticos, un único tipo de acción
candidata (`reiniciar_contenedor`), evaluación cada 5 min solo para
los que no estén `running and healthy`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | Sí | Un contenedor crítico caído, o un cortacircuito abierto, o "ninguna acción aplica" avisan por Telegram cada vez que se detectan — no una sola vez (FR-012). |
| II. Salud por Resultado | Sí | El reinicio se verifica contra el estado real `running` del contenedor, nunca contra el código de salida del comando (FR-010) — mismo criterio que ya corrigió `docker_monitor.py` el 2026-07-26. |
| III. Estado Esperado Declarado | Sí | `running and healthy` sigue siendo el estado esperado de un contenedor no crítico — sin cambios respecto a `docker_monitor.py`. |
| IV. Diagnóstico Previo a la Acción | **Sí, en un sentido ampliado — no literal** (`/speckit-analyze`, hallazgo A1) | Aquí sí hay un diagnóstico real antes de actuar: DeepSeek evalúa evidencia concreta (reutilizada de `diagnostico.evidencia`) y decide si la acción aplica — no una condición ciega. **Matiz honesto**: el principio exige identificar "la causa probable"; esta feature deliberadamente no pregunta eso (research.md §3, spec.md Clarifications) — pregunta algo más estrecho ("¿aplica esta acción?"). Ningún FR/criterio de aceptación exige que el `razonamiento` de DeepSeek constituya una causa, así que la afirmación de cumplimiento no es verificable desde el spec — se sostiene por el espíritu del principio (diagnóstico real, no condición ciega), no por su letra. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí | DeepSeek elige entre la lista cerrada ya definida en código (`reiniciar_contenedor` de 021, `rotar_log` de 019) — nunca inventa una acción nueva (FR-003, verificado explícitamente con Miquel antes de escribir el spec). |
| VI. Reversibilidad Escrita | Parcial, documentado explícitamente | Un reinicio no tiene rollback real (FR-016) — a diferencia de `rotar_log`. Se documenta como excepción explícita, no como incumplimiento silencioso: "reversible" para esta acción significa que el propio contenedor puede volver a reiniciarse si algo sale mal, no que exista una operación de deshacer. |
| VII. Un Actor por Acción | Sí, tras enmendar el principio (constitution.md v2.0.0, 2026-08-14) | `docker_monitor.py` deja de decidir reinicios en su propio bucle (FR-017) — pasa a ser una biblioteca de funciones ya probadas que `remediacion` invoca, no un actor independiente compitiendo por el mismo contenedor. Un único actor decide: `remediacion`. **La versión anterior del principio no cubría esto**: garantizaba sin condiciones que la remediación existente siguiera funcionando "con independencia del estado del agente" — `/speckit-analyze` lo detectó como conflicto real (hallazgo C1), no solo de redacción, porque si `remediacion`/DeepSeek deja de poder evaluar (sin presupuesto, sin respuesta), los 26 no críticos dejarían de auto-repararse sin que nada lo distinga de "sigue vigilado". Resuelto acotando la garantía de independencia a los contenedores críticos (sin cambios para ellos) y exigiendo, como contrapartida no negociable, un aviso cuando la nueva capa lleve evaluaciones consecutivas sin poder decidir — FR-019, nueva en esta feature tras la sesión de clarificación del 2026-08-14. |
| VIII. Registro de Acciones e Hipótesis | Sí | Cada evaluación de DeepSeek (con o sin acción recomendada) y cada intento se registran con su razonamiento y desenlace real (FR-018). |
| IX. Mejora Medida Contra la Línea Base | Sí, con línea base real | A diferencia de 019, aquí sí hay línea base: `restart_history` tiene meses de intentos reales de `docker_monitor.py` — sirve de referencia de tasa de éxito/fallo antes del corte, aunque no se migre (research.md §5). |
| X. Local por Defecto | Sí | Nombres de contenedor y estado del propio Mac — misma naturaleza que datos ya aceptados desde 007. |
| XI. Reproducibilidad Diferida | No aplica | Evaluación en vivo únicamente, mismo criterio que 019 — no hay modo diferido que ofrecer para una decisión de reinicio. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | Sin cambios en el dashboard (Assumptions de spec.md). |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | Empieza solo en contenedores (único origen con acción cerrada real hoy), extensible sin rehacer el mecanismo el día que exista una acción real para otro origen (Clarifications de spec.md). |
| Modelo Operacional B | Sí, generalizado a "por componente" | 019 ya estableció que la lista cerrada es necesaria pero no suficiente para actuar sola (el modo importa). 021 generaliza la granularidad del modo de "por tipo de acción" a "por componente individual" — primera vez que se hace, documentado como extensión explícita, no como contradicción de 019. |

**Resultado**: PASS, con dos excepciones documentadas explícitamente,
ninguna a un principio NO NEGOCIABLE:

1. **Principio VI (Reversibilidad Escrita)**: un reinicio no tiene
   rollback real — aceptado explícitamente en el spec (FR-016), mismo
   criterio de honestidad que ya se aplicó a otras limitaciones reales
   del proyecto (p. ej. el histórico agregado de relays en 012).
2. **Aislamiento de paquetes** (no es un principio numerado, pero es
   un patrón repetido en todo el proyecto): `remediacion` pasa a
   importar de `diagnostico` (evidencia, cliente DeepSeek, gasto) por
   primera vez. Es una dependencia estrecha y deliberada — nunca de
   `diagnostico.store`/`model` ni de la vía de `causa_probable` — no
   una vuelta a un monolito. Documentada aquí y en `research.md §2`.

**Re-chequeo tras el diseño de Fase 1** (research.md, data-model.md,
contracts/cli.md, quickstart.md ya escritos): **PASS confirmado, sin
violaciones nuevas.** El diseño concreto no introdujo ninguna
dependencia ni excepción que no estuviera ya prevista arriba —
`intentos_reinicio` no tiene columna de rollback (coherente con la
excepción 1), y las únicas importaciones nuevas de `remediacion` son
exactamente las tres acotadas en `research.md §2` (coherente con la
excepción 2). `quickstart.md` refuerza, en vez de debilitar, el límite
no negociable de Principio V/FR-003: ningún escenario permite que
DeepSeek ejecute algo fuera de `TIPOS_ACCION`, y ningún escenario toca
un contenedor real de producción.

**Re-chequeo tras `/speckit-tasks` + `/speckit-analyze`** (2026-08-14):
`/speckit-analyze` encontró un **conflicto real** con el Principio VII
tal y como estaba redactado entonces (hallazgo C1, no una simple
ambigüedad de redacción) — ver la fila VII arriba. A diferencia de las
dos excepciones de más abajo (documentadas dentro del principio ya
vigente), esto exigió una **enmienda formal** de la constitución
(`.specify/memory/constitution.md`, 1.2.4 → 2.0.0, MAJOR por
redefinición incompatible), ejecutada con `/speckit-constitution` a
petición explícita de Miquel. spec.md gana FR-019/SC-007 (aviso por
`sin_evaluar` persistente) como contrapartida directa de la enmienda —
sin FR-019, la enmienda de VII quedaría sin la garantía que la
justifica. **PASS confirmado tras la enmienda**, sin violaciones
adicionales.

## Project Structure

### Documentation (this feature)

```text
specs/021-remediacion-contenedores/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md          # Phase 1 output
├── contracts/               # Phase 1 output
│   └── cli.md                  # Extensión del contrato de remediacion.cli
└── tasks.md                      # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/remediacion/                    # paquete YA EXISTENTE (019) — se extiende, no se crea
├── __init__.py                        # docstring ampliado: ya no "independiente de diagnostico"
├── model.py                            # + ConfiguracionContenedor, IntentoReinicio, EvaluacionDeepSeek
├── store.py                              # + tablas configuracion_contenedor, intentos_reinicio
├── acciones.py                             # + reiniciar_contenedor: comprobar/proponer/ejecutar
├── deepseek_contenedores.py                  # NUEVO — construir_prompt_remediacion() + parsear_respuesta_remediacion() + soporte de REMEDIACION_DEEPSEEK_MOCK; el orquestador completo (congelar_vivo → presupuesto → llamar_deepseek → parsear → persistir) es acciones.evaluar_contenedor(), no este módulo — ver data-model.md
├── _homelab_bridge.py                          # + docker_critical/never_restart/restart_container/breaker_decision
└── cli.py                                        # + tipos ya lista reiniciar_contenedor; + modo-contenedor, pendientes-contenedor, etc.

tests/selftest/
├── test_remediacion_deepseek_contenedores.py  # NUEVO — prompt + orquestación, DeepSeek real siempre mockeado
└── test_remediacion_acciones.py                 # + reiniciar_contenedor, restart_container/breaker_decision mockeados
```

**Structure Decision**: extiende el paquete `remediacion` ya
existente — no se crea ninguno nuevo. `docker_monitor.py` (privado,
fuera de este repo) pierde su bucle de decisión de reinicio en
`main()`, pero conserva `restart_container()`/`breaker_decision()`
como funciones reutilizables — cambio en infraestructura privada, sin
versionar aquí, documentado en `research.md §4` y ejecutado como parte
de esta feature.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| `remediacion` importa de `diagnostico` por primera vez (rompe el aislamiento declarado desde 019) | La recogida de evidencia (`congelar_vivo`), el cliente DeepSeek (`llamar_deepseek`) y el presupuesto diario (`gasto.py`) ya existen, probados, en `diagnostico` — duplicarlos en `remediacion` crearía dos copias de la misma lógica que divergirían con el tiempo | Duplicar esas ~150 líneas en `remediacion` mantendría el aislamiento formal, pero el proyecto ya rechazó ese patrón para el aviso de Telegram (research.md §11 de 019 reutiliza `inventory._homelab_bridge` en vez de reimplementar) — aquí el caso es más fuerte porque es lógica interna del propio repo, no solo credenciales |
| `remediacion` reutiliza funciones de `docker_monitor.py` (privado) en vez de reimplementar el reinicio | `restart_container()`/`breaker_decision()` ya se corrigieron una vez tras un bug real (2026-07-26, "success" basado en código de salida) — reimplementarlas arriesga repetir ese mismo bug | Reimplementar en `remediacion` sería más "limpio" en términos de aislamiento público/privado, pero repetiría trabajo ya hecho y ya corregido, exactamente lo que `research.md` de 019 (§11) decidió evitar para el caso análogo del bridge de Telegram |
