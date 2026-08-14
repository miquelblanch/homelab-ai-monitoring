# Tasks: Clasificación de Remediación en Inventario, con DeepSeek Evaluando también Contenedores Críticos

**Input**: Design documents from `/specs/022-clasificacion-remediacion/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/cli.md](./contracts/cli.md), [quickstart.md](./quickstart.md)

**Tests**: incluidas como tareas de autocomprobación (`tests/selftest/`),
mismo patrón sin pytest ya usado por `remediacion` (019/021) —
`llamar_deepseek` y `docker_monitor.restart_container()` siempre
sustituidos por dobles de prueba (quickstart.md, Autocomprobación).

**Organization**: tres historias de usuario (spec.md), P1×2, P2×1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (ficheros o funciones
  independientes, sin dependencia de datos entre ellas)
- **[Story]**: US1-US3, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Extiende `src/remediacion/` (paquete ya existente desde 019/021) — no
se crea ningún paquete nuevo, salvo un módulo puro nuevo dentro de él
(`clasificacion.py`, sin I/O). Cero tablas nuevas en `remediacion.db`
(data-model.md). El trabajo de interfaz (columna en Inventario, estado
en Alarmas) vive en el dashboard privado
(`homelab-dashboard/scripts/app.py`, fuera de este repositorio) — las
tareas que lo tocan están marcadas explícitamente "(privado, fuera de
este repo)", mismo patrón que T031 de 021.

---

## Phase 1: Setup

- [X] T001 Actualizar el comentario de cabecera del bloque
  "Contenedores" en `src/remediacion/acciones.py` — anota que desde
  `specs/022-clasificacion-remediacion/` la evaluación también cubre
  contenedores críticos (modo siempre forzado a `"manual"`), y que la
  clasificación Manual/Automática/IA vive en el módulo nuevo
  `clasificacion.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: protege la garantía NO NEGOCIABLE (FR-008) que
sostienen las tres historias — ninguna puede darse por completa sin
esto

- [X] T002 [P] Crear `src/remediacion/clasificacion.py` —
  `clasificar_contenedor(nombre: str, criticos: set[str],
  never_restart: set[str], modo: str | None) -> str` (`"manual"` si
  `nombre` está en `criticos` o `never_restart` — `modo` se ignora en
  ese caso; si no, `"ia"` siempre, con independencia de `modo`,
  FR-004); `clasificar_log(modo: str) -> str` (`"automatica"` si
  `modo == "automatico"`, si no `"manual"`, FR-005) — módulo puro, sin
  `sqlite3` ni red (research.md §4, data-model.md)
- [X] T003 [P] Ampliar `src/remediacion/store.py` —
  `set_modo_contenedor(conn, contenedor, modo)` gana una guarda al
  inicio: si `modo == "automatico"` y `contenedor` está en
  `bridge.docker_critical()`, `raise ValueError(f"{contenedor} es
  crítico — no admite modo automático")` sin escribir nada (research.md
  §2, FR-008) — depende de que `_homelab_bridge.docker_critical()` ya
  exista (021, sin cambios de firma)
- [X] T004 [P] Ampliar `src/remediacion/_homelab_bridge.py` —
  `docker_critical()` añade al conjunto devuelto por
  `docker_monitor.CRITICAL` los nombres listados en
  `REMEDIACION_TEST_FORZAR_CRITICO` (variable de entorno, lista
  separada por comas) si está presente — hook de pruebas, nunca activo
  en producción (research.md §1b, contracts/cli.md)

**Checkpoint**: la clasificación pura y las dos guardas de seguridad
están listas — ninguna historia puede completarse antes de esto.

---

## Phase 3: User Story 1 - Ver cómo se resolvería una alarma de cualquier componente (Priority: P1) 🎯 MVP

**Goal**: la pestaña Inventario puede mostrar, para cada contenedor y
cada log vigilado, una clasificación Manual/Automática/IA derivada de
su configuración y criticidad reales — sin inventar nada para el resto
de categorías (spec.md FR-001 a FR-007).

**Independent Test**: `clasificacion.py` produce los valores correctos
para los casos de tabla del spec; el snapshot JSON incluye un bloque
`contenedores[]` con la clasificación correcta para críticos, no
críticos y `NEVER_RESTART` mezclados — quickstart.md Escenario 1 y la
primera parte del Escenario 5 (sin `intento_vigente`, que es de US3).

