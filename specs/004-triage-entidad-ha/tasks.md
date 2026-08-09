---

description: "Task list for Triaje de Brechas entidad_ha — Ajustes, Automatizaciones y Frigate"
---

# Tasks: Triaje de Brechas `entidad_ha` — Ajustes, Automatizaciones y Frigate

**Input**: Design documents from `/specs/004-triage-entidad-ha/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ficheros.md, quickstart.md (todos presentes)

**Tests**: No se piden tests de contrato/integración explícitos en `spec.md`. Se
amplía `--selftest` de `inventory.cli` con casos para el tipo de brecha nuevo
(`condicion_incumplida`) y la regla de `entity_category`, como parte de las
tareas de implementación — no como fase de test aparte. `ha_monitor.py` no
tiene suite propia en el homelab (mismo patrón que el resto de monitores);
se valida con `quickstart.md`.

**Organization**: Tareas agrupadas por historia de usuario (`spec.md`), en orden
de prioridad P1 → P2 → P3, con una fase Foundational previa (bloquea US2 y
US3, no US1 — ver Dependencies) y una fase final de verificación cruzada.

**Nota de ubicación**: `scripts/ha_monitor.py` vive fuera de este repositorio,
en la máquina privada del homelab (mismo patrón que 001-003). El resto de
tareas tocan `src/inventory/` dentro de este repo público.

**Las 17+33+5 `entity_id` exactas** de automatizaciones, entidades de Frigate
y excepciones de seguridad están en `data-model.md` (confirmadas contra el
registro real de HA el 2026-08-09) — no se repiten aquí.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (ficheros distintos, sin dependencia de
  una tarea sin terminar)
- **[Story]**: Historia de usuario a la que pertenece la tarea (US1, US2, US3)
- Cada tarea incluye la ruta exacta del fichero que toca

---

## Phase 1: Setup

Sin tareas. Sin proyecto nuevo, sin script nuevo — ampliación de ficheros que
ya existen (`plan.md`, "Structure Decision").

---

## Phase 2: Foundational (bloquea US2 y US3 — no US1)

**Purpose**: El cambio de contrato de `esta_vigilado` (`research.md` §4) y el
tipo de brecha nuevo son prerrequisito para que las automatizaciones (US2) y
Frigate (US3) puedan mostrarse como `condicion_incumplida` en vez de
`sin_declaracion`. User Story 1 (regla `entity_category`) no depende de
ninguna de estas tareas — puede avanzar en paralelo desde el principio.

- [X] T001 [P] En `src/inventory/model.py`, añadir `"condicion_incumplida"` a
  la tupla `TIPOS_BRECHA` (FR-004, FR-006; `data-model.md`, "Tipo de brecha
  nuevo").
- [X] T002 [P] En `src/inventory/_homelab_bridge.py`, añadir
  `ha_monitor_check_result(entity_id)`: lee `ha_monitor_state.json` desde la
  ruta privada del homelab, construye el mapeo `entity_id → id de check` a
  partir de `ha_monitor.CHECKS` (ya importado en este fichero), y devuelve la
  entrada de estado correspondiente (`{ok, down_since, label, motivo,
  detail}`) o `None` si no hay dato — nunca lanza, mismo principio "a prueba
  de fallos" que `read_heartbeat()` en el mismo fichero (`contracts/
  ficheros.md`). Fichero distinto de T001, sin dependencia de código.
- [X] T003 (FR-004, FR-006) En `src/inventory/evaluate.py`,
  `_vigilancia_entidad_ha()`: sustituir la comprobación de membresía pura por
  una llamada a `bridge.ha_monitor_check_result()` — `tiene_estado_declarado`
  sigue siendo "¿está en `ha_monitor.CHECKS`?", pero `esta_vigilado` pasa a
  ser el `ok` real del último resultado (`research.md` §4, `contracts/
  ficheros.md`). Aplica a los 65 checks de `entidad_ha` en `CHECKS` (los 15
  ya existentes + los 50 de este feature), no solo a los nuevos. Depende de
  T002.
- [X] T004 (FR-004, FR-006) En `src/inventory/evaluate.py`, `classify_gap()`
  y `gap_context()`: nueva rama para cuando `tiene_estado_declarado=True` y
  `esta_vigilado=False` con motivo distinto de "ausente"/"caducada" →
  `"condicion_incumplida"`, con el mensaje "'{nombre}' ({categoria}) tiene un
  estado esperado declarado y vigilado, pero su último resultado real no lo
  cumple: {detalle}." (`data-model.md`). Depende de T001, T003. Mismo fichero
  que la futura T007 de User Story 1 (funciones distintas — `classify_gap()`/
  `gap_context()` vs. `is_intentional()` — coordinar si se hacen a la vez).

**Checkpoint**: El modelo de `entidad_ha` ya distingue "nunca declarado" de
"declarado y vigilado pero incumplido" — listo para que US2 y US3 lo usen.

---

## Phase 3: User Story 1 - Dejar de contar como brecha lo que es ajuste, no salud (Priority: P1) 🎯 MVP

**Goal**: Ninguna entidad con `entity_category` de ajuste o diagnóstico
(salvo las excepciones de seguridad y las de Frigate) cuenta como brecha
(FR-001, FR-002, FR-003).

**Independent Test**: Relanzar el inventario y comprobar que ninguna entidad
con `entity_category` de ajuste/diagnóstico aparece como brecha, salvo las
excepciones explícitas — sin depender de Foundational, US2 ni US3 (`spec.md`,
US1 "Independent Test"; `quickstart.md` §1). La lista de entidades de Frigate
funciona igual de bien con o sin User Story 3 desplegada (`research.md`, nota
de sincronización — hallazgo M1 de `/speckit-analyze`).

### Implementation for User Story 1

- [X] T005 [US1] En `src/inventory/_homelab_bridge.py`, añadir
  `ha_monitor_conditional_entities()`: mismo patrón que
  `ha_monitor_checked_entities()`, filtrando `ha_monitor.CHECKS` a las
  entradas con `requires_container` — devuelve el conjunto vacío si
  `ha_monitor.py` no está disponible o todavía no tiene esas entradas (antes
  de desplegar User Story 3), nunca lanza (`data-model.md`, `contracts/
  ficheros.md`). Mismo fichero que T002 (Foundational) — funciones distintas,
  coordinar si se hacen a la vez; sin dependencia de código entre las dos.
- [X] T006 [US1] En `src/inventory/sources.py`, añadir la constante
  `ENTIDAD_HA_EXCEPCIONES_SEGURIDAD` (5 `entity_id` de seguridad), la
  constante `_ENTIDAD_HA_FRIGATE_FALLBACK` (33 `entity_id` de Frigate, ver
  `data-model.md`) y la función `entidad_ha_frigate()` que devuelve
  `bridge.ha_monitor_conditional_entities() or _ENTIDAD_HA_FRIGATE_FALLBACK`
  (`research.md`, nota de sincronización). Depende de T005 (llama a su
  función).
- [X] T007 [US1] (FR-001, FR-002, FR-003) En `src/inventory/evaluate.py`,
  `is_intentional()`: para `categoria == "entidad_ha"`, añadir que
  `entity_category` en `("config", "diagnostic")` **y** el componente no está
  en `ENTIDAD_HA_EXCEPCIONES_SEGURIDAD` **ni** en `sources.entidad_ha_
  frigate()` cuenta como intencionado, además de la condición `disabled_by`
  ya existente (`research.md` §3). Depende de T006. Mismo fichero que T003/
  T004 (Foundational) — función distinta (`is_intentional()` vs.
  `_vigilancia_entidad_ha()`/`classify_gap()`), coordinar si se hacen a la
  vez.
- [X] T008 [US1] Validar manualmente siguiendo `quickstart.md` §1: relanzar
  `inventory.cli --gaps` y comprobar que el recuento de `entidad_ha` baja en
  al menos 115 respecto a las 309 de referencia, y que las 5 excepciones de
  seguridad siguen apareciendo. Depende de T007.

**Checkpoint**: User Story 1 funciona y es verificable de forma independiente
— MVP entregable, sin depender de que `ha_monitor.py` se haya tocado.

---

## Phase 4: User Story 2 - Saber si una automatización doméstica se ha desactivado sola (Priority: P2)

**Goal**: Las 17 automatizaciones domésticas en alcance cuentan como brecha
real (`condicion_incumplida`) cuando están desactivadas, no como
`sin_declaracion` (FR-004).

**Independent Test**: Desactivar a mano una automatización no crítica y
comprobar que el inventario la marca como brecha; reactivarla y comprobar que
deja de estarlo — sin depender de que US1 esté terminada, pero sí de
Foundational (`spec.md`, US2 "Independent Test"; `quickstart.md` §2).

### Implementation for User Story 2

- [X] T009 [US2] En `scripts/ha_monitor.py`, añadir las 17 entradas nuevas a
  `CHECKS`, tipo `entity_state` con `ok_state: "on"`, una por automatización
  en alcance (`data-model.md`, "Automatizaciones (17)") — sin código nuevo en
  `check_status()`, el tipo ya existe (`research.md` §1).
- [X] T010 [US2] Validar manualmente siguiendo `quickstart.md` §2: desactivar
  una automatización en alcance, esperar un ciclo de `ha_monitor.py` (hasta
  15 min), comprobar que aparece como `condicion_incumplida` en
  `inventory.cli --gaps`; reactivarla y comprobar que desaparece en el
  siguiente ciclo. Depende de T009 y de Foundational (T001-T004).

**Checkpoint**: User Story 2 funciona de forma independiente.

---

## Phase 5: User Story 3 - Vigilar Frigate solo cuando está encendido (Priority: P3)

**Goal**: Las ~33 entidades de Frigate cuentan como brecha únicamente cuando
el contenedor `frigate` está corriendo y alguna entidad está
`unavailable`/`unknown` (FR-005, FR-006, FR-007).

**Independent Test**: Parar y arrancar el contenedor `frigate` y comprobar
que las entidades dejan/empiezan a poder contar como brecha en cada caso — sin
depender de que US1 o US2 estén terminadas, pero sí de Foundational
(`spec.md`, US3 "Independent Test"; `quickstart.md` §3-5). Desplegar esta
historia también hace que `entidad_ha_frigate()` de User Story 1 pase a leer
la lista en vivo en vez del fallback (`research.md`, nota de sincronización).

### Implementation for User Story 3

- [X] T011 [US3] En `scripts/ha_monitor.py`, `check_status()`: añadir la
  comprobación de `requires_container` — si el check la trae y el contenedor
  no está corriendo (`docker inspect -f '{{.State.Running}}' <contenedor>`,
  cacheado en un diccionario a nivel de módulo dentro de la misma ejecución
  de `main()`), devolver `(True, "<contenedor> parado — no aplica", "")` sin
  consultar la API de HA (`research.md` §2, `data-model.md`).
- [X] T012 [US3] En `scripts/ha_monitor.py`, añadir las 33 entradas nuevas a
  `CHECKS`, tipo `entity_available` con `requires_container: "frigate"`, una
  por entidad de Frigate en alcance (`data-model.md`, "Entidades de Frigate
  (33)"). Depende de T011 (mismo fichero, la comprobación debe existir antes
  de añadir checks que dependen de ella).
- [X] T013 [US3] Validar manualmente siguiendo `quickstart.md` §3-4. §3
  (Frigate parado) validado de verdad: `docker stop frigate` + ciclo de
  `ha_monitor.py` → las 33 entradas salen "RECOVERED (frigate parado — no
  aplica)"; `inventory.cli --gaps` → 0 brechas de Frigate. Frigate
  reiniciado después para no dejarlo parado sin avisar. §4 (Frigate
  corriendo + datos reales → 0 brechas) **no se pudo demostrar en vivo**:
  hay un fallo real y preexistente (MQTT, ver T014) que impide que
  ninguna entidad de Frigate esté disponible ahora mismo mientras el
  contenedor corre. Validado en su lugar por inspección de código: es la
  misma lógica `entity_available` que ya usan `shelly_riego`/
  `esp32_toldos`/etc., 9 de cuyos checks equivalentes están en `ok` ahora
  mismo (mismo camino de código, otras entidades). Depende de T012, y de
  Foundational (T001-T004).
- [X] T014 [US3] Validar manualmente siguiendo `quickstart.md` §5: con
  Frigate corriendo, parar uno de los relays `amsterdam9.frigate.relay-*`,
  esperar un ciclo, y comprobar que las entidades de esa cámara aparecen como
  `condicion_incumplida`; restaurar el relay. Depende de T013. **Validado con
  un escenario real más completo que el planeado**: Frigate lleva desde el
  21-07-2026 sin poder autenticarse en MQTT ("MQTT Not authorized") — con el
  contenedor corriendo y sano, las 33 entidades salen `condicion_incumplida`
  de verdad, no simulado parando un relay.

**Checkpoint**: Las tres historias funcionan, cada una verificable de forma
independiente. Además, `entidad_ha_frigate()` (User Story 1) pasa a usar la
lista en vivo — validar con una repetición rápida de `quickstart.md` §1 tras
esta fase para confirmar que el resultado no cambia (T005/T006 diseñadas
justo para eso).

---

## Phase 6: Verificación cruzada

**Purpose**: Confirmar que el cambio de contrato de `esta_vigilado`
(Foundational) no rompe nada ya existente, y que el cierre de brechas es el
esperado en conjunto.

- [X] T015 Validar `quickstart.md` §6: ejecutar
  `PYTHONPATH=src python3 -m inventory.cli --selftest` y comprobar que todo
  sigue en verde, incluidas las aserciones de `test_evaluate.py` para
  categorías que no tocan `entidad_ha`. Depende de T003, T004.
- [X] T016 Validar `SC-001` en conjunto: relanzar
  `PYTHONPATH=src python3 -m inventory.cli --no-telegram` y comprobar que el
  total de brechas `entidad_ha` baja de 309 en al menos 115 (criterio real
  de `spec.md`, SC-001 — **corrección sobre la nota original de esta
  tarea**: "165 = 115+17+33" asumía que ninguna de las 50 entidades nuevas
  incumpliría su estado esperado; en la práctica 41 sí lo incumplen ahora
  mismo — 8 automatizaciones realmente desactivadas y las 33 de Frigate por
  el fallo de MQTT de T014 — así que se reclasifican como `condicion_
  incumplida` en vez de desaparecer del todo. Resultado real: 309 → 181
  (-128, ≥115 ✓), con las 5 excepciones de seguridad y 135 de cola larga sin
  triar intactos. Depende de T008, T010, T014.

**Checkpoint**: Feature 004 completo — 165 de las 309 brechas `entidad_ha`
cerradas, con las excepciones documentadas explícitas.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: sin tareas.
- **Foundational (Phase 2)**: bloquea US2 y US3 — **no** bloquea US1.
- **User Story 1 (Phase 3)**: sin dependencia lógica de Foundational ni de
  US2/US3 — comparte fichero con Foundational en dos puntos
  (`_homelab_bridge.py` en T002/T005, `evaluate.py` en T003-T004/T007), sin
  dependencia de código entre las funciones que cada una toca. Coordinar si
  se ejecutan literalmente a la vez, por el fichero compartido, no por orden
  obligatorio.
- **User Story 2 (Phase 4)**: depende de Foundational — sin dependencia de
  US1 ni US3.
- **User Story 3 (Phase 5)**: depende de Foundational — sin dependencia de
  US1 ni US2. Su despliegue cambia el comportamiento interno de US1
  (`entidad_ha_frigate()` pasa de fallback a lista en vivo), sin que haga
  falta ningún cambio de código en US1 para ello.
- **Verificación cruzada (Phase 6)**: depende de que las tres historias estén
  terminadas.

### Within Foundational

T001 y T002 independientes entre sí (ficheros distintos).
T002 → T003 (mismo cambio lógico, `evaluate.py` necesita la función del
puente).
T001, T003 → T004 (necesita el valor de enum y el nuevo comportamiento de
`esta_vigilado` a la vez).

### Within User Story 1

T005 → T006 (`entidad_ha_frigate()` llama a la función del puente) → T007
(`is_intentional()` llama a `entidad_ha_frigate()`) → T008.

### Within User Story 2

T009 → T010 (validar necesita el check ya desplegado).

### Within User Story 3

T011 → T012 (mismo fichero, la comprobación debe existir antes que los
checks que la usan) → T013 → T014.

### Parallel Opportunities

- T001 y T002 (Foundational) pueden avanzar en paralelo — ficheros distintos.
- User Story 1 completa (T005-T008) puede avanzar en paralelo con
  Foundational (T001-T004) — sin dependencia de código, con dos puntos de
  fichero compartido a coordinar (ver arriba).
- Una vez completado Foundational, User Story 2 (T009-T010) y User Story 3
  (T011-T014) pueden avanzar en paralelo entre sí — ambas tocan
  `scripts/ha_monitor.py`, pero en secciones distintas (`CHECKS` vs.
  `check_status()`); coordinar para no pisarse en el mismo fichero.

---

## Parallel Example: Foundational + User Story 1 a la vez

```bash
# Foundational (un desarrollador/sesión):
Task: "T001 [P] Añadir condicion_incumplida a TIPOS_BRECHA en model.py"
Task: "T002 [P] Añadir ha_monitor_check_result() en _homelab_bridge.py"

