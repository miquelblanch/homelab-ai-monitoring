# Implementation Plan: Reinicio de Agentes y Relays (LaunchAgents/LaunchDaemons)

**Branch**: `026-reiniciar-agentes-relays` | **Date**: 2026-08-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/026-reiniciar-agentes-relays/spec.md`

## Summary

Tercera acción de la lista cerrada (tras `rotar_log` de 019 y
`reiniciar_contenedor` de 021), construida sobre el mismo esqueleto
exacto que las dos anteriores — sin paquete nuevo, sin runtime nuevo:

1. **`reiniciar_agente`** (`src/remediacion/acciones.py`): para un
   LaunchAgent/LaunchDaemon sin proceso activo, reúne evidencia real
   (`diagnostico.evidencia.agente.congelar_agente_vivo`, ya existente
   desde 016), pregunta a DeepSeek (`deepseek_agentes.py`, nuevo,
   mismo patrón que `deepseek_contenedores.py`) y ejecuta o propone
   según `configuracion_accion` (019, sin tabla de modo por-instancia
   — a diferencia de contenedores, un agente no tiene eje
   crítico/no-crítico). Ejecución real vía `launchctl kickstart`,
   nueva en este repo (nada que bridgear: no existe un
   "`agent_monitor.py`" privado equivalente a `docker_monitor.py`).
2. **Permiso `sudoers` para `com.homeassistant.*`**: comprobación de
   solo lectura (`sudo -n -l <comando exacto>`, nunca ejecuta) antes
   de intentar el reinicio — alimenta FR-023 (Remediaciones distingue
   "bloqueado por permiso" de "listo para actuar").
3. **Cableado de "Beszel (hub)"**: **cero cambios de backend** —
   `_snapshot_contenedores()` (022) ya incluye los 39 contenedores,
   `beszel` entre ellos, con su clasificación e intento vigente. Solo
   falta el `join` del lado del dashboard privado (por nombre,
   `"Beszel (hub)"` ↔ contenedor `beszel`), documentado en
   `contracts/cli.md`, no implementado en este repositorio.
4. **"Remediaciones" y ampliación de "Correcciones"**: ambas viven en
   el dashboard privado (`homelab-dashboard/scripts/app.py`, fuera de
   este repo, mismo patrón que 019/020/021/022). Este plan solo amplía
   `escribir_snapshot()` con un bloque `agentes[]` (mismo bloque que
   `contenedores[]`/`logs[]`, con el estado del permiso `sudoers`
   incluido) para que el dashboard tenga todo lo que necesita sin
   montar `remediacion.db` directamente — documentado en
   `contracts/snapshot-json.md`.

## Technical Context

**Language/Version**: Python 3.11 (mismo runtime que el resto del repo).

**Primary Dependencies**: Ninguna nueva de terceros. `subprocess` de
la librería estándar (nuevo en este paquete — primera vez que
`remediacion` ejecuta un comando de sistema directamente en vez de vía
un bridge a un script privado, ver Constitution Check). Reutiliza las
mismas tres importaciones de `diagnostico` ya aceptadas desde 021
(`evidencia.congelar_vivo` → aquí `evidencia.agente.congelar_agente_vivo`,
`deepseek.llamar_deepseek`, `deepseek._extraer_contenido_y_tokens` vía
025, `gasto`).

**Storage**: `remediacion.db` (ya existente) — **una tabla nueva**,
`intentos_agente` (mismas columnas que `intentos_reinicio`, con
`label` en vez de `contenedor`). `configuracion_accion` (019) se
reutiliza tal cual para el modo de `reiniciar_agente` — sin tabla de
configuración por-instancia (a diferencia de `configuracion_contenedor`
de 021: un agente no tiene eje crítico/no-crítico, FR-008 del spec).
El espacio de `id` compartido (`_siguiente_id_compartido`,
`localizar_intento`) se amplía de dos tablas a tres — ver research.md
§1, es el cambio con más riesgo de regresión silenciosa de todo el plan.

**Testing**: `tests/selftest/`, mismo runner compartido por los tres
paquetes (025). Casos nuevos: `evaluar_agente` con label sin proceso
activo (modo manual → pendiente; modo automático → ejecutado/fallido),
cortacircuito compartido con contenedores (mismo umbral, casos
mezclados en la misma ventana no deben interferir entre sí),
`sudoers_permitido()` con `sudo -n -l` mockeado (nunca se ejecuta de
verdad en tests), `localizar_intento` con las tres tablas pobladas a
la vez (regresión del hallazgo de 021 sobre IDs compartidos, ahora con
un tercer caso). DeepSeek y `launchctl` siempre mockeados vía
variables de entorno, mismo principio que 021.

**Target Platform**: macOS (Mac Mini M4 Pro), igual que el resto del
repo. `launchctl kickstart` es específico de macOS/launchd — sin
intención de portabilidad (mismo criterio que el resto del proyecto,
atado a esta máquina concreta).

**Project Type**: Extensión de `src/remediacion/` (paquete ya
existente) — no se crea ningún paquete nuevo. Un módulo nuevo y
pequeño, `deepseek_agentes.py` (mismo patrón que
`deepseek_contenedores.py`). Los cambios de interfaz ("Remediaciones",
ampliación de "Correcciones") viven en el dashboard privado, fuera de
este repositorio — documentados en `contracts/`, no versionados aquí.

**Performance Goals**: Sin objetivo nuevo — la comprobación de 43
agentes candidatos se añade a un ciclo de 5 minutos que ya evalúa 39
contenedores; incluso en el peor caso (todos caídos a la vez) el
volumen es pequeño para una sola máquina.

**Constraints**: Ningún reinicio de `com.homeassistant.*` se ejecuta
sin que la comprobación `sudo -n -l` confirme el permiso exacto
instalado (FR-005/FR-023, NO NEGOCIABLE por decisión explícita de
Miquel sobre no compartir contraseñas — spec.md SC-005). El
cortacircuito y el aviso por fallo persistente reutilizan el umbral ya
existente de contenedores, 3 intentos/6 horas — sin configuración
independiente (Clarifications, sesión 2026-08-16). `reiniciar_agente`
es la única acción candidata para un agente caído: si no aplica,
`sin_accion` es una conclusión legítima, nunca un reinicio "porque sí"
(FR-002 reforzado).

**Scale/Scope**: 43 agentes candidatos (32 `amsterdam9.*` + 11
`com.homeassistant.*`) más el cableado de 1 hallazgo (`Beszel (hub)`)
— sobre un inventario total de 792 componentes, el resto sigue sin
ninguna acción real (spec.md, techo ya documentado en
`CASUISTICA-026-acciones-reversibles.md`).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | Sí, vía `amsterdam9.health` (o equivalente), no vía `remediacion` | Igual que 021 con `docker_monitor.py`: la vigilancia y aviso de un agente caído la sigue dando el mecanismo ya existente, sin cambios (FR-013). `remediacion` no notifica un "agente caído" nuevo — solo el resultado de su propia evaluación (`sin_accion`, cortacircuito, sin_evaluar persistente), mismo patrón exacto que contenedores. |
| II. Salud por Resultado | Sí | Un reinicio se verifica con una consulta en vivo (`launchctl list <label>`, tras una espera corta) — nunca contra `LAUNCHAGENTS_RAW` (volcado de hasta 5 min de antigüedad, inútil para algo que acaba de pasar) ni contra el código de salida de `launchctl kickstart` (FR-006, corregido tras `/speckit-analyze` hallazgo D1 — research.md §2b). |
| III. Estado Esperado Declarado | Sí | "Proceso activo" es el estado esperado de un LaunchAgent/LaunchDaemon — ya declarado desde 016, sin cambios. |
| IV. Diagnóstico Previo a la Acción | Sí | DeepSeek evalúa la evidencia real (`congelar_agente_vivo`) antes de proponer — nunca un reinicio automático al solo detectar "no corriendo" (FR-002 reforzado tras Clarifications). |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí | Una acción nueva, `reiniciar_agente`, añadida a `TIPOS_ACCION` (ahora tres: `rotar_log`, `reiniciar_contenedor`, `reiniciar_agente`). Decidido explícitamente en Clarifications: ninguna segunda acción se diseña en este feature — `sin_accion` cubre el resto de casos. |
| VI. Reversibilidad Escrita | Igual que 021, mismo precedente aceptado | Un reinicio de proceso no tiene deshacer literal (FR-007) — mismo criterio que `reiniciar_contenedor` (FR-016 de 021): reversible en el sentido de "no destruye estado, no deja peor de lo que estaba", no en el de "hay un botón deshacer". |
| VII. Un Actor por Acción | Sí | `amsterdam9.health` (o el mecanismo de vigilancia de agentes) sigue siendo, sin cambios, quien vigila y avisa. `remediacion` asume decidir y actuar — misma cesión ya aceptada para contenedores (021), misma contrapartida no negociable (FR-014: aviso tras fallo persistente para decidir). |
| VIII. Registro de Acciones e Hipótesis | Sí | Cada evaluación (con o sin acción recomendada) se registra en `intentos_agente`, igual que `intentos_reinicio` para contenedores. |
| IX. Mejora Medida Contra la Línea Base | No aplica nueva línea base | Sin línea base propia para "reinicio de agentes" — no existía nada equivalente antes con lo que comparar (mismo caso que 021/022). |
| X. Local por Defecto | Sí, extensión de una justificación ya aceptada | Enviar evidencia de un agente caído a DeepSeek es la misma naturaleza de dato ya justificada para contenedores (021) — mismo proveedor, misma justificación, población ampliada. |
| XI. Reproducibilidad Diferida | No aplica | Evaluación en vivo únicamente — ya establecido por 016 (sin modo diferido para agentes, FR-003), sin cambios. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | Sí, directamente relevante | FR-023 existe precisamente por este principio: Remediaciones NO DEBE mostrar como ejecutable un `com.homeassistant.*` cuyo `sudoers` no está instalado — el estado del permiso viaja en el snapshot (`contracts/snapshot-json.md`) para que el dashboard nunca tenga que adivinarlo. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | Los 43 agentes candidatos se derivan de la misma fuente ya usada por 016/Inventario (`launchctl list` vía `LAUNCHAGENTS_RAW`/`launchagent_components()`), no de una lista fija copiada — un agente nuevo reconocido por el inventario entra automáticamente (spec.md, User Story 4, Acceptance Scenario 2). |
| Modelo Operacional B | Sí | Reversible y de bajo riesgo (un reinicio de proceso) → autonomía posible en modo automático, con cortacircuito — mismo modelo que las otras dos acciones. |

**Resultado**: PASS. La única pieza que podría parecer una excepción
nueva —`remediacion` ejecutando un comando de sistema directamente en
vez de bridgear a un script privado— no es una violación de ningún
principio: no hay ningún principio que exija que toda ejecución pase
por un script privado, y la razón de hacerlo así (no existe un
"`agent_monitor.py`" equivalente a `docker_monitor.py` del que
bridgear) queda documentada en Complexity Tracking por transparencia,
no porque incumpla nada.

**Re-chequeo tras Fase 1** (research.md, data-model.md,
contracts/cli.md, contracts/snapshot-json.md, quickstart.md): **PASS
confirmado.** El diseño concreto no introduce ninguna tabla, campo o
dependencia no prevista arriba. La comprobación `sudo -n -l` (research.md
§3) es de solo lectura por diseño — nunca ejecuta el comando que
comprueba, cerrando cualquier duda sobre si podría violar SC-005 por
la puerta de atrás.

**Re-chequeo tras `/speckit-tasks` + `/speckit-analyze`** (2026-08-16):
**PASS confirmado tras corregir un hallazgo real (D1).** El borrador
de research.md §2 dejaba la verificación post-reinicio sin mecanismo
concreto, con riesgo de releer `LAUNCHAGENTS_RAW` (hasta 5 min de
desfase) en vez de consultar en vivo — habría hecho que la fila II de
este Constitution Check afirmara un PASS que el diseño no sostenía de
verdad. Corregido con una consulta en vivo (`launchctl list <label>`,
research.md §2b) antes de escribir ninguna tarea de implementación.
`/speckit-analyze` también encontró un hallazgo HIGH (E1: la
contrapartida no negociable del Principio VII enmendado, FR-014, sin
función ni tarea) — corregido en data-model.md/tasks.md, ver su nota
correspondiente ahí.

## Project Structure

### Documentation (this feature)

```text
specs/026-reiniciar-agentes-relays/
├── plan.md                    # This file
├── research.md                # Phase 0 output
├── data-model.md              # Phase 1 output
├── quickstart.md              # Phase 1 output
├── contracts/                 # Phase 1 output
│   ├── cli.md                     # Subcomandos nuevos/ampliados de remediacion.cli
│   └── snapshot-json.md           # Forma de remediacion_estado.json ampliado (bloque agentes[])
└── tasks.md                   # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/remediacion/                       # paquete YA EXISTENTE — se extiende, no se crea
├── acciones.py                           # + TIPO_ACCION_REINICIAR_AGENTE, TIPOS_ACCION amplia a 3;
│                                            + ejecutar_reiniciar_agente() (subprocess launchctl kickstart +
│                                            verificación en vivo con launchctl list, nunca LAUNCHAGENTS_RAW —
│                                            research.md §2/§2b, corregido tras /speckit-analyze D1);
│                                            + _crear_intento_agente() (punto único de escritura, dispara los
│                                            tres avisos de Telegram — corregido tras /speckit-analyze E1);
│                                            + evaluar_agente()/comprobar_reiniciar_agente() (mismo
│                                            esqueleto exacto que evaluar_contenedor(), con
│                                            configuracion_accion en vez de configuracion_contenedor);
│                                            + _snapshot_agentes() y escribir_snapshot(): + bloque
│                                            agentes[] (mismo patrón que contenedores[] de 022)
├── deepseek_agentes.py                   # NUEVO — construir_prompt_agente(), parsear_respuesta_agente(),
│                                            respuesta_mock(); reutiliza _extraer_contenido_y_tokens (025),
│                                            mismo patrón que deepseek_contenedores.py
├── store.py                              # + tabla intentos_agente (mismas columnas que intentos_reinicio,
│                                            label en vez de contenedor); insert/get/update/listar
│                                            simétricos; _siguiente_id_compartido() y localizar_intento()
│                                            amplían de 2 a 3 tablas (research.md §1 — riesgo principal)
├── model.py                              # + IntentoAgente (dataclass, mismas columnas que
│                                            IntentoReinicio con label); reutiliza ESTADOS_INTENTO_REINICIO
├── _homelab_bridge.py                    # + sudoers_permitido(label) -> bool (sudo -n -l, solo lectura,
│                                            research.md §3); launchagents_activos() si hace falta releer
│                                            LAUNCHAGENTS_RAW fuera de diagnostico (a decidir en research.md §4)
└── cli.py                                # + comprobar-agentes, agentes (solo lectura); pendientes/tipos/
                                             aprobar/rechazar/historial amplían para cubrir intentos_agente
                                             vía localizar_intento (sin comandos nuevos para esos)