### Implementación para User Story 1

- [X] T005 [US1] En `src/remediacion/acciones.py` — `escribir_snapshot()`
  gana una clave `contenedores`: recorre `bridge.listar_contenedores()`
  (los 39 conocidos, no solo los evaluables — FR-001/SC-002), y para
  cada uno añade `{"nombre", "critico": nombre in criticos,
  "never_restart": nombre in never_restart, "clasificacion":
  clasificacion.clasificar_contenedor(...), "modo": None si crítico o
  never_restart, si no `store.get_modo_contenedor(conn, nombre)`}` —
  sin la clave `intento_vigente` todavía (US3, T018) — depende de T002,
  T004
- [X] T006 [US1] En `acciones.py` — cada entrada de `logs` dentro de
  `escribir_snapshot()` gana la clave `"clasificacion":
  clasificacion.clasificar_log(modo)`, junto a los campos ya existentes
  (`nombre`, `tamano_bytes`, `umbral_bytes`, `supera_umbral`) — depende
  de T002
- [X] T007 [P] [US1] Autocomprobación
  `tests/selftest/test_remediacion_clasificacion.py` — casos de tabla
  de `clasificar_contenedor`/`clasificar_log` (data-model.md,
  "Clasificación de remediación"): crítico → manual con cualquier
  modo; no crítico → ia con cualquier modo; `NEVER_RESTART` → manual;
  log automático → automatica; log manual → manual — depende de T002
- [X] T008 [US1] Autocomprobación en
  `tests/selftest/test_remediacion_acciones.py` — `escribir_snapshot()`
  con una mezcla de contenedores críticos, no críticos y
  `NEVER_RESTART` (vía `REMEDIACION_TEST_FORZAR_CRITICO` para el caso
  crítico) produce el bloque `contenedores[]` esperado, y `logs[]`
  incluye `clasificacion` — depende de T005, T006
- [X] T009 [US1] Validar manualmente el Escenario 1 completo y la
  primera mitad del Escenario 5 de [quickstart.md](./quickstart.md)
  (clasificación pura + snapshot, sin `intento_vigente`) — depende de
  T008. **Ejecutado contra Docker real** (2026-08-14), con
  `REMEDIACION_DB_PATH`/`DIAGNOSTICO_DB_PATH`/`REMEDIACION_SNAPSHOT_PATH`
  aislados en un directorio temporal y `listar_contenedores()`
  acotado por mock a un único contenedor de prueba desechable
  (`remediacion-quickstart-critico`, marcado crítico solo vía
  `REMEDIACION_TEST_FORZAR_CRITICO`) — los 38 contenedores reales
  restantes nunca se evaluaron ni se leyó su evidencia. `docker
  stop`/`docker inspect` reales; DeepSeek mockeado
  (`REMEDIACION_DEEPSEEK_MOCK`, determinista, sin coste). 5/5 checks
  OK — ver el resto en T016/T020
- [X] T010 [US1] (privado, fuera de este repo — `homelab-dashboard/scripts/app.py`)
  Añadir la columna "remediación" a la pestaña Inventario: unir cada
  componente de `get_inventory()` con `contenedores[]`/`logs[]` del
  snapshot por nombre (contracts/cli.md); "Manual" por defecto para
  cualquier componente ausente de ambos bloques (entidad HA,
  integración, host externo, Hermes, Telegram — FR-003). Si el propio
  snapshot no se puede leer (fichero ausente o JSON corrupto), la
  columna DEBE mostrar "sin datos de remediación" — explícito, nunca
  "Manual" por defecto ni en blanco (spec.md Edge Cases; contracts/cli.md
  garantía 22; añadido tras `/speckit-analyze`, hallazgo E2) — depende
  de T009. **Implementado y desplegado en vivo** (2026-08-14, a
  petición explícita de Miquel — resultó no ser un "dashboard privado"
  en el sentido de fuera de alcance, sino el dashboard real ya en
  producción, editable desde este mismo entorno): función
  `remediacionClasificacion()` + columna nueva en `renderInvTable()`,
  mismo mapeo visual manual→warn/ia→info/automática→ok ya usado en
  Correcciones (008/021). Contenedor `homelab-dashboard` reconstruido
  (`docker compose up -d --build`) y verificado sano — `/api/data`
  responde con `remediacion.contenedores` (39) y `remediacion.logs`
  (17) reales, la cabecera `<th>Remediación</th>` confirmada en el
  HTML servido

