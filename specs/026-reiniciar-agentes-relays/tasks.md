# Tasks: Reinicio de Agentes y Relays (LaunchAgents/LaunchDaemons)

**Input**: Design documents from `/specs/026-reiniciar-agentes-relays/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [contracts/snapshot-json.md](./contracts/snapshot-json.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest ya usado por `diagnostico`/`inventory`/`remediacion`.
`llamar_deepseek` y `launchctl`/`sudo` siempre sustituidos por dobles de
prueba (quickstart.md, Escenarios 1-5) — solo el Escenario 6 toca un
`launchctl kickstart` real, sobre un LaunchAgent desechable creado y
destruido en la propia prueba.

**Organization**: cinco historias de usuario (spec.md), en el orden
P1, P2, P3, P4, P5. **US3 y US5 no generan tareas de código en este
repositorio** — research.md §7/§9 confirmó que ambas ya están
satisfechas por el trabajo de US1/US4 más un cableado que vive
enteramente en el dashboard privado, fuera de este repo.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros o funciones
  independientes, sin dependencia de datos entre ellas)
- **[Story]**: US1-US5, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Extiende `src/remediacion/` (paquete ya existente) — no se crea ningún
paquete nuevo. Un módulo nuevo, `src/remediacion/deepseek_agentes.py`.
Primera vez que `remediacion` ejecuta un comando de sistema
(`launchctl`/`sudo`) directamente en vez de bridgear a un script
privado — no existe ningún equivalente a `docker_monitor.py` para
agentes (research.md §2).

---

## Phase 1: Setup

- [X] T001 Actualizar el docstring de `src/remediacion/__init__.py` —
  documentar la tercera acción (`reiniciar_agente`), la tercera tabla
  (`intentos_agente`), y que esta feature introduce la primera
  ejecución directa de un comando de sistema del paquete (sin bridge a
  un script privado, research.md §2) — referencia a
  `specs/026-reiniciar-agentes-relays/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase

- [X] T002 [P] Ampliar `src/remediacion/model.py` — dataclass
  `IntentoAgente` (`label`, `modo_en_deteccion`, `episodio_id`,
  `accion_recomendada`, `razonamiento_deepseek`, `coste_eur`,
  `estado`, `detalle`, `creado_en`, `resuelto_en`, `id`) — mismos
  campos que `IntentoReinicio` con `label` en vez de `contenedor`
  (data-model.md); reutiliza `ESTADOS_INTENTO_REINICIO` ya existente,
  sin tupla nueva (el conjunto de estados es idéntico)
- [X] T003 Ampliar `src/remediacion/store.py` — `CREATE TABLE IF NOT
  EXISTS intentos_agente` (SQL exacto de data-model.md, con
  `idx_intentos_agente_label_estado`) dentro de `_SCHEMA`; funciones
  simétricas a las de `intentos_reinicio`:
  `insert_intento_agente(conn, intento) -> int`,
  `get_intento_agente(conn, id) -> IntentoAgente | None`,
  `update_intento_agente_estado(conn, id, estado, detalle)`,
  `intento_reciente_pendiente_o_sin_evaluar_agente(conn, label) ->
  bool`, `listar_pendientes_agente(conn) -> list[IntentoAgente]`,
  `intentos_recientes_agente(conn, label, desde_iso: str) ->
  list[IntentoAgente]` (alimenta el cortacircuito compartido),
  `sin_evaluar_consecutivos_agente(conn, label) -> int`,
  `intento_agente_vigente(conn, label) -> IntentoAgente | None`
  (ventana `REMEDIACION_INTENTO_VIGENTE_MINUTOS`, ya existente);
  **`_siguiente_id_compartido()` amplía de `max(a, b)` a `max(a, b,
  c)` con `intentos_agente`**; **`localizar_intento()` prueba
  `intentos_remediacion` → `intentos_reinicio` → `intentos_agente`,
  en ese orden** (research.md §1 — el cambio de más riesgo de este
  plan, cualquier regresión aquí rompe `aprobar`/`rechazar` sobre las
  tres tablas a la vez) — depende de T002