tests/selftest/
├── test_remediacion_deepseek_agentes.py  # NUEVO — construir_prompt_agente/parsear_respuesta_agente,
│                                            mismos casos que test_remediacion_deepseek_contenedores.py
├── test_remediacion_acciones.py          # + evaluar_agente (pendiente/ejecutado/fallido/sin_accion/
│                                            sin_evaluar/cortacircuito), + bloque agentes[] del snapshot
├── test_remediacion_store.py             # + intentos_agente (insert/get/update/vigente/recientes),
│                                            + localizar_intento con las tres tablas pobladas
└── test_remediacion_cli.py               # + comprobar-agentes, agentes, aprobar/rechazar sobre un
                                             intento_agente

# Fuera de este repositorio (dashboard privado, mismo patrón que 019/020/021/022):
# homelab-dashboard/scripts/app.py —
#   1. Pestaña "Remediaciones" nueva: lee logs[]/contenedores[]/agentes[] del
#      snapshot ampliado + la clasificación de Inventario, filtra "manual", pinta
#      componente + acción real + clasificación (+ "bloqueado por sudoers" si aplica).
#   2. Ampliación de "Correcciones": además del mecanismo ya existente (alarma
#      resuelta → ALARM_MANUAL_CORRECTIONS_FILE), lee el intento vigente de cada
#      componente directamente del snapshot para mostrar pendiente/rechazado/
#      fallido/cortacircuito de una alarma que sigue activa — sin esperar a que
#      desaparezca. Ver contracts/snapshot-json.md para la forma exacta que
#      consume, y contracts/cli.md §3 para la nota de qué NO cambia (008/021).
#   3. Cableado de "Beszel (hub)": join por nombre entre la fila de Inventario
#      ("Beszel (hub)", categoría infra_monitorizacion) y la entrada "beszel"
#      del bloque contenedores[] ya existente — CERO cambios de backend.
```

**Structure Decision**: extiende `src/remediacion/` — un módulo nuevo
y pequeño (`deepseek_agentes.py`), una tabla nueva (`intentos_agente`),
cero paquetes nuevos. El trabajo de interfaz (pestaña Remediaciones,
ampliación de Correcciones, cableado de Beszel hub) es responsabilidad
del dashboard privado, documentado en `contracts/`, no implementado
aquí — mismo patrón que 019/020/021/022.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| `remediacion` ejecuta `launchctl`/`sudo` directamente vía `subprocess`, en vez de bridgear a un script privado (a diferencia de `restart_container`, que bridgea a `docker_monitor.py`) | No existe ningún "`agent_monitor.py`" privado del que bridgear — el mecanismo de reinicio de agentes no existía en ningún sitio antes de este feature, ni siquiera manual-vía-script (solo sugerencias impresas, `CASUISTICA-026-...md`) | Crear primero un script privado nuevo solo para bridgear después sería indirección sin beneficio — ningún otro consumidor lo necesita hoy, y el propio 019 estableció el precedente de ejecutar directamente (`ejecutar_rotar_log`, sin bridge) cuando no hay nada previo que reutilizar |
| Excepciones heredadas de 021/022 sin cambios: `remediacion` importa de `diagnostico`; reutiliza funciones ya corregidas de fuera del paquete | Documentadas y aceptadas en el plan de 021 — no se reabren aquí, este plan no cambia esa relación | — |