**Checkpoint**: la clasificación es correcta y consultable para el
100% del inventario — la pieza mínima que pidió Miquel ya funciona,
aunque los contenedores críticos con "Manual" todavía no tengan
ninguna propuesta real detrás (eso es US2).

---

## Phase 4: User Story 2 - DeepSeek también analiza los contenedores críticos, pero nunca actúa sin aprobación (Priority: P1)

**Goal**: un contenedor crítico caído se evalúa igual que uno no
crítico (misma evidencia, mismo DeepSeek), pero con el modo forzado a
`"manual"` en código — nunca lee ni admite `"automatico"` (spec.md
FR-008/FR-009/FR-010).

**Independent Test**: un contenedor de prueba marcado crítico
(`REMEDIACION_TEST_FORZAR_CRITICO`) que se detiene genera un intento
`pendiente`, nunca uno ejecutado directamente; fijar su modo a
automático se rechaza sin escribir nada; aprobar la propuesta sí
ejecuta y verifica — quickstart.md Escenarios 2, 3 y 4.

### Implementación para User Story 2

- [X] T011 [US2] En `acciones.py` — `evaluar_contenedor(conn_remediacion,
  conn_diagnostico, contenedor, modo_forzado: str | None = None)`:
  nuevo parámetro; si no es `None`, se usa en vez de
  `store.get_modo_contenedor(...)` — la tabla no se consulta en
  absoluto para ese contenedor (research.md §1). Sin cambio de
  comportamiento para las llamadas existentes de 021 (`modo_forzado`
  por defecto `None`)
- [X] T012 [US2] En `acciones.py` —
  `comprobar_reiniciar_contenedor(conn_remediacion, conn_diagnostico)`
  deja de excluir `bridge.docker_critical()` de la lista que recorre —
  solo excluye `bridge.docker_never_restart()` (FR-007). Para un
  contenedor de `criticos` que no esté `running and healthy` y sin ya
  un intento reciente, llama a `evaluar_contenedor(...,
  modo_forzado="manual")` — depende de T011, T003
- [X] T013 [P] [US2] Autocomprobación en
  `tests/selftest/test_remediacion_store.py` — `set_modo_contenedor`
  lanza `ValueError` y no persiste ninguna fila al intentar
  `"automatico"` sobre un contenedor de `docker_critical()`
  (`REMEDIACION_TEST_FORZAR_CRITICO`); `"manual"` sobre el mismo
  contenedor se acepta sin error — depende de T003, T004
- [X] T014 [P] [US2] Autocomprobación en
  `tests/selftest/test_remediacion_acciones.py` —
  `comprobar_reiniciar_contenedor` con un crítico simulado caído crea
  un intento `pendiente` con `modo_en_deteccion == "manual"`, nunca
  `ejecutado`/`fallido` directamente; nunca llega a `cortacircuito`
  (no entra en la rama automática, que exige `bridge.breaker_decision`)
  — depende de T012, T004
- [X] T015 [US2] En `src/remediacion/cli.py` — confirmar que
  `modo-contenedor CONTENEDOR --automatico` sobre un crítico devuelve
  un mensaje de error legible (la excepción de T003 se propaga como
  fallo de comando, no como traza cruda); añadir el flag
  `--incluir-criticos` a `contenedores` (contracts/cli.md): con él,
  añade los 12 críticos a la lista con `modo: null` — depende de T003,
  T005. Autocomprobación emparejada: T026 (Polish — añadida tras
  `/speckit-analyze`, hallazgo E1: era la única tarea de
  implementación del documento sin test emparejado)
- [X] T016 [US2] Validar manualmente los Escenarios 2, 3 y 4 de
  [quickstart.md](./quickstart.md) (crítico caído → pendiente; modo
  automático rechazado; aprobar ejecuta con verificación real) —
  depende de T013, T014, T015. **Ejecutado contra Docker real**
  (2026-08-14), mismo aislamiento que T009: `modo-contenedor
  --automatico` sobre el contenedor de prueba marcado crítico se
  rechazó de verdad (sin escribir fila); `aprobar` ejecutó un `docker
  restart` real sobre él (vía `docker_monitor.restart_container()` sin
  mockear) y `docker inspect` confirmó `Running: true` después —
  verificación real, no solo el código de salida del comando. Ningún
  contenedor de los 39 reales del homelab se tocó. 5/5 checks OK