- [X] T004 [P] Ampliar `src/remediacion/_homelab_bridge.py` —
  `listar_agentes_conocidos() -> list[dict]` (lee `LAUNCHAGENTS_RAW`,
  misma fuente que `diagnostico.evidencia.agente`, filtra por prefijo
  `amsterdam9.`/`com.homeassistant.`, research.md §4);
  `recent_agent_restart_attempts(conn_remediacion, label, window_hours
  = 6) -> int` — mismo cálculo que `recent_restart_attempts()`, sobre
  `intentos_agente` (llama a `store.intentos_recientes_agente`, cuenta
  `estado in ("ejecutado", "fallido")`)
- [X] T005 Ampliar `src/remediacion/acciones.py` —
  `TIPO_ACCION_REINICIAR_AGENTE = "reiniciar_agente"`; `TIPOS_ACCION`
  pasa de 2 a 3 valores — único registro de qué tipos de acción
  existen en el código — depende de T002

**Checkpoint**: persistencia y bridges listos; ninguna historia puede
arrancar antes de esto.

---

## Phase 3: User Story 1 - Reiniciar un LaunchAgent de usuario caído (Priority: P1)

**Goal**: para un `amsterdam9.*` sin proceso activo, el sistema reúne
evidencia real, pregunta a DeepSeek si `reiniciar_agente` aplica, y
ejecuta o propone según el modo vigente — sin privilegios elevados
(spec.md FR-001 a FR-004, FR-006 a FR-012).

**Independent Test**: simular un `amsterdam9.*` sin proceso activo
(vía `LAUNCHAGENTS_RAW` de prueba) y comprobar que el sistema genera
una evaluación y, según el modo, ejecuta o deja una propuesta pendiente
— quickstart.md Escenarios 1-4, sin tocar ningún LaunchDaemon root ni
contenedor.

### Implementación para User Story 1

- [X] T006 [US1] Crear `src/remediacion/deepseek_agentes.py` —
  `construir_prompt_agente(episodio, acciones_candidatas)` —
  instrucciones adaptadas a "un LaunchAgent/LaunchDaemon sin proceso
  activo" (research.md §5), misma forma de respuesta JSON que
  `deepseek_contenedores` (`{"accion_aplica": "reiniciar_agente" |
  null, "razonamiento": "..."}`)
- [X] T007 [US1] En `deepseek_agentes.py` —
  `parsear_respuesta_agente(respuesta: dict) -> dict | None` —
  reutiliza `diagnostico.deepseek._extraer_contenido_y_tokens` (025,
  no se duplica el parseo); valida `accion_aplica` contra
  `acciones.TIPOS_ACCION` completo (mismo criterio que
  `deepseek_contenedores._accion_valida`, sin endurecerlo) — depende
  de T005
- [X] T008 [US1] En `deepseek_agentes.py` — `respuesta_mock()`, mismo
  `REMEDIACION_DEEPSEEK_MOCK` ya usado por contenedores (sin variable
  nueva — un solo mock activo por invocación de CLI, nunca se llaman
  ambos flujos a la vez) — depende de T007
- [X] T009 [US1] En `acciones.py` —
  `ejecutar_reiniciar_agente(label: str, requiere_sudo: bool) -> bool`
  — para `requiere_sudo=False`: `subprocess.run(["launchctl",
  "kickstart", "-k", f"gui/{os.getuid()}/{label}"], timeout=
  REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS)` — **30s, corregido de
  15 tras validar T031 contra la máquina real: un `kickstart` real
  tarda ~18s en devolver el control en este Mac**, medido de forma
  consistente (no un cuelgue, una latencia real de `launchd` en esta
  máquina concreta); (research.md §2); **el código de salida de
  `kickstart` nunca decide el resultado por sí solo** — tras lanzarlo,
  espera `REMEDIACION_AGENTE_ESPERA_VERIFICACION_SEGUNDOS` (3 por
  defecto) y hace una verificación **en vivo**: `subprocess.run(["launchctl",
  "list", label])` (forma de un solo argumento — nunca relee
  `LAUNCHAGENTS_RAW`, que puede tener hasta 5 min de desfase,
  research.md §2b, corregido tras `/speckit-analyze` hallazgo D1);
  `True` solo si esa consulta confirma un PID asignado —
  `REMEDIACION_TEST_FORZAR_FALLO_AGENTE` en el entorno fuerza `False`
  sin invocar `launchctl` en absoluto (hook de pruebas, quickstart.md
  Escenario 3); cualquier excepción o timeout → `False`, nunca lanza.
  La rama `requiere_sudo=True` queda como `NotImplementedError`
  explícito hasta US2 (T016) — para que un uso prematuro falle alto y
  claro, no en silencio
