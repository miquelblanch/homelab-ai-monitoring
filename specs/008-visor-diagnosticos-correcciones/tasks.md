# Tasks: Visor de Diagnósticos en Alarmas

**Input**: Design documents from `/specs/008-visor-diagnosticos-correcciones/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/api-diagnostico.md](./contracts/api-diagnostico.md), [quickstart.md](./quickstart.md)

**Tests**: sin tareas de test automatizado — este repo (`homelab-ai-monitoring`)
no contiene `app.py` (vive en `homelab-dashboard/scripts/app.py`, fuera de
este repositorio, sin árbol de tests propio, mismo caso que features
002/006). La validación es manual contra el dashboard real, siguiendo
[quickstart.md](./quickstart.md) — cada escenario de ese documento tiene
su tarea de validación correspondiente más abajo.

**Organization**: agrupadas por historia de usuario (spec.md) para poder
implementar y validar cada una por separado.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: se puede hacer en paralelo (funciones independientes, sin
  dependencia de datos entre ellas — aunque casi todo vive en el mismo
  fichero `app.py`, así que "paralelo" aquí significa "sin bloqueo
  lógico", no "sin conflicto de merge")
- **[Story]**: US1 / US2 / US3, según spec.md
- Cada tarea incluye la ruta exacta del fichero

## Path Conventions

Todo el código de este feature vive fuera de este repositorio, en
`/Volumes/FastData/homelab/docker/homelab-dashboard/scripts/app.py`
(plan.md, Project Structure) — no se crea ningún paquete nuevo en
`src/` de `homelab-ai-monitoring`.

---

## Phase 1: Setup

**Purpose**: constante de configuración nueva, sin lógica todavía

- [X] T001 Añadir la constante `DIAGNOSTICO_DB_PATH` (por defecto
  `/data/diagnostico.db`) junto a las demás rutas `/data/*` ya
  existentes en `homelab-dashboard/scripts/app.py` (research.md §1)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: acceso a `diagnostico.db` y normalización de fechas que
las tres historias necesitan

**⚠️ CRITICAL**: ninguna historia puede completarse sin esta fase

- [X] T002 Implementar en `homelab-dashboard/scripts/app.py` el lector
  de solo lectura de `diagnostico.db` (`sqlite3.connect(f"file:{DIAGNOSTICO_DB_PATH}?mode=ro", uri=True, timeout=3)`,
  mismo patrón que la lectura existente de `speedtest.db`, research.md
  §1) — devuelve `None`/lista vacía si el fichero no existe o la
  conexión falla, nunca lanza (spec.md FR-008; depende de T001)
- [X] T003 [P] Implementar en `homelab-dashboard/scripts/app.py` la
  normalización de fechas (research.md §4): si el timestamp llega sin
  marca de zona (`episodios.ventana_inicio`/`ventana_fin`, siempre
  locales) se le añade el offset de `Europe/Madrid`
  (`zoneinfo.ZoneInfo`, biblioteca estándar); si ya la trae
  (`episodios.creado_en`/`diagnosticos.creado_en`, ambos UTC explícito
  — corregido el 2026-08-11, `creado_en` no era naive como se pensó al
  escribir esta tarea) se sirve tal cual — función pura, independiente
  de T002

**Checkpoint**: lectura de `diagnostico.db` y normalización de fechas
listas; ninguna historia de usuario puede arrancar antes de esto.

---

## Phase 3: User Story 1 - Ver la conclusión de un diagnóstico sin salir del dashboard (Priority: P1) 🎯 MVP

**Goal**: cada alarma de contenedor caído con un episodio diagnosticado
de la caída actual muestra su conclusión y fecha en el dashboard
(spec.md FR-001/FR-002/FR-004/FR-007, SC-001/SC-005/SC-006).

**Independent Test**: diagnosticar en vivo un contenedor caído por CLI
y comprobar que su alarma en el dashboard muestra la conclusión —
quickstart.md Escenario 1.

### Implementación para User Story 1

- [X] T004 [US1] Implementar `get_diagnostico_para_alarma(componente,
  down_since)` en `homelab-dashboard/scripts/app.py` — busca en
  `episodios` (mismo `contenedor`) el que minimice la distancia de
  `down_since` al **rango** `[ventana_inicio, ventana_fin]` (`0` si cae
  dentro); si esa distancia está dentro de 30 minutos, toma su intento
  de diagnóstico más reciente y devuelve el dict de `data-model.md`
  (`episodio_fecha`, `diagnostico_fecha`, `conclusion_tipo`,
  `conclusion_texto`, `hipotesis`); si no hay ninguno dentro de esa
  tolerancia, devuelve `None` (research.md §2-§3, spec.md FR-004;
  depende de T002, T003). **Corregido el 2026-08-11 tras probar contra
  un episodio real** (`congelar --vivo`): la versión con distancia a un
  solo punto (`ventana_inicio`) rechazaba en falso el caso de uso más
  común — ver research.md §3.
- [X] T005 [US1] Conectar `get_diagnostico_para_alarma()` en la rama
  `origen == "contenedores"` de `get_active_alarms()`
  (`homelab-dashboard/scripts/app.py`) — añade el campo `diagnostico`
  al dict de la alarma; `None` cuando `agrupada=True` (spec.md FR-012)
  o cuando `origen != "contenedores"` (FR-011, sin tocar el resto de
  orígenes) (depende de T004)
- [X] T006 [US1] Ampliar `renderAlarmas()` (JS embebido en
  `homelab-dashboard/scripts/app.py`) para pintar, cuando
  `a.diagnostico` no es `null`, la conclusión
  (`conclusion_tipo`/`conclusion_texto`) y `episodio_fecha` siempre
  visibles bajo la fila de la alarma; cuando es `null`, la alarma se
  ve exactamente igual que hoy (spec.md FR-002/FR-007, SC-005; depende
  de T005)
- [X] T007 [US1] Reconstruir y relanzar el contenedor
  `homelab-dashboard` (`docker compose build dashboard && docker
  compose up -d dashboard`) y validar manualmente el Escenario 1 de
  [quickstart.md](./quickstart.md) (diagnóstico en vivo visible en la
  alarma) y el Escenario 4 (alarma sin diagnóstico, sin cambios) contra
  el dashboard real (depende de T006). **Validado el 2026-08-11**: se
  congeló/diagnosticó en vivo un episodio real (`minipaint`, id 14,
  simulando su `down_since` — el contenedor real se paró y se volvió a
  levantar después) y se confirmó por captura de pantalla real
  (Playwright/Chromium) que la alarma muestra la conclusión, las dos
  fechas (SC-005) y el gasto diario; las alarmas de HA sin diagnóstico
  se siguen viendo sin cambios (SC-004). Este mismo escenario reveló el
  bug de emparejamiento corregido en T004.
- [X] T008 [US1] Validar manualmente el Escenario 5 de
  [quickstart.md](./quickstart.md) — SC-006: una caída anterior ya
  resuelta de `beszel` no debe aparecer en la alarma de una caída nueva
  sin diagnosticar todavía (depende de T006). **Validado el
  2026-08-11**: `get_diagnostico_para_alarma('beszel', '2020-01-01T...')`
  devuelve `None` — ningún episodio real de `beszel` (todos de
  marzo-mayo 2026) cae dentro de la tolerancia de 30 min de un
  `down_since` muy alejado, confirmando que una caída antigua nunca se
  cuela en una alarma sin relación temporal real.

**Checkpoint**: la conclusión de un diagnóstico ya es visible en el
dashboard, con la garantía de que nunca es de una caída anterior — el
feature ya demuestra su valor central (User Story 1 completa e
independientemente comprobable).

---

## Phase 4: User Story 2 - Ver el detalle de cada hipótesis considerada (Priority: P2)

**Goal**: el detalle completo de hipótesis (descripción, comprobación,
desenlace) de un diagnóstico ya visible se puede consultar sin salir
del dashboard (spec.md FR-003, SC-002).

**Independent Test**: comparar el detalle mostrado en el dashboard
contra `diagnostico.cli mostrar` para el mismo episodio — quickstart.md
Escenario 2.

### Implementación para User Story 2

- [X] T009 [US2] Ampliar `renderAlarmas()` (JS,
  `homelab-dashboard/scripts/app.py`) para mostrar, tras una acción
  explícita (clic, colapsado por defecto — research.md §6), el detalle
  de `a.diagnostico.hipotesis`: cada una con su `descripcion`,
  `comprobacion` y `desenlace` (spec.md FR-003, SC-002; el dato ya
  llega desde T004, esta tarea es solo de presentación — depende de
  T006). Implementado con `<details>/<summary>` nativo, sin JS de
  estado adicional.
- [X] T010 [US2] Validar manualmente el Escenario 2 de
  [quickstart.md](./quickstart.md) — el detalle mostrado coincide
  exactamente con `diagnostico.cli mostrar` para el mismo episodio
  (depende de T009). **Validado el 2026-08-11**: la llamada directa a
  `get_diagnostico_para_alarma('beszel', ...)` devolvió las 3
  hipótesis reales del episodio 6 con descripción/comprobación/
  desenlace idénticos a los persistidos en `diagnostico.db` (misma
  fuente que lee `diagnostico.cli mostrar`) — no hay transformación de
  datos entre medias que pudiera introducir una divergencia. El bloque
  `<details>` colapsable se confirmó visualmente (Playwright) con el
  caso de 0 hipótesis (no aparece, correcto); el caso con 3 hipótesis
  no se pudo capturar en pantalla sin parar el contenedor real de
  `beszel` (la propia herramienta de monitorización), evitado a
  propósito.

**Checkpoint**: el razonamiento completo de un diagnóstico es
consultable desde el dashboard — User Story 1 y 2 funcionan juntas.

---

## Phase 5: User Story 3 - Ver el gasto diario acumulado de DeepSeek (Priority: P3)

**Goal**: el gasto acumulado del día en DeepSeek y su límite son
visibles en la pestaña Alarmas (spec.md FR-006, SC-003).

**Independent Test**: comparar el valor mostrado con el acumulado real
de `gasto_diario` para el día en curso — quickstart.md Escenario 3.

### Implementación para User Story 3

- [X] T011 [P] [US3] Implementar `get_gasto_diagnostico_hoy()` en
  `homelab-dashboard/scripts/app.py` — lee `gasto_diario` para el día
  natural en curso (research.md §5); `{"coste_eur_acumulado": 0.0,
  "limite_eur": <default>}` si no hay fila para hoy (spec.md User
  Story 3, escenario 2; depende de T002, independiente de T004-T010)
- [X] T012 [US3] Añadir `gasto_diagnostico` como campo de nivel
  superior en el payload de `/api/data` (`collect()`,
  `homelab-dashboard/scripts/app.py`), junto a `alarms` (depende de
  T011)
- [X] T013 [US3] Mostrar `gasto_diagnostico` una vez en la pestaña
  Alarmas (JS, `homelab-dashboard/scripts/app.py`), no por alarma
  (research.md §6; depende de T012)
- [X] T014 [US3] Reconstruir/relanzar el contenedor si no se hizo ya en
  T007, y validar manualmente el Escenario 3 de
  [quickstart.md](./quickstart.md) (depende de T013). **Validado el
  2026-08-11**: confirmado por API (`gasto_diagnostico` refleja el
  coste real de 0,00347791€ tras diagnosticar el episodio de prueba) y
  por captura de pantalla real ("Diagnóstico DeepSeek hoy: 0,0035€ /
  5€" visible en la cabecera de la pestaña).

**Checkpoint**: las tres historias de usuario funcionan juntas — el
feature completo según el spec.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T015 [P] Validar manualmente que ninguna alarma de otro origen
  (`ha`, `backup`, `relays`...) ni ninguna alarma agrupada
  (`agrupada=true`) lleva un `diagnostico` distinto de `null` —
  inspección directa del payload real de `/api/data` (spec.md
  FR-011/FR-012, contrato api-diagnostico.md garantía 1, corregida
  2026-08-11 tras el hallazgo I1 de `/speckit-analyze`: la clave está
  siempre presente, nunca ausente). **Validado el 2026-08-11**:
  comprobado contra `/api/data` real — 0 alarmas sin la clave
  `diagnostico`, 0 alarmas de origen distinto de `contenedores` con
  valor distinto de `null`, 0 alarmas agrupadas con valor distinto de
  `null`.
- [X] T016 [P] Ejecutar la "Autocomprobación del emparejamiento" de
  [quickstart.md](./quickstart.md) (`get_diagnostico_para_alarma()`
  contra `diagnostico.db` real, sin levantar el dashboard completo)
  como comprobación de regresión rápida para futuros cambios.
  **Validado el 2026-08-11** vía `docker exec homelab-dashboard
  python3 -c "..."` — match esperado, sin match esperado, contenedor
  inexistente y `down_since=None` dan el resultado correcto en los
  cuatro casos.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sin dependencias — empieza de inmediato
- **Foundational (Phase 2)**: depende de Setup — BLOQUEA las tres
  historias
- **US1 (Phase 3)**: depende solo de la Fase 2 — es el MVP real de
  este feature
- **US2 (Phase 4)**: depende de que `renderAlarmas()` ya muestre la
  conclusión (T006, US1) — el detalle de hipótesis es una ampliación
  de esa misma fila, no independiente de verdad pese a tener su propia
  prioridad
- **US3 (Phase 5)**: depende solo de la Fase 2 (T002) — independiente
  de US1/US2 en cuanto a lógica (T011-T013 no tocan
  `get_diagnostico_para_alarma()` ni la conclusión mostrada), aunque
  comparte fichero
- **Polish (Phase 6)**: depende de que las tres historias estén
  completas

### Parallel Opportunities

- T003 (Foundational) es paralelo a T002 (funciones independientes)
- T011 (US3, `get_gasto_diagnostico_hoy()`) es paralelo a todo T004-T010
  (US1/US2) una vez completada la Fase 2 — lógica sin relación
- T015, T016 (Polish) son paralelas entre sí

---

## Implementation Strategy

### MVP real de este feature (User Story 1 sola)

A diferencia de 007, aquí sí hay un MVP mínimo real y con valor propio:

1. Completar Fase 1: Setup
2. Completar Fase 2: Foundational (bloquea todo)
3. Completar Fase 3: US1 (T004-T008)
4. **PARAR Y VALIDAR**: Escenarios 1, 4 y 5 de `quickstart.md`
5. Ese es el punto en el que el feature ya resuelve el problema central
   del spec — ver un diagnóstico sin salir del dashboard, sin inventar
   una caída que no es la actual (SC-006)

### Entrega incremental

1. Setup + Foundational → base lista
2. US1 → MVP real, demo posible (conclusión visible, con la garantía
   de SC-006)
3. US2 → detalle de hipótesis, ampliación de la misma fila
4. US3 → gasto diario visible, independiente de las otras dos
5. Polish → comprobaciones de regresión (contrato respetado, sin fugas
   a orígenes ajenos)

---

## Notes

- [P] = sin dependencia lógica entre tareas, aunque casi todo comparte
  fichero (`app.py`) — no hay conflicto de "paralelo de verdad" que
  evitar aquí, es una app de un solo fichero
- [Story] mapea cada tarea a su historia para trazabilidad
- Ninguna tarea de este documento ejecuta ni dispara un diagnóstico
  nuevo desde el dashboard (FR-009) ni escribe en `diagnostico.db`
  (FR-010) — restricción del propio feature, no algo pendiente
- Sin tareas de test automatizado (ver "Tests" arriba) — la validación
  de cada historia es su tarea de "validar manualmente" contra
  `quickstart.md`
