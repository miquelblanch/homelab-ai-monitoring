# Tasks: Remediación Asistida por DeepSeek — Contenedores

**Input**: Design documents from `/specs/021-remediacion-contenedores/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest ya usado por `diagnostico`/`inventory`/`remediacion`
(019) — con `llamar_deepseek`, `docker_monitor.restart_container()` y
`docker_monitor.breaker_decision()` siempre sustituidos por dobles de
prueba (quickstart.md, Autocomprobación).

**Organization**: cinco historias de usuario (spec.md), en el orden de
prioridad P1×4, P2×1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros distintos o funciones
  independientes, sin dependencia de datos entre ellas)
- **[Story]**: US1-US5, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Extiende `src/remediacion/` (paquete ya existente desde 019) — no se
crea ningún paquete nuevo. Primera vez que importa de `src/diagnostico/`
(exactamente `evidencia.congelar_vivo`, `deepseek.llamar_deepseek`,
`gasto` — research.md §2, nada más). El reinicio real y el cortacircuito
se reutilizan de `docker_monitor.py` (privado, fuera de este repo, vía
`HOMELAB_SCRIPTS_DIR`) a través de `_homelab_bridge.py` — nunca se
reimplementan (research.md §4).

---

## Phase 1: Setup

- [X] T001 Actualizar el docstring de `src/remediacion/__init__.py` —
  ya no dice "paquete independiente de `diagnostico`, no importa nada
  de ese módulo" (frase heredada de 019); documenta las tres
  importaciones concretas y acotadas que introduce esta feature
  (`evidencia.congelar_vivo`, `deepseek.llamar_deepseek`, `gasto`),
  referencia a `specs/021-remediacion-contenedores/` (research.md §2)

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase

- [X] T002 [P] Ampliar `src/remediacion/model.py` — dataclasses
  `ConfiguracionContenedor` (`contenedor`, `modo="manual"`,
  `actualizado_en`) e `IntentoReinicio` (todos los campos de
  data-model.md: `contenedor`, `modo_en_deteccion`, `episodio_id`,
  `accion_recomendada`, `razonamiento_deepseek`, `coste_eur`, `estado`,
  `detalle`, `creado_en`, `resuelto_en`, `id`); tupla
  `ESTADOS_INTENTO_REINICIO = ("pendiente", "rechazado", "ejecutado",
  "fallido", "cortacircuito", "sin_accion", "sin_evaluar")` — sin
  `"deshecho"` (FR-016). `MODOS` ya existente (`"manual"`/
  `"automatico"`) se reutiliza tal cual, sin duplicarlo. Dataclass
  intermedia `EvaluacionDeepSeek` (`accion_recomendada: str | None`,
  `razonamiento: str | None`, `tokens_entrada: int`,
  `tokens_salida: int`, `fallo: bool`, `motivo_fallo: str | None`) —
  resultado interno de preguntar a DeepSeek, antes de persistirlo como
  `IntentoReinicio`; no tiene tabla propia
- [X] T003 Ampliar `src/remediacion/store.py` — `CREATE TABLE IF NOT
  EXISTS` para `configuracion_contenedor` e `intentos_reinicio` (SQL
  exacto de data-model.md, con su índice
  `idx_intentos_reinicio_contenedor_estado`) dentro del mismo
  `_SCHEMA` ya aplicado por `connect()`; funciones nuevas:
  `get_modo_contenedor(conn, contenedor) -> str` (crea la fila en
  `"manual"` si no existe, mismo patrón que `get_modo()` de 019 —
  research.md §7, caso de un contenedor nuevo no cubierto por la
  migración inicial), `listar_modos_contenedor(conn, contenedores:
  tuple[str, ...]) -> list[tuple[str, str]]` (solo lectura, sin crear
  filas — mismo patrón que `listar_modos()`), `set_modo_contenedor(conn,
  contenedor, modo)`, `insert_intento_reinicio(conn, intento) -> int`,
  `get_intento_reinicio(conn, id) -> IntentoReinicio | None`,
  `update_intento_reinicio_estado(conn, id, estado, detalle)`,
  `intento_reciente_pendiente_o_sin_evaluar(conn, contenedor) -> bool`
  (para que `comprobar_reiniciar_contenedor` no duplique evaluaciones,
  data-model.md), `listar_pendientes_reinicio(conn) ->
  list[IntentoReinicio]`, `intentos_recientes_contenedor(conn,
  contenedor, desde_iso: str) -> list[IntentoReinicio]` (alimenta el
  cortacircuito de US3), `localizar_intento(conn, id) -> tuple[str,
  object] | None` — busca `id` primero en `intentos_remediacion`, luego
  en `intentos_reinicio`, devuelve `("remediacion", intento)` /
  `("reinicio", intento)` o `None` (contracts/cli.md: `pendientes`/
  `aprobar`/`rechazar`/`deshacer` resuelven sobre la tabla que
  corresponda) — depende de T002
- [X] T004 [P] Ampliar `src/remediacion/_homelab_bridge.py` — importar
  `docker_monitor` igual que ya hace `inventory._homelab_bridge`
  (`sys.path` vía `HOMELAB_SCRIPTS_DIR`, `try/except ImportError`);
  `docker_critical() -> set[str]` y `docker_never_restart() -> set[str]`
  (replicadas de `inventory._homelab_bridge`, research.md §2 de 019:
  paquetes independientes, sin importar entre `inventory` y
  `remediacion`); `listar_contenedores() -> list[dict]` — bridge nuevo
  hacia `docker_monitor.get_containers()`, única fuente de verdad de
  qué contenedores existen y su `status`/`health` reales, mismo
  mecanismo que ya usa `docker_monitor.py` (evita reimplementar
  `docker ps` por separado); `restart_container(name, reason) -> bool`
  — bridge hacia `docker_monitor.restart_container()`, con hook de
  pruebas: si `REMEDIACION_TEST_FORZAR_FALLO` está en el entorno,
  devuelve `False` sin tocar Docker (quickstart.md Escenario 5, para
  poder probar el cortacircuito sin depender de un fallo real);
  `breaker_decision(attempts, max_attempts=3) -> tuple[bool, str]` —
  bridge hacia `docker_monitor.breaker_decision()`, función pura
- [X] T005 Ampliar `src/remediacion/acciones.py` —
  `TIPO_ACCION_REINICIAR_CONTENEDOR = "reiniciar_contenedor"`; añadir a
  `TIPOS_ACCION` (pasa de `(TIPO_ACCION_ROTAR_LOG,)` a
  `(TIPO_ACCION_ROTAR_LOG, TIPO_ACCION_REINICIAR_CONTENEDOR)`) — único
  registro de qué tipos de acción existen en el código (comentario ya
  presente en el fichero), ahora con dos valores — depende de T002

**Checkpoint**: persistencia y bridges listos; ninguna historia puede
arrancar antes de esto.

---

## Phase 3: User Story 1 - DeepSeek decide si reiniciar es la acción correcta (Priority: P1) 🎯 MVP del "cerebro"

**Goal**: para un contenedor no crítico caído, el sistema reúne su
evidencia real (reutilizando `diagnostico.evidencia.congelar_vivo`),
pregunta a DeepSeek si `reiniciar_contenedor` aplica, y registra la
decisión con su razonamiento — nunca una condición fija (spec.md
FR-001/FR-002/FR-003/FR-013).

**Independent Test**: con logs simulados que indican un problema
externo, DeepSeek puede recomendar "ninguna acción aplica", no solo
"reiniciar" — quickstart.md Escenario 1 (parte de evaluación) y
Escenario 3.

### Implementación para User Story 1

- [X] T006 [US1] Crear `src/remediacion/deepseek_contenedores.py` —
  `construir_prompt_remediacion(episodio, acciones_candidatas)` — su
  propia pregunta ("dada esta evidencia, ¿aplica alguna de estas
  acciones, y cuál?"), **no** reutiliza `diagnostico.deepseek.
  construir_prompt` (research.md §3); serializa
  `episodio.snapshot_evidencia` igual que hace `construir_prompt`,
  pero con instrucciones propias y la forma de respuesta esperada
  (`{"accion_aplica": "reiniciar_contenedor" | null, "razonamiento":
  "..."}`, `response_format: json_object`)
- [X] T007 [US1] En `deepseek_contenedores.py` —
  `parsear_respuesta_remediacion(respuesta: dict) -> dict | None` —
  extrae `content`/`reasoning_content` igual que `diagnostico.deepseek.
  parsear_respuesta` (mismo respaldo para el caso `content` vacío,
  research.md §3 referencia el hallazgo ya documentado); valida que
  `accion_aplica` sea `null` o esté en `acciones.TIPOS_ACCION` — si no,
  `None` (FR-003: la lista cerrada la impone el código, nunca la
  respuesta del modelo); devuelve también `tokens_entrada`/
  `tokens_salida` de `usage` — depende de T005
- [X] T008 [US1] En `deepseek_contenedores.py` — soporte para
  `REMEDIACION_DEEPSEEK_MOCK` (variable de entorno con un JSON como el
  de T007): si está presente, se usa directamente como respuesta ya
  parseada en vez de llamar a `llamar_deepseek` — sin gastar
  presupuesto real, sin llamada de red (quickstart.md, todos los
  escenarios salvo el 6) — depende de T007
- [X] T009 [US1] En `src/remediacion/acciones.py` —
  `evaluar_contenedor(conn_remediacion, conn_diagnostico, contenedor)
  -> IntentoReinicio` — orquesta (data-model.md): `modo =
  store.get_modo_contenedor(...)`; `episodio =
  evidencia.congelar_vivo(conn_diagnostico, contenedor)`; si
  `REMEDIACION_DEEPSEEK_MOCK` no está presente, comprueba
  `gasto.hay_presupuesto(conn_diagnostico, tokens_estimados)` sobre el
  prompt de T006 — sin presupuesto, crea el intento en `sin_evaluar`
  con `episodio_id` puesto y sin coste (FR-014) y termina; si hay
  presupuesto (o hay mock), llama a `deepseek.llamar_deepseek` (o usa
  el mock de T008), parsea con T007 — un fallo/`None`/respuesta
  inconsistente crea `sin_evaluar` (FR-015, nunca `sin_accion` ni
  `reiniciar`); con una respuesta válida real, registra el coste con
  `gasto.registrar_coste` (nunca para el mock); si `accion_aplica` es
  `null`, crea el intento en `sin_accion` con el razonamiento (US4);
  si es `reiniciar_contenedor`, crea el intento — en `manual` queda
  `pendiente` sin tocar el contenedor (US2); la rama de ejecución en
  `automatico` es la de User Story 3 (T019) — depende de T003, T004,
  T006, T007, T008
- [X] T010 [US1] En `acciones.py` —
  `comprobar_reiniciar_contenedor(conn_remediacion, conn_diagnostico)
  -> list[IntentoReinicio]` — recorre `bridge.listar_contenedores()`,
  excluye los de `bridge.docker_critical()` y
  `bridge.docker_never_restart()` (FR-006, nunca llegan ni a la
  evidencia ni a DeepSeek), se queda con los que no están `running and
  healthy`, salta los que ya tienen un intento `pendiente`/
  `sin_evaluar` reciente (`store.intento_reciente_pendiente_o_sin_evaluar`)
  y llama a `evaluar_contenedor` para el resto — depende de T009
- [X] T011 [US1] Conectar `comprobar-contenedores` en
  `src/remediacion/cli.py` — separado de `comprobar` (que sigue siendo
  solo `rotar_log`, contracts/cli.md); actualizar el docstring del
  módulo con el comando nuevo — depende de T010
- [X] T012 [P] [US1] Autocomprobación
  `tests/selftest/test_remediacion_deepseek_contenedores.py` —
  `construir_prompt_remediacion` incluye la evidencia real;
  `parsear_respuesta_remediacion` rechaza una `accion_aplica` fuera de
  `TIPOS_ACCION` y acepta `null`; `evaluar_contenedor` con
  `congelar_vivo`/`llamar_deepseek` mockeados: recomienda reiniciar,
  concluye que ninguna acción aplica, y el caso de fallo de la llamada
  (`sin_evaluar`, nunca confundido con `sin_accion`); coste registrado
  contra `gasto_diario` compartido con `diagnostico` (FR-013,
  Acceptance Scenario 3 de US1)
- [X] T013 [US1] Validar manualmente el Escenario 1 (parte de
  evaluación, sin aprobar todavía) y el Escenario 3 de
  [quickstart.md](./quickstart.md) — depende de T011

**Checkpoint**: DeepSeek decide con evidencia real, con o sin acción
recomendada, y el coste queda contabilizado — el cambio central que
pidió Miquel ya funciona de extremo a extremo, aunque manual/automático
todavía no tengan su propio CLI de resolución (US2/US3).

---

## Phase 4: User Story 2 - Modo manual: la decisión de DeepSeek se propone, no se ejecuta sola (Priority: P1)

**Goal**: en modo manual, la recomendación de DeepSeek se registra
como propuesta pendiente con su razonamiento; Miquel la aprueba (rota
de verdad, con verificación real) o la rechaza (el contenedor no se
toca) — spec.md FR-007, Acceptance Scenarios de US2.

**Independent Test**: forzar que DeepSeek recomiende reiniciar en
manual crea una propuesta pendiente sin tocar el contenedor;
aprobarla lo reinicia y verifica; rechazarla lo deja como estaba —
quickstart.md Escenarios 1 y 2.

### Implementación para User Story 2

- [X] T014 [US2] En `acciones.py` —
  `resolver_aprobacion_reinicio(conn_remediacion, intento_id) ->
  IntentoReinicio` — exige `estado == "pendiente"` (si no, error
  explícito sin ejecutar nada, mismo criterio que
  `resolver_aprobacion` de `rotar_log`); ejecuta vía
  `bridge.restart_container(contenedor, reason=...)`, pasa a
  `"ejecutado"` si vuelve `True`, a `"fallido"` si no (FR-010: la
  verificación real ya vive en `docker_monitor.restart_container()`,
  no se reimplementa aquí); `resolver_rechazo_reinicio(conn_remediacion,
  intento_id) -> IntentoReinicio` — mismo patrón, pasa a `"rechazado"`
  sin tocar el contenedor, conservando el razonamiento de DeepSeek
  (Acceptance Scenario 3 de US2) — depende de T004, T009
- [X] T015 [US2] Generalizar `pendientes`/`aprobar`/`rechazar` en
  `cli.py` para resolver también sobre `intentos_reinicio` — usan
  `store.localizar_intento` (T003) para decidir qué tabla actualizar;
  `deshacer` rechaza explícitamente cualquier `id` que resuelva a
  `intentos_reinicio` (FR-016, contracts/cli.md garantía 15) en vez de
  intentar deshacer un reinicio — depende de T003, T014
- [X] T016 [P] [US2] Autocomprobación en
  `tests/selftest/test_remediacion_acciones.py` — un intento
  `pendiente` de reinicio no toca el contenedor;
  `resolver_aprobacion_reinicio` ejecuta y verifica de verdad (con
  `bridge.restart_container` mockeado a `True`/`False`);
  `resolver_rechazo_reinicio` dejalo intacto; en
  `tests/selftest/test_remediacion_cli.py` — `aprobar`/`rechazar`
  sobre un `id` de `intentos_reinicio` resuelven la tabla correcta;
  `deshacer` sobre un `id` de `intentos_reinicio` se rechaza
- [X] T017 [US2] Validar manualmente los Escenarios 1 y 2 completos de
  [quickstart.md](./quickstart.md) — depende de T015

**Checkpoint**: el ciclo manual completo funciona — proponer con
razonamiento real, aprobar o rechazar, sin que nada se ejecute sin
que Miquel lo revise.

---

## Phase 5: User Story 3 - Modo automático: DeepSeek decide y el sistema ejecuta solo (Priority: P1)

**Goal**: en modo automático, una recomendación de reiniciar se
ejecuta directo, con la misma verificación real y el mismo
cortacircuito de 3 intentos en 6 horas que ya tenía
`docker_monitor.py` — spec.md FR-008/FR-011, Acceptance Scenarios de
US3.

**Independent Test**: forzar una recomendación de reiniciar en
automático se ejecuta sin ningún paso de aprobación, con verificación
real; al cuarto intento fallido en la ventana, el cortacircuito lo
impide y avisa — quickstart.md Escenarios 4 y 5.

### Implementación para User Story 3

- [X] T018 [US3] En `_homelab_bridge.py` —
  `recent_restart_attempts(conn_remediacion, contenedor, window_hours=6)
  -> int` — cuenta en `intentos_reinicio` (nunca en `restart_history`,
  research.md §5) los intentos en estado `"ejecutado"` o `"fallido"`
  del `contenedor` dentro de la ventana; variables de entorno
  `REMEDIACION_CB_MAX_INTENTOS` (default `3`) y
  `REMEDIACION_CB_VENTANA_HORAS` (default `6`), mismos valores que
  `docker_monitor.CB_MAX_ATTEMPTS`/`CB_WINDOW_HOURS` pero configurables
  para poder probar el cortacircuito por CLI sin esperar 6 horas
  reales (contracts/cli.md) — depende de T004
- [X] T019 [US3] Completar en `acciones.py` la rama `automatico` de
  `evaluar_contenedor` (T009): antes de ejecutar, calcula
  `bridge.recent_restart_attempts(...)` y
  `bridge.breaker_decision(intentos, REMEDIACION_CB_MAX_INTENTOS)`; si
  el cortacircuito lo impide, crea el intento en `"cortacircuito"` sin
  llamar a `restart_container` (FR-011, Acceptance Scenario 3 de US3)
  y avisa por Telegram (FR-012a); si lo permite, ejecuta vía
  `bridge.restart_container` y crea el intento directamente en
  `"ejecutado"`/`"fallido"` según el resultado, sin pasar nunca por
  `"pendiente"` (FR-008, Acceptance Scenario 1) — depende de T009, T018
- [X] T020 [US3] En `acciones.py` — `_notificar_cortacircuito(contenedor,
  detalle)`, mismo patrón que `_notificar_fallo_automatico` ya
  existente (Telegram, nunca lanza, `False` si no se pudo enviar);
  conectarla en T019 — depende de T004
- [X] T021 [P] [US3] Autocomprobación en
  `tests/selftest/test_remediacion_acciones.py` — en automático, una
  recomendación de reiniciar se ejecuta sin ningún `pendiente`
  intermedio; una conclusión de "ninguna acción aplica" nunca reinicia
  en automático (Acceptance Scenario 2 de US3); 3 fallos consecutivos
  simulados abren el cortacircuito exactamente en el 4º intento
  (SC-006), sin llamar a `restart_container` esa vez
- [X] T022 [US3] Validar manualmente los Escenarios 4 y 5 de
  [quickstart.md](./quickstart.md) — depende de T019, T020

**Checkpoint**: la mitad autónoma del interruptor funciona con las
mismas protecciones que `docker_monitor.py` ya tenía — comparable
directamente, no reimplementado desde cero.

---

## Phase 6: User Story 4 - Ninguna acción aplica: avisar con el análisis, no quedarse callado (Priority: P2)

**Goal**: cuando DeepSeek concluye que ninguna acción de la lista
cerrada resuelve el caso, el sistema avisa a Miquel con la evidencia y
el razonamiento, en vez de silencio o de forzar un reinicio ya
descartado — spec.md FR-009, Acceptance Scenarios de US4.

**Independent Test**: forzar una evidencia donde DeepSeek concluye que
ninguna acción aplica dispara un aviso por Telegram con el
razonamiento, y queda registrado como intento consultable — quickstart.md
Escenario 3.

### Implementación para User Story 4

- [X] T023 [US4] En `acciones.py` — `_notificar_sin_accion(contenedor,
  razonamiento)`, mismo patrón Telegram que `_notificar_fallo_automatico`/
  `_notificar_cortacircuito`; conectarla en `evaluar_contenedor` (T009)
  justo cuando el intento se crea en `"sin_accion"`, en cualquier modo
  (manual o automático — FR-009 no distingue) — depende de T009
- [X] T024 [P] [US4] Autocomprobación en
  `tests/selftest/test_remediacion_acciones.py` — un intento
  `"sin_accion"` nunca reinicia el contenedor en ningún modo; el aviso
  se dispara (mockeando `_notificar_sin_accion` para comprobar solo la
  llamada, mismo criterio que 019 con `_notificar_fallo_automatico`);
  el intento queda consultable vía `store.get_intento_reinicio`/
  `store.localizar_intento` con su razonamiento íntegro
- [X] T025 [US4] Validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) — depende de T023

**Checkpoint**: un reinicio que no ayudaría ya no se pierde en
silencio — el valor de "DeepSeek decide" más allá de reiniciar.

---

## Phase 7: User Story 5 - Cambiar el modo de un contenedor concreto (Priority: P1)

**Goal**: Miquel cambia el modo de un contenedor no crítico concreto
(manual ↔ automático) sin afectar a los demás — spec.md FR-004,
Acceptance Scenarios de US5.

**Independent Test**: cambiar el modo de un contenedor de prueba solo
afecta a ese contenedor; dos contenedores en modos distintos resuelven
su recomendación de forma distinta a la vez — quickstart.md Escenario
4 (cambio de modo) y Acceptance Scenario 1 de US5.

### Implementación para User Story 5

- [X] T026 [US5] Conectar `modo-contenedor CONTENEDOR
  (--automatico|--manual)` en `cli.py` — rechaza explícitamente, sin
  escribir nada, si `CONTENEDOR` está en `bridge.docker_critical()` o
  `bridge.docker_never_restart()` (FR-006, Edge Cases de spec.md);
  si no, llama a `store.set_modo_contenedor` — depende de T003, T004
- [X] T027 [US5] Conectar `contenedores` en `cli.py` — lista los
  contenedores no críticos/`NEVER_RESTART` (`bridge.listar_contenedores()`
  filtrado) con su modo actual (`store.listar_modos_contenedor`, solo
  lectura, sin crear filas), mismo espíritu que `tipos` — depende de
  T003, T004
- [X] T028 [P] [US5] Autocomprobación en
  `tests/selftest/test_remediacion_store.py` — `get_modo_contenedor`
  devuelve `"manual"` por defecto para un contenedor nunca visto
  (research.md §7); `set_modo_contenedor` cambia y persiste sin
  afectar a otros contenedores; en `test_remediacion_cli.py` —
  `modo-contenedor` sobre un contenedor de la lista crítica o
  `frigate` se rechaza sin escribir en `configuracion_contenedor`
- [X] T029 [US5] Validar manualmente la parte de cambio de modo del
  Escenario 4 y el comando `contenedores` de
  [quickstart.md](./quickstart.md) — depende de T026, T027

**Checkpoint**: las 5 historias de usuario funcionan juntas — feature
completo según el spec, con el interruptor de granularidad por
contenedor ya aplicado a la decisión de DeepSeek.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T030 [P] Tarea de despliegue: insertar las 26 filas de
  `configuracion_contenedor` en modo `"automatico"` (research.md §7,
  FR-005) — explícita, no depende del comportamiento por defecto de
  `get_modo_contenedor` (que trataría "sin fila" como manual); ejecutar
  con ventana de mantenimiento activa (`mwin`), verificando
  contenedor a contenedor contra la lista de 26 no críticos del
  `CLAUDE.md` general — depende de T026
- [X] T031 Editar `docker_monitor.py` (privado, fuera de este repo,
  `/Volumes/FastData/homelab/scripts/docker_monitor.py`) — retirar de
  `main()` el bloque que decide reiniciar un contenedor no crítico
  caído (research.md §4, líneas ~405-430 de la versión actual;
  FR-017), conservando sin cambios `restart_container()`,
  `breaker_decision()`, `get_containers()`, `CRITICAL`, `NEVER_RESTART`
  y el resto de responsabilidades (métricas, discos, alerta de
  crítico caído) como funciones/datos reutilizables — depende de T030,
  T037 (FR-019 debe estar operativo antes del corte real — no basta
  con la recomendación en prosa de más abajo, es una dependencia
  formal)
- [X] T032 [P] Confirmar por inspección que ningún camino de código
  permite que un contenedor de `bridge.docker_critical()` o
  `bridge.docker_never_restart()` llegue a `evaluar_contenedor` ni a
  `bridge.restart_container` (FR-006, SC-001) — mismo tipo de
  verificación explícita que T025 de 019, documentada aquí como tarea
  y no como supuesto implícito
- [X] T033 [P] Validar manualmente el Escenario 6 de
  [quickstart.md](./quickstart.md) — única llamada real a la API de
  DeepSeek de todo el feature, sobre el contenedor de prueba
  desechable, nunca sobre uno de los 39 reales — depende de T013
- [X] T034 [P] Confirmar que `tests/selftest/
  test_remediacion_deepseek_contenedores.py` se descubre
  automáticamente vía `--selftest` (`pkgutil.iter_modules`, sin
  registro manual — `tests/selftest/__init__.py::run_all()`), junto a
  los módulos ya existentes de 019
- [X] T038 [P] Validación end-to-end de SC-002, cerrada tras el corte
  real (2026-08-14, `/speckit-analyze` hallazgo G2 — no había ninguna
  tarea que la cubriera explícitamente): el Escenario 4 de
  `quickstart.md` ya validó el camino automático completo contra un
  contenedor real (sin aprobación intermedia, verificación real de
  `running`); tras cargar `amsterdam9.remediacion.comprobar-contenedores`
  (T031), su primera ejecución real contra los 26 contenedores de
  producción terminó en "nada por evaluar" — confirma que recorre la
  flota completa sin excluir ninguno por error, con todos ya sanos.
  Sin incidencia real que forzara un reinicio automático de producción
  en el momento del corte

### Añadidas tras `/speckit-analyze` (hallazgos C1/G1, 2026-08-14)

Contrapartida directa de enmendar el Principio VII (constitution.md
v2.0.0): la cesión de la decisión de reinicio a `remediacion` (T031)
solo es segura si una incapacidad persistente de evaluar avisa —
FR-019/SC-007. **Recomendado completarlas antes de T031**: el corte
real retira la única red de seguridad que tenía `docker_monitor.py`
para los no críticos, y FR-019 es su sustituta.

- [X] T035 En `src/remediacion/store.py` —
  `sin_evaluar_consecutivos(conn, contenedor) -> int` — cuenta los
  `intentos_reinicio` más recientes de `contenedor` (orden descendente
  por `id`) mientras su `estado` sea `"sin_evaluar"`, deteniéndose en
  el primero que no lo sea (o devolviendo 0 si no hay ninguno) —
  FR-019 — depende de T003
- [X] T036 En `src/remediacion/acciones.py` —
  `REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS` (variable de entorno,
  default `3` — mismo valor que el cortacircuito por familiaridad,
  mecanismo independiente); `_notificar_sin_evaluar_persistente(
  contenedor, racha)`, mismo patrón Telegram que
  `_notificar_cortacircuito`/`_notificar_sin_accion` (nunca lanza,
  `False` si no se pudo enviar); conectarla en `evaluar_contenedor`
  (T009) — tras crear un intento en `"sin_evaluar"`, comprobar
  `store.sin_evaluar_consecutivos`; al alcanzar o superar el umbral,
  avisar (FR-019) — depende de T009, T035
- [X] T037 [P] Autocomprobación en
  `tests/selftest/test_remediacion_acciones.py` — 3 `sin_evaluar`
  consecutivos (umbral por defecto) disparan el aviso; 2 no lo
  alcanzan y no avisan; una evaluación real entre medias (con o sin
  acción recomendada, no `sin_evaluar`) resetea la racha — depende de
  T036

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las 5
  historias
- **US1 (Phase 3)**: depende solo de la Fase 2 — MVP del "cerebro"
  (decisión con evidencia real)
- **US2 (Phase 4)**: depende de US1 (necesita intentos `pendiente` que
  aprobar/rechazar)
- **US3 (Phase 5)**: depende de US1 (T009, rama automática incompleta
  hasta aquí) y de T018 (cortacircuito)
- **US4 (Phase 6)**: depende de US1 (T009 ya crea `sin_accion`; aquí
  se conecta el aviso)
- **US5 (Phase 7)**: depende solo de la Fase 2 (usa `store.py`/
  `_homelab_bridge.py` directamente) — independiente de US1-US4, en la
  práctica se valida junto a ellas ya desplegadas
- **Polish (Phase 8)**: depende de que las 5 historias estén completas.
  Dentro de Polish, **T031 depende formalmente de T037** (no solo de
  T030) — FR-019 (aviso por `sin_evaluar` persistente) DEBE estar
  operativo antes del corte real de `docker_monitor.py`, es la
  contrapartida de seguridad que hace aceptable retirarle su
  independencia sobre los no críticos (Principio VII enmendado,
  `/speckit-analyze` hallazgo C1/G1, formalizado tras hallazgo U2);
  T035 depende solo de T003, T036 de T009+T035

### Parallel Opportunities

- T002 (model.py) y T004 (_homelab_bridge.py) son paralelos entre sí,
  antes de T003/T005
- T012 (US1) es paralelo al resto de la fase una vez lista T009/T010
- T016 (US2) es paralelo a T015 una vez lista T014
- T021 (US3) es paralelo a T019/T020
- T024 (US4) es paralelo a T023
- T028 (US5) es paralelo a T026/T027
- T032, T033, T034 (Polish) son paralelas entre sí una vez cerradas
  las 5 historias
- T035 es paralela a T032/T033/T034; T037 es paralela al resto una vez
  lista T036

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Setup
2. Completar Fase 2: Foundational (persistencia + bridges)
3. Completar Fase 3: US1 (T006-T013) — DeepSeek decide con evidencia
   real, con o sin acción recomendada
4. **PARAR Y VALIDAR**: Escenarios 1 (evaluación) y 3 de
   `quickstart.md`
5. Es el punto donde el feature ya demuestra el giro que pidió Miquel:
   ya no es la condición fija descartada

### Entrega incremental

1. Setup + Foundational → persistencia y bridges listos
2. US1 → el "cerebro" decide, coste contabilizado — MVP real
3. US2 → ciclo manual completo (aprobar/rechazar una recomendación)
4. US3 → ciclo automático completo, con cortacircuito reutilizado
5. US4 → ningún caso "ninguna acción aplica" se pierde en silencio
6. US5 → el interruptor de granularidad por contenedor
7. Polish → **T035-T037 primero** (FR-019: aviso por `sin_evaluar`
   persistente — la contrapartida que hace segura la independencia
   perdida de `docker_monitor.py`), luego T030-T031 (corte real de
   producción: 26 contenedores + edición de `docker_monitor.py`),
   verificación explícita de exclusión de críticos (T032), única
   llamada real a DeepSeek (T033)

---

## Notes

- [P] = ficheros distintos o funciones independientes, sin dependencia
  de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ningún test de `--selftest` llama a la API real de DeepSeek ni
  reinicia un contenedor real (quickstart.md, Autocomprobación) — los
  únicos puntos de este documento que tocan algo real son T033
  (DeepSeek real, contenedor de prueba) y T030-T031 (corte real de
  producción, con ventana de mantenimiento)
- Ninguna tarea reimplementa `restart_container()`/`breaker_decision()`
  — se reutilizan de `docker_monitor.py` vía `_homelab_bridge.py`
  (research.md §4, mismo motivo que ya justificó reutilizar en vez de
  duplicar para el bridge de Telegram en 019)
- `restart_history` (tabla de `metrics_db.py`) no se toca en ninguna
  tarea de este documento (research.md §5) — los intentos nuevos viven
  siempre en `intentos_reinicio`, `remediacion.db`
- T035-T037 no estaban en la primera versión de este documento — se
  añadieron tras `/speckit-analyze` (hallazgos C1/G1) y la enmienda
  resultante del Principio VII (constitution.md 1.2.4 → 2.0.0,
  2026-08-14). Sin ellas, FR-017 (T031) dejaría a `docker_monitor.py`
  sin la independencia que el principio le garantizaba antes de
  acotarse a críticos, sin ninguna contrapartida real