- [X] T010 [US1] En `acciones.py` — primero
  `_crear_intento_agente(conn, label, modo, episodio_id, estado,
  detalle, accion_recomendada=None, razonamiento=None, coste_eur=None)
  -> IntentoAgente` (data-model.md, **añadida tras `/speckit-analyze`
  hallazgo E1**) — mismo rol que `_crear_intento_reinicio()` (021):
  único punto de escritura de `intentos_agente`; si `estado ==
  "sin_evaluar"`, comprueba `store.sin_evaluar_consecutivos_agente(conn,
  label)` y dispara `_notificar_sin_evaluar_persistente(label, racha)`
  si supera `REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS` (FR-014, la
  contrapartida no negociable del Principio VII enmendado — **sin este
  punto único, el aviso queda sin implementar de verdad**, no solo sin
  probar). Después, `evaluar_agente(conn_remediacion, conn_diagnostico,
  label) -> IntentoAgente` — mismo esqueleto exacto que
  `evaluar_contenedor()` (data-model.md), creando siempre el intento vía
  `_crear_intento_agente()`, nunca con un `INSERT` directo: `modo =
  store.get_modo(conn_remediacion, TIPO_ACCION_REINICIAR_AGENTE)`
  (acción por tipo, sin `modo_forzado` — un agente no tiene eje
  crítico); `episodio =
  diagnostico_evidencia.agente.congelar_agente_vivo(conn_diagnostico,
  label)`; sin presupuesto o respuesta inconsistente →
  `_crear_intento_agente(..., estado="sin_evaluar", ...)`;
  `accion_aplica is None` → `_crear_intento_agente(...,
  estado="sin_accion", ...)` + `_notificar_sin_accion(label,
  razonamiento)` (FR-002); modo manual → `_crear_intento_agente(...,
  estado="pendiente", ...)`; modo automático → cortacircuito
  (`bridge.recent_agent_restart_attempts` + `bridge.breaker_decision`,
  mismo umbral que contenedores, sesión Clarifications 2026-08-16) → si
  el cortacircuito está abierto, `_crear_intento_agente(...,
  estado="cortacircuito", ...)` + `_notificar_cortacircuito(label,
  motivo)` (FR-009 — **este aviso también faltaba explícito antes de
  E1**); si no, `ejecutar_reiniciar_agente(label, requiere_sudo=False)`
  → `_crear_intento_agente(..., estado="ejecutado"|"fallido", ...)` —
  depende de T003, T004, T006, T007, T008, T009
- [X] T011 [US1] En `acciones.py` —
  `comprobar_reiniciar_agente(conn_remediacion, conn_diagnostico) ->
  list[IntentoAgente]` — recorre `bridge.listar_agentes_conocidos()`,
  se queda con los sin proceso activo, salta los que ya tienen un
  intento `pendiente`/`sin_evaluar` reciente
  (`store.intento_reciente_pendiente_o_sin_evaluar_agente`), evalúa el
  resto vía `evaluar_agente` — depende de T010
- [X] T012 [US1] Conectar `comprobar-agentes` en
  `src/remediacion/cli.py` — separado de `comprobar`/
  `comprobar-contenedores` (contracts/cli.md); actualizar el docstring
  del módulo — depende de T011
- [X] T013 [US1] Generalizar `pendientes`/`aprobar`/`rechazar`/
  `historial` en `cli.py` para resolver también sobre `intentos_agente`
  vía `store.localizar_intento` (T003, ahora de tres vías); `deshacer`
  rechaza explícitamente cualquier `id` que resuelva a `intentos_agente`
  (FR-007, sin rollback) — depende de T003, T011