**Checkpoint**: los contenedores críticos tienen análisis real de
DeepSeek, con la garantía NO NEGOCIABLE de FR-008 sostenida por dos
guardas independientes — el cambio de mayor riesgo de este feature ya
funciona de extremo a extremo.

---

## Phase 5: User Story 3 - Ver en Alarmas el estado real de una remediación en curso (Priority: P2)

**Goal**: para una alarma sobre un contenedor o log con un intento de
remediación vigente, Alarmas muestra ese estado real junto a la
explicación fija de 006 — spec.md FR-011/FR-012.

**Independent Test**: tras generar una propuesta pendiente (US2) o una
rotación de log, el snapshot incluye el estado real en
`intento_vigente`; sin ningún intento vigente, el campo es `null` —
quickstart.md Escenario 5 completo.

### Implementación para User Story 3

- [X] T017 [US3] En `store.py` — constante
  `REMEDIACION_INTENTO_VIGENTE_MINUTOS` (entorno, default `5` — mismo
  patrón nombrado/configurable que `REMEDIACION_CB_VENTANA_HORAS`,
  corregido tras `/speckit-analyze` hallazgo C1: antes era un literal
  "5 minutos" sin nombrar); `intento_reinicio_vigente(conn,
  contenedor) -> IntentoReinicio | None`: el intento más reciente en
  estado `pendiente`/`sin_evaluar`/`sin_accion`, o el
  `ejecutado`/`fallido`/`rechazado` más reciente si su `resuelto_en`
  está dentro de esa ventana; `None` si no hay ninguno relevante
  (data-model.md) — solo lectura, sin efectos — depende de T003 (mismo
  fichero)
- [X] T018 [US3] En `acciones.py` — cada entrada de `contenedores`
  dentro de `escribir_snapshot()` (T005) gana la clave
  `"intento_vigente"`: `None`, o `{"estado", "detalle", "creado_en"}`
  de `store.intento_reinicio_vigente(conn, nombre)` — depende de T005,
  T017
- [X] T019 [P] [US3] Autocomprobación en `test_remediacion_store.py` —
  `intento_reinicio_vigente` devuelve el intento `pendiente` más
  reciente si existe; `None` si el único intento tiene `resuelto_en`
  fabricado fuera de `REMEDIACION_INTENTO_VIGENTE_MINUTOS` y ya está
  `ejecutado` (probado con la ventana reducida por variable de
  entorno, sin dormir minutos reales — hallazgo C1); en
  `test_remediacion_acciones.py` — `escribir_snapshot()` con un intento
  pendiente real refleja `intento_vigente` no nulo para ese contenedor
  — depende de T018
- [X] T020 [US3] Validar manualmente el Escenario 5 completo de
  [quickstart.md](./quickstart.md) (clasificación + `intento_vigente`
  tras aprobar una propuesta) — depende de T019, T016 (necesita el
  flujo de US2 para tener un intento real que mostrar). **Ejecutado
  contra Docker real** (2026-08-14), a continuación de T016: tras
  aprobar de verdad, `escribir_snapshot()` sobre la base temporal
  reflejó `critico=true`, `clasificacion="manual"`, `modo=null`, e
  `intento_vigente.estado="ejecutado"` para el contenedor de prueba
  real — el snapshot completo, no solo su forma. 5/5 checks OK
