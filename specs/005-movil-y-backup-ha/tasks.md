---

description: "Task list for Metadatos de Móvil Fuera de Alcance y Backup Propio de HA"
---

# Tasks: Metadatos de Móvil Fuera de Alcance y Backup Propio de HA

**Input**: Design documents from `/specs/005-movil-y-backup-ha/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ficheros.md, quickstart.md (todos presentes)

**Tests**: No se piden tests de contrato/integración explícitos en `spec.md`.
`ha_monitor.py` no tiene suite propia en el homelab (mismo patrón que el
resto de monitores); se valida con `quickstart.md`. La condición nueva de
`is_intentional()` y el tipo de check nuevo no requieren aserciones nuevas
en `test_evaluate.py` — el mecanismo genérico ya está cubierto desde
feature 004 (`research.md` §3).

**Organization**: Tareas agrupadas por historia de usuario (`spec.md`), en
orden de prioridad P1 → P2, más una fase final de verificación cruzada.

**Nota de ubicación**: `scripts/ha_monitor.py` vive fuera de este
repositorio (mismo patrón que 001-004). Solo `src/inventory/evaluate.py`
se toca dentro de este repo — a diferencia de 004, ni `sources.py`, ni
`model.py`, ni `_homelab_bridge.py` necesitan cambios (`plan.md`,
"Project Structure").

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin
  dependencia de una tarea sin terminar)
- **[Story]**: Historia de usuario a la que pertenece la tarea (US1, US2)
- Cada tarea incluye la ruta exacta del fichero que toca

---

## Phase 1: Setup

Sin tareas. Sin proyecto nuevo, sin script nuevo (`plan.md`, "Structure
Decision").

---

## Phase 2: Foundational

Sin tareas bloqueantes. A diferencia de 004, este feature no necesita
ningún cambio de contrato previo — el modelo de `esta_vigilado`/
`condicion_incumplida` ya quedó lo bastante general en 004 para aceptar
un tipo de check nuevo sin tocar `evaluate.py` más allá de la propia
regla de `is_intentional()` (`research.md` §3). Las dos historias son
independientes entre sí desde el principio: US1 toca `evaluate.py`, US2
toca `ha_monitor.py` — ficheros distintos, sin dependencia de código.

---

## Phase 3: User Story 1 - Dejar de contar como brecha los metadatos personales del móvil (Priority: P1) 🎯 MVP

**Goal**: Ninguna entidad con `platform: mobile_app` cuenta como brecha
(FR-001, FR-002).

**Independent Test**: Relanzar el inventario y comprobar que ninguna
entidad de la app móvil de Home Assistant aparece como brecha, sin que
ninguna otra entidad cambie de clasificación (`spec.md`, US1
"Independent Test"; `quickstart.md` §1).

### Implementation for User Story 1

- [X] T001 [US1] (FR-001, FR-002) En `src/inventory/evaluate.py`,
  `is_intentional()`: para `categoria == "entidad_ha"`, añadir que
  `raw.meta.get("platform") == "mobile_app"` cuenta como intencionado,
  junto a las condiciones ya existentes de `disabled_by` y
  `entity_category` (feature 004) — las tres son independientes entre sí
  (`research.md` §1, `data-model.md`). Sin lectura nueva: `platform` ya
  viaja en `meta` desde feature 001.
- [X] T002 [US1] Validar manualmente siguiendo `quickstart.md` §1:
  relanzar `inventory.cli --gaps` y comprobar que el recuento de
  `entidad_ha` baja en al menos 53. **Validación reforzada tras hallazgo
  M1 de `/speckit-analyze`**: comparado el conjunto exacto de brechas
  antes/después (no solo el total) — de las 55 que desaparecieron, 53
  son `platform: mobile_app` (esperado) y 2 son `platform: frigate`
  (`review_status` de ambas cámaras, que pasaron de `unknown` a un valor
  real por el propio paso del tiempo desde la sesión de feature 004 —
  ajeno a este cambio). Confirmado con 0 entidades `mobile_app`
  restantes como brecha. Depende de T001.

**Checkpoint**: User Story 1 funciona y es verificable de forma
independiente — MVP entregable, sin depender de `ha_monitor.py`.

---

## Phase 4: User Story 2 - Saber si el backup automático de Home Assistant ha dejado de funcionar (Priority: P2)

**Goal**: El sistema de copias de seguridad automáticas de HA cuenta
como brecha real cuando la última copia correcta supera 36 h de
antigüedad, o cuando no hay ninguna copia correcta registrada (FR-003,
FR-004).

**Independent Test**: Comprobar que, mientras la última copia correcta
tiene menos de 36 h, no aparece como brecha — y que si esa antigüedad
se supera, sí aparece como brecha real, no como "sin declaración" —
sin depender de que US1 esté terminada (`spec.md`, US2 "Independent
Test"; `quickstart.md` §2).

### Implementation for User Story 2

- [X] T003 [US2] En `scripts/ha_monitor.py`, `check_status()`: añadir el
  tipo de check nuevo `entity_age_below` — lee el `state` de la entidad
  (fecha ISO 8601); `unavailable`/`unknown` → `(False, state,
  "no_disponible")`; no interpretable como fecha → `(False, "fecha no
  interpretable: <state>", "no_numerico")`; antigüedad
  (`datetime.now().timestamp() - fecha.timestamp()`) mayor que
  `check["max_age_s"]` → `(False, "...", "umbral")`; si no, `(True,
  "hace {h}h", "")` (`data-model.md`, `contracts/ficheros.md`).
- [X] T004 [US2] En `scripts/ha_monitor.py`, añadir la entrada nueva a
  `CHECKS`: `id: "ha_backup_reciente"`, tipo `entity_age_below`, entidad
  `sensor.backup_ultima_copia_de_seguridad_automatica_realizada_
  correctamente`, `max_age_s: 129600` (36 h, FR-004) (`data-model.md`).
  Depende de T003 (mismo fichero, el tipo debe existir antes de usarlo).
- [X] T005 [US2] Validar manualmente siguiendo `quickstart.md` §2:
  confirmar que con la copia reciente actual el inventario no marca
  `ha_backup_reciente` como brecha; validar por inspección de código +
  dato sintético (mismo mecanismo ya probado en `quickstart.md` de
  feature 004) que un resultado `ok=false` se clasifica como
  `condicion_incumplida`, no como `sin_declaracion`. Depende de T004.

**Checkpoint**: User Story 2 funciona de forma independiente.

---

## Phase 5: Verificación cruzada

**Purpose**: Confirmar que las dos piezas no rompen nada ya existente y
que el cierre de brechas es el esperado en conjunto.

- [X] T006 Validar `quickstart.md` §3: ejecutar
  `PYTHONPATH=src python3 -m inventory.cli --selftest` y comprobar que
  todo sigue en verde. Depende de T001.
- [X] T007 Validar `SC-001` en conjunto: relanzar
  `PYTHONPATH=src python3 -m inventory.cli --no-telegram` y comprobar
  que el total de brechas `entidad_ha` baja de 150 en al menos 53, con
  el resto de la cola larga sin triar (`melcloud`, `esphome`, `tplink`,
  `script`, `proximity`, etc.) intacto. Depende de T002, T005.

**Checkpoint**: Feature 005 completo.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup / Foundational**: sin tareas.
- **User Story 1 (Phase 3)**: sin dependencia de Foundational (no hay)
  ni de US2.
- **User Story 2 (Phase 4)**: sin dependencia de Foundational ni de US1.
- **Verificación cruzada (Phase 5)**: depende de que las dos historias
  estén terminadas.

### Within User Story 1

T001 → T002.

### Within User Story 2

T003 → T004 (mismo fichero, el tipo de check debe existir antes de la
entrada que lo usa) → T005.

### Parallel Opportunities

- User Story 1 completa (T001-T002) puede avanzar en paralelo con User
  Story 2 completa (T003-T005) — ficheros distintos (`evaluate.py` vs.
  `ha_monitor.py`), sin dependencia de código entre ellas. Es el primer
  feature de los cinco donde las dos historias son 100% paralelas sin
  ninguna coordinación de fichero compartido.

---

## Parallel Example: las dos historias a la vez

```bash
# User Story 1 (un desarrollador/sesión):
Task: "T001 [US1] Condición platform mobile_app en is_intentional()"

# User Story 2, en paralelo (otro desarrollador/sesión):
Task: "T003 [US2] Tipo de check entity_age_below en check_status()"
Task: "T004 [US2] Entrada ha_backup_reciente en CHECKS"
```

---

## Implementation Strategy

### MVP First (User Story 1 sola)

1. T001 → T002.
2. **Parar y validar**: cierra 53 de las 106 brechas de este feature sin
   tocar `ha_monitor.py` — el mayor impacto con el menor riesgo
   (`spec.md`, "Why this priority" de US1).
3. Desplegar/demo si está listo — no depende de US2.

### Incremental Delivery

1. User Story 1 → validar → desplegar (MVP).
2. User Story 2 → validar → desplegar (en paralelo si hay capacidad).
3. Verificación cruzada (T006-T007) → cierre formal de `SC-001`.

---

## Notes

- [P] = ficheros distintos, sin dependencia de código. No se han marcado
  tareas individuales `[P]` porque, dentro de cada historia, hay una
  dependencia de orden real de un único fichero (T001 solo, T003→T004);
  el paralelismo real de este feature está entre historias, documentado
  arriba.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Ninguna tarea de este feature modifica la configuración de la app
  móvil, de ningún dispositivo, ni del sistema de backup de HA
  (`spec.md`, FR-005) — todas las tareas son de lectura/declaración de
  estado esperado.
- Ninguna tarea toca `docker/homelab-dashboard/scripts/app.py`
  (`research.md` §4).