- [X] T014 [P] [US1] Autocomprobación —
  `tests/selftest/test_remediacion_deepseek_agentes.py` (mismos casos
  que `test_remediacion_deepseek_contenedores.py`: prompt incluye la
  evidencia real, `accion_aplica` fuera de `TIPOS_ACCION` se rechaza,
  `null` se acepta); ampliar `test_remediacion_acciones.py` (manual →
  pendiente; automático → ejecutado/fallido, con la verificación en
  vivo de T009 mockeada — un `kickstart` con código 0 pero
  `launchctl list` sin PID después debe dar `fallido`, no `ejecutado`;
  sin_accion con `_notificar_sin_accion` disparado; sin_evaluar por
  falta de presupuesto; **3 `sin_evaluar` consecutivos disparan
  `_notificar_sin_evaluar_persistente` — caso nuevo, hallazgo E1,
  antes no probado**; cortacircuito tras 3 intentos en la ventana con
  `_notificar_cortacircuito` disparado — **también nuevo, mismo
  hallazgo E1** — contado solo sobre `intentos_agente`, sin
  interferir con la racha de ningún contenedor); ampliar
  `test_remediacion_store.py` (`localizar_intento` con las tres tablas
  pobladas a la vez — regresión del bug de 021 con un tercer caso);
  ampliar `test_remediacion_cli.py` (`comprobar-agentes`,
  `aprobar`/`rechazar` sobre un `id` de `intentos_agente`)
- [X] T015 [US1] Validar manualmente los Escenarios 1-4 de
  [quickstart.md](./quickstart.md) — depende de T012, T013

**Checkpoint**: un `amsterdam9.*` caído recibe diagnóstico real y, según
el modo, se repara solo o espera aprobación — sin ningún privilegio
especial. MVP real de este feature.

---

## Phase 4: User Story 2 - Reiniciar un relay HA gestionado por un LaunchDaemon root (Priority: P2)

**Goal**: los 11 `com.homeassistant.*` reciben el mismo tratamiento,
sin dar `sudo` genérico — solo el comando exacto de cada relay
conocido, y nunca se ejecuta si el permiso no está confirmado
(spec.md FR-005, FR-023).

**Independent Test**: con el `sudoers` no instalado en la máquina de
pruebas, un intento sobre un `com.homeassistant.*` falla con "permiso
denegado" real (no un mock) — quickstart.md Escenario 5.

### Implementación para User Story 2

- [X] T016 [US2] En `acciones.py` — completar la rama
  `requiere_sudo=True` de `ejecutar_reiniciar_agente()` (T009):
  `subprocess.run(["sudo", "-n", "launchctl", "kickstart", "-k",
  f"system/{label}"], timeout=REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS)`
  — mismo timeout de 30s que la rama sin sudo (T031) — `-n` falla inmediato si el
  `sudoers` no cubre el comando, nunca se cuelga esperando contraseña
  (research.md §2); la verificación en vivo posterior (T009) usa
  `launchctl list <label>` **sin** `sudo` — **confirmado contra la
  máquina real (2026-08-16): leer el estado de un LaunchDaemon root no
  requiere privilegio** (research.md §2b), diseño correcto tal cual,
  sin cambios pendientes
- [X] T017 [US2] En `_homelab_bridge.py` — `sudoers_permitido(label:
  str) -> bool` — `sudo -n -l launchctl kickstart -k
  system/{label}"`, código de salida `== 0`; nunca lanza, cualquier
  fallo se trata como `False` (más seguro que "sin dato", research.md
  §3) — **de solo lectura, nunca ejecuta el comando que comprueba**
- [X] T018 [US2] En `acciones.py` — `comprobar_reiniciar_agente()`
  (T011) determina `requiere_sudo` por prefijo del label
  (`com.homeassistant.` → `True`) al llamar `evaluar_agente`/
  `ejecutar_reiniciar_agente` — depende de T011, T016
- [X] T019 [P] [US2] Autocomprobación — `sudoers_permitido()` con
  `subprocess.run` mockeado (código 0 → `True`, código ≠0 → `False`,
  excepción → `False`); `ejecutar_reiniciar_agente(requiere_sudo=True)`
  con `sudo -n` mockeado a fallo real ("permiso denegado") → intento
  `fallido` con el motivo, nunca `sin_evaluar` (data-model.md,
  transición nueva)
- [X] T020 [US2] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) (contra un `sudoers` real NO
  instalado — resultado esperado, no un mock) — depende de T018