- [X] T021 [US3] (privado, fuera de este repo —
  `homelab-dashboard/scripts/app.py`) En la pestaña Alarmas, para las
  alarmas `contenedor_caido`/`contenedor_caido_critico` y las de log,
  añadir el estado de `intento_vigente` (si no es `null`) junto a la
  explicación fija de `ALARM_TYPES` (006) — sin tocar el catálogo
  estático ni la pestaña Correcciones (008/021, mecanismo distinto:
  historial de alarmas ya resueltas, no de propuestas en curso). Si el
  snapshot no se puede leer, mostrar "sin datos de remediación" en vez
  de omitir la sección en silencio (mismo criterio que T010,
  contracts/cli.md garantía 22, hallazgo E2) — depende de T018.
  **Implementado y desplegado en vivo** (2026-08-14): función
  `remediacionIntentoHtml()`, con la corrección de E2 real aplicada
  aquí (la primera versión omitía la sección en silencio si el
  snapshot faltaba, en vez de avisarlo — corregido y redesplegado
  antes de cerrar la tarea). **Matiz encontrado al implementar**: "las
  de log" del enunciado no aplica — los 10 orígenes de la Central de
  Alarmas (006) no incluyen ningún origen "logs"; la rotación de logs
  solo aparece en el panel "Remediación" (020), que ya muestra su
  propio estado desde antes de este feature. Solo `contenedor_caido`/
  `contenedor_caido_critico` necesitaban esta pieza. Verificado contra
  `/api/data` real: `alarms.total=5` (alarmas reales de HA, no
  relacionadas con este feature), `remediacion.contenedores` con 39
  entradas — ninguna alarma de contenedor activa ahora mismo, así que
  el bloque nuevo no se dispara todavía, comportamiento correcto

**Checkpoint**: las tres historias funcionan juntas — el 100% del
inventario clasificado (US1), los críticos con análisis real y
aprobación obligatoria (US2), y el estado de cualquier remediación en
curso visible sin salir de Alarmas (US3).

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T022 [P] Confirmar por inspección que ningún camino de código
  permite que `configuracion_contenedor.modo == "automatico"` se lea o
  se aplique para un contenedor de `bridge.docker_critical()` — dos
  puntos a revisar explícitamente: `store.set_modo_contenedor` (T003,
  guarda de escritura) y `evaluar_contenedor` con `modo_forzado`
  (T011, guarda de evaluación) — mismo tipo de verificación explícita
  que T032 de 021 (FR-008, SC-005)
- [X] T023 [P] Confirmar que
  `tests/selftest/test_remediacion_clasificacion.py` se descubre
  automáticamente vía `--selftest` (`pkgutil.iter_modules`, sin
  registro manual — `tests/selftest/__init__.py::run_all()`)
- [X] T024 Verificar que el LaunchAgent
  `amsterdam9.remediacion.comprobar-contenedores` (020, cada 5 min)
  sigue completando su ciclo dentro de su ventana habitual tras
  incluir los 12 críticos en el recorrido de
  `comprobar_reiniciar_contenedor` — sin aumentar su cadencia ni su
  presupuesto de DeepSeek más allá de lo ya compartido (FR-015).
  **Resulta que sí era una tarea de esta sesión**: este repo es
  `WorkingDirectory`/`PYTHONPATH` real de los dos LaunchAgents de
  `remediacion` (`~/Library/LaunchAgents/amsterdam9.remediacion.*.plist`)
  — no hay paso de despliegue aparte, el código editado aquí ya es el
  código en producción. **Incidente real encontrado y ya resuelto**:
  el log (`~/Library/Logs/remediacion-comprobar-contenedores.log`)
  muestra un `ImportError: cannot import name 'intento_reinicio_vigente'`
  — el LaunchAgent disparó a mitad de esta sesión, en la ventana entre
  añadir el import en `acciones.py` (T005/T006) y crear la función en
  `store.py` (T017), unos minutos después. Autocorregido solo en el
  siguiente ciclo de 5 min una vez completado T017 — 0 contenedores
  tocados durante el fallo (crashea antes de leer ningún contenedor).
  10 ejecuciones limpias ("nada por evaluar") confirmadas después. Sin
  cambio de cadencia ni gasto — cero contenedores no críticos caídos
  ahora mismo, así que no hay ninguna llamada real a DeepSeek que
  contar todavía
- [X] T025 Ejecutar `python3 -m remediacion.cli --selftest` completo
  tras todas las tareas anteriores — cero regresiones sobre la
  cobertura ya existente de 019/021

### Añadida tras `/speckit-analyze` (hallazgo E1, 2026-08-14)

T015 era la única tarea de implementación de todo el documento sin
una tarea de autocomprobación emparejada — cada otra pieza (T002-T006,
T011-T012, T017-T018) sí la tiene, y 021 tenía su propio
`test_remediacion_cli.py` para el mismo tipo de comportamiento
(rechazo de `modo-contenedor` sobre un crítico).