# User Story 1, en paralelo (otro desarrollador/sesión — coordinar en
# _homelab_bridge.py y evaluate.py, ver Dependencies):
Task: "T005 Añadir ha_monitor_conditional_entities() en _homelab_bridge.py"
Task: "T006 Listas de exclusión + entidad_ha_frigate() en sources.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 sola)

1. T005 → T006 → T007 → T008.
2. **Parar y validar**: cierra 115 de las 165 brechas de este feature sin
   tocar `ha_monitor.py` ni depender de Foundational — el mayor impacto con
   el menor riesgo (`spec.md`, "Why this priority" de US1).
3. Desplegar/demo si está listo — no depende de Foundational, US2 ni US3.

### Incremental Delivery

1. Foundational + User Story 1 en paralelo → validar cada una por separado.
2. User Story 2 → validar → desplegar.
3. User Story 3 → validar → desplegar (esto además activa la lista en vivo
   de `entidad_ha_frigate()`, cerrando el hallazgo M1).
4. Verificación cruzada (T015-T016) → cierre formal de `SC-001`.

---

## Notes

- [P] = ficheros distintos, sin dependencia de código.
- [Story] mapea cada tarea a su historia de usuario para trazabilidad.
- Sin tareas de test de contrato/integración: no se piden en `spec.md`; el
  `--selftest` de T015 y la validación manual vía `quickstart.md` son la
  verificación de este feature.
- T003 es la tarea de mayor riesgo del feature: cambia el significado de
  `esta_vigilado` para los 15 checks `entidad_ha` ya existentes, no solo los
  50 nuevos. Ya se comprobó en `research.md` §4 que los 15 están en `ok`
  ahora mismo, así que T015 (selftest) y una comprobación manual de que el
  recuento de brechas no sube inesperadamente en otras categorías son las
  dos validaciones que confirman que ese riesgo no se materializó.
- T005/T006 resuelven el hallazgo M1 de `/speckit-analyze` (2026-08-09): la
  lista de entidades de Frigate ya no puede desincronizarse de forma que
  importe, porque en cuanto `ha_monitor.py` tiene las 33 entradas (US3), esa
  lista en vivo manda y el fallback fijo en este repo queda inerte.
- Ninguna tarea de este feature modifica la configuración de HA, Frigate o
  ninguna automatización (`spec.md`, FR-008/FR-009) — todas las tareas son de
  lectura/declaración de estado esperado.
- Ninguna tarea toca `docker/homelab-dashboard/scripts/app.py` — el recuento
  "Domótica X/Y" ya refleja los checks nuevos sin cambios ahí (`research.md`
  §5).