**Checkpoint**: los 43 candidatos (32 + 11) reciben el mismo
tratamiento — ningún reinicio de `com.homeassistant.*` se ejecuta sin
que `sudo -n` lo confirme en el momento.

---

## Phase 5: User Story 3 - Cablear "Beszel (hub)" a la acción ya existente (Priority: P3)

**Goal**: el hallazgo "Beszel (hub)" del inventario queda conectado al
estado real de `reiniciar_contenedor` sobre `beszel` (spec.md FR-015).

**Independent Test**: el bloque `contenedores[]` del snapshot ya
incluye `beszel` con su clasificación e intento vigente.

### Verificación para User Story 3 — sin tareas de código

- [X] T021 [US3] Verificar (no requiere cambio de código en este repo,
  research.md §7): ejecutar `comprobar-contenedores` y confirmar en
  `remediacion_estado.json` que la entrada `"beszel"` del bloque
  `contenedores[]` (ya existente desde 022) tiene `clasificacion` e
  `intento_vigente` reales — el trabajo que falta para que Miquel *vea*
  esto en Inventario es el `join` por nombre del dashboard privado
  (`"Beszel (hub)"` ↔ `"beszel"`), fuera de este repositorio
  (`homelab-dashboard/scripts/app.py`, documentado en plan.md)

**Checkpoint**: confirmado que no hace falta ningún cambio de backend
para esta historia — el dato ya existe, solo falta el cableado visual.

---

## Phase 6: User Story 4 - Ver en "Remediaciones" qué es arreglable y cómo (Priority: P4)

**Goal**: el snapshot expone un bloque `agentes[]` (mismo nivel que
`logs[]`/`contenedores[]`) con la clasificación y el estado del
permiso `sudoers` de cada candidato, para que el dashboard privado
pueda pintar la pestaña "Remediaciones" sin montar `remediacion.db`
directamente (spec.md FR-017 a FR-019, FR-023).

**Independent Test**: `remediacion_estado.json` incluye `agentes[]`
con la forma exacta de `contracts/snapshot-json.md`, incluido
`sudoers_instalado` (`null` para `amsterdam9.*`, `true`/`false` para
`com.homeassistant.*`) — quickstart.md Escenario 7.

### Implementación para User Story 4

- [X] T022 [US4] Ampliar `src/remediacion/clasificacion.py` —
  `clasificar_agente(label: str, modo: str | None) -> str` — mismo
  criterio que `clasificar_log()`: siempre `"ia"` si hay una
  configuración real (no hay eje crítico/automática-determinista para
  agentes, research.md §8)
- [X] T023 [US4] En `acciones.py` — `_snapshot_agentes(conn) ->
  list[dict]` — recorre `bridge.listar_agentes_conocidos()`, para cada
  uno: `running` (de `LAUNCHAGENTS_RAW`), `clasificacion` (T022),
  `sudoers_instalado` (`None` si `amsterdam9.*`, `bridge.sudoers_permitido(label)`
  si `com.homeassistant.*` — T017), `intento_vigente`
  (`store.intento_agente_vigente`); un fallo por agente concreto lo
  omite del array, no aborta el resto (contracts/snapshot-json.md
  garantía 9) — depende de T017, T022
- [X] T024 [US4] En `acciones.py` — `escribir_snapshot()` añade el
  bloque `"agentes": _snapshot_agentes(conn)` al payload ya existente
  (`logs`, `contenedores`) — mismo `try/except` que ya envuelve
  `_snapshot_contenedores()` (nunca aborta el resto del snapshot) —
  depende de T023
- [X] T025 [P] [US4] Autocomprobación — `_snapshot_agentes()` con
  `LAUNCHAGENTS_RAW`/`sudoers_permitido` mockeados: entrada por cada
  candidato conocido, `sudoers_instalado` correcto por tipo,
  `intento_vigente` reflejado cuando existe; `escribir_snapshot()`
  incluye `agentes[]` sin romper `logs[]`/`contenedores[]` existentes
- [X] T026 [US4] Conectar `agentes` (solo lectura) en `cli.py` —
  lista los 43 candidatos con estado/clasificación/`sudoers_instalado`
  (contracts/cli.md) — depende de T023
- [X] T027 [US4] Validar manualmente el Escenario 7 de
  [quickstart.md](./quickstart.md) — depende de T024