- [X] T026 [P] [US2] Crear/ampliar
  `tests/selftest/test_remediacion_cli.py` — `contenedores
  --incluir-criticos` incluye los 12 críticos con `modo: null`, y sin
  el flag no cambia el comportamiento de 021 (solo los 26 no
  críticos); `modo-contenedor CONTENEDOR --automatico` sobre un
  crítico (`REMEDIACION_TEST_FORZAR_CRITICO`) devuelve un error de
  comando legible, sin traza cruda y sin persistir ninguna fila
  (mismo hecho que T013 ya prueba a nivel de `store.py`, aquí a nivel
  de CLI) — depende de T015

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las 3
  historias (protege FR-008, NO NEGOCIABLE)
- **US1 (Phase 3)**: depende solo de la Fase 2 — MVP: clasificación
  visible para el 100% del inventario
- **US2 (Phase 4)**: depende solo de la Fase 2 — independiente de US1
  en código (usa `_homelab_bridge`/`store` directamente), aunque su
  valor completo se aprecia junto a US1 (la columna "Manual" de un
  crítico deja de estar vacía)
- **US3 (Phase 5)**: depende de US1 (T005, el bloque `contenedores[]`
  que amplía) y de US2 (T016, necesita un intento real para validar el
  Escenario 5 completo)
- **Polish (Phase 6)**: depende de que las 3 historias estén completas.
  T026 depende solo de T015 (US2) — se completó en Polish porque se
  añadió tras `/speckit-analyze`, no porque dependa de US3

### Parallel Opportunities

- T002, T003, T004 (Foundational) son paralelas entre sí — ficheros
  distintos, sin dependencia de datos
- T007 (US1) es paralela al resto de su fase una vez lista T002
- T013, T014 (US2) son paralelas entre sí una vez listas T003/T004/T012
- T019 (US3) es paralela al resto una vez lista T018
- T022, T023, T026 (Polish) son paralelas entre sí y con T024/T025

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

1. Completar Fase 1: Setup
2. Completar Fase 2: Foundational (clasificación pura + dos guardas)
3. Completar Fase 3: US1 (T005-T010) — el 100% del inventario ya
   clasificado, consultable en el snapshot y (fuera de este repo) en
   el dashboard
4. **PARAR Y VALIDAR**: Escenario 1 de `quickstart.md`
5. Es el punto donde ya se cumple SC-001/SC-002, aunque los críticos
   con "Manual" todavía sean una etiqueta sin propuesta real detrás

### Entrega incremental

1. Setup + Foundational → clasificación pura y guardas de seguridad
   listas
2. US1 → columna de Inventario completa — MVP real
3. US2 → el cambio de mayor riesgo: DeepSeek también analiza críticos,
   siempre con aprobación explícita
4. US3 → Alarmas deja de ser solo texto para lo que sí tiene acción
   real
5. Polish → verificación explícita de las dos guardas (T022), y
   confirmación de que el cron de producción sigue sano tras incluir
   críticos (T024)

---

## Notes

- [P] = ficheros o funciones distintas, sin dependencia de datos
- [Story] mapea cada tarea a su historia para trazabilidad
- Ningún test de `--selftest` llama a la API real de DeepSeek ni
  reinicia un contenedor real — los únicos puntos de este documento
  que tocarían algo real son las validaciones manuales de
  `quickstart.md` (siempre sobre un contenedor de prueba desechable,
  marcado crítico solo vía `REMEDIACION_TEST_FORZAR_CRITICO`, nunca
  uno de los 12 reales)
- Cero tablas nuevas en `remediacion.db` — ninguna tarea de este
  documento crea una migración de esquema (data-model.md)
- T026 no estaba en la primera versión de este documento — se añadió
  tras `/speckit-analyze` (hallazgo E1, 2026-08-14): T015 era la única
  tarea de implementación sin autocomprobación emparejada. T017 y T010/
  T021 se reescribieron en la misma sesión (hallazgos C1 y E2) sin
  cambiar su ID, porque ninguna tarea de este documento estaba todavía
  implementada — no hubo necesidad de un patrón de "tareas añadidas
  después" para esas dos, a diferencia de T026
- T010 y T021 son las únicas tareas que tocan el dashboard privado —
  el resto de este documento es enteramente `homelab-ai-monitoring`
  (repo público)