**Checkpoint**: el dashboard privado tiene todo el dato que necesita
para pintar "Remediaciones" — la pestaña en sí (JS/HTML de `app.py`)
queda fuera de este repositorio, documentada en plan.md, sin tarea de
código aquí.

---

## Phase 7: User Story 5 - Ampliar "Correcciones" al ciclo completo de un intento (Priority: P5)

**Goal**: Correcciones deja de depender solo de que una alarma
desaparezca — puede leer el `intento_vigente` de cualquier componente
directamente del snapshot (spec.md FR-020/FR-021).

**Independent Test**: el snapshot expone `intento_vigente` en los tres
bloques (`logs[]`, `contenedores[]` desde 022, `agentes[]` desde T024)
— suficiente para que el dashboard cruce una alarma activa con su
intento sin ninguna fuente nueva.

### User Story 5 — verificación que encontró un hueco real y lo cerró

- [X] T028 [US5] Verificar que `remediacion_estado.json` expone
  `intento_vigente` en los tres bloques por igual — **la verificación
  encontró que `logs[]` nunca lo había tenido** (research.md §9 daba
  por hecho, sin comprobarlo, que sí existía "desde 020"). Corregido:
  `store.intento_vigente(conn, tipo_accion, componente)` nueva
  (data-model.md), cableada en `escribir_snapshot()`
  (`contracts/snapshot-json.md` garantía 11), con tests en
  `test_remediacion_store.py`/`test_remediacion_acciones.py`. El
  trabajo que queda (leer este dato en vez de solo
  `ALARM_HISTORY_FILE` al pintar Correcciones) sigue viviendo
  enteramente en `homelab-dashboard/scripts/app.py`, fuera de este
  repositorio — eso sí sin tarea de código aquí

**Checkpoint**: el backend ya soporta esta historia por completo,
incluido el hueco de `logs[]` que la propia verificación encontró — el
único trabajo pendiente (leer el dato en el dashboard) no tiene tarea
en este repo.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T029 [P] Ejecutar la suite completa de autocomprobación
  (`PYTHONPATH=src python3 -m remediacion.cli --selftest`, comparte
  runner con `diagnostico`/`inventory`) tras completar las 5 historias
  — 0 regresiones esperadas sobre las aserciones ya existentes
- [X] T030 [P] Revisar `README.md` — añadir `comprobar-agentes`/
  `agentes` a la lista de comandos si el fichero los documenta (mismo
  criterio que 021/022 al añadir los suyos)
- [X] T031 Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — **resuelto (2026-08-16), causa
  real identificada y corregida, no un artefacto de sesión.** Miquel
  reprodujo el mismo `TimeoutExpired` en una Terminal normal (fuera de
  Claude Code), descartando que fuera cosa de esta sesión. Aislado
  después con varias pruebas controladas (`start_new_session`, `stdin`/
  `stdout`/`stderr` con `DEVNULL` real en vez de `PIPE`, `os.system`):
  **`launchctl kickstart` tarda ~18s en devolver el control en esta
  máquina** (medido de forma consistente, dos veces, exactamente 18.0s
  — probablemente por la cantidad de jobs registrados en `launchd` en
  este homelab), no se cuelga de verdad. El timeout original (15s,
  T009) cortaba una operación que sí iba a terminar bien 3s más tarde
  — un `fallido` falso por mal calibrado, no un fallo de diseño.
  Corregido a `REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS = 30`
  (nueva constante, configurable). Reconfirmado de extremo a extremo
  sobre el LaunchAgent desechable real: `aprobar` → `ejecutado —
  reiniciado y verificado`, ~21s totales, PID nuevo confirmado en vivo
  — depende de T015
- [X] T032 Instalar el `sudoers` real en la máquina de producción —
  **hecho por Miquel el 2026-08-16**, `/etc/sudoers.d/amsterdam9-remediacion-relays`,
  validado con `visudo -c -f` antes de instalar (0440, los 11 labels
  de `com.homeassistant.*` exactos). Confirmado con `sudo -n -l
  launchctl kickstart -k system/com.homeassistant.esphome-sal-relay`:
  el comando se permite sin pedir contraseña. De paso, resolvió
  también la duda abierta de T016/research.md §2b (leer el estado no
  necesita `sudo`, confirmado con `launchctl list
  com.homeassistant.esphome-sal-relay` real, sin privilegios, código 0)
  — depende de T020

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las 5
  historias
- **US1 (Phase 3)**: depende solo de la Fase 2 — MVP real de este
  feature
- **US2 (Phase 4)**: depende de US1 (T009 deja la rama `sudo`
  esqueletada; T011 ya recorre los 43 candidatos)
- **US3 (Phase 5)**: depende solo de la Fase 2 (usa
  `_snapshot_contenedores()`, ya existente desde 022) — independiente
  de US1/US2 en la práctica
- **US4 (Phase 6)**: depende de US1 (clasificación/estado de agentes
  reales que exponer) y de US2 (`sudoers_instalado` real)
- **US5 (Phase 7)**: depende de US4 (T024 — el bloque `agentes[]` es
  lo único que le faltaba al snapshot)
- **Polish (Phase 8)**: depende de que las 5 historias estén completas

### Parallel Opportunities

- T002 (model.py) y T004 (_homelab_bridge.py) son paralelos, antes de
  T003/T005
- T014 (US1) es paralela al resto de la fase una vez listas T010/T011
- T019 (US2) es paralela a T018 una vez lista T017
- T025 (US4) es paralela a T026 una vez lista T024
- T029, T030 (Polish) son paralelas entre sí una vez cerradas las 5
  historias

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Setup
2. Completar Fase 2: Foundational (persistencia + bridges)
3. Completar Fase 3: US1 (T006-T015) — un `amsterdam9.*` caído recibe
   diagnóstico real y se repara solo o espera aprobación
4. **PARAR Y VALIDAR**: Escenarios 1-4 de `quickstart.md`
5. Es el punto donde el feature ya demuestra el valor central — los
   otros 11 candidatos (US2) y la visibilidad (US4/US5) son
   incrementales sobre esto

### Entrega incremental

1. Setup + Foundational → persistencia y bridges listos
2. US1 → 32 `amsterdam9.*` cubiertos, MVP real
3. US2 → los 11 `com.homeassistant.*` se suman, con permiso acotado
4. US3 → confirmado sin trabajo de código — "Beszel (hub)" ya está
   cableado desde 022
5. US4 → el snapshot expone todo lo que el dashboard privado necesita
   para "Remediaciones"
6. US5 → confirmado sin trabajo de código adicional — Correcciones ya
   tiene todo el dato que necesita desde T024
7. Polish → suite completa, instalación real del `sudoers`, único
   kickstart real de todo el feature

---

## Notes

- [P] = ficheros o funciones distintas, sin dependencia de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ningún test de `--selftest` ejecuta `launchctl`/`sudo` reales ni
  llama a la API real de DeepSeek (quickstart.md, Escenarios 1-5) — los
  únicos puntos de todo este documento que tocan algo real son T031
  (kickstart real, LaunchAgent desechable) y el Escenario 8 (DeepSeek
  real, opcional, sin tarea propia)
- **T021 y T028 nacieron como tareas de verificación, no de código**
  — la investigación de `research.md` (§7, §9) encontró que ambas
  historias ya estaban satisfechas por trabajo de otras tareas (022
  para US3, T024 para US5); generar tareas de implementación donde no
  hace falta código habría sido trabajo inventado. **T021 se confirmó
  tal cual — T028 no**: verificarla de verdad (no solo dar por buena
  la premisa de research.md) encontró que `logs[]` nunca había tenido
  `intento_vigente`, y esa verificación sí terminó en código real
  (`store.intento_vigente`, cableado en `escribir_snapshot`). Ninguna
  de las dos generó trabajo inventado — T028 generó trabajo real que
  la propia verificación reveló necesario.
- Ninguna tarea reimplementa `breaker_decision()` — se reutiliza tal
  cual de `docker_monitor.py` vía `_homelab_bridge.py`, mismo bridge ya
  usado por contenedores (research.md §6)
- La pestaña "Remediaciones" y la ampliación visual de "Correcciones"
  (JS/HTML de `homelab-dashboard/scripts/app.py`) no tienen tareas en
  este documento — viven fuera de este repositorio, documentadas en
  `plan.md` y `contracts/snapshot-json.md`, mismo patrón que
  019/020/021/022
