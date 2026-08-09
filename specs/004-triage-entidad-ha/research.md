# Research — Triaje de Brechas `entidad_ha`

**Feature**: [spec.md](./spec.md) · **Fecha**: 2026-08-09

Cada decisión se contrastó contra el código real — `ha_monitor.py`,
`src/inventory/{evaluate,sources,model}.py`,
`docker/homelab-dashboard/scripts/app.py` — y contra el estado real de
`ha_monitor_state.json` (los 15 checks actuales, todos en `ok` el
2026-08-09, comprobado en vivo antes de decidir el punto 4).

## 1. Automatizaciones domésticas (17) — qué tipo de check (FR-004)

**Decision**: 17 entradas nuevas en `ha_monitor.CHECKS`, tipo
`entity_state` con `ok_state: "on"` — el mismo tipo que ya usa
`z2m_bridge`. Sin código nuevo en `check_status()`.

**Rationale**: el tipo `entity_state` ya existe y ya compara
`state == check["ok_state"]` — una automatización de HA expone
exactamente ese contrato (`state` es `on`/`off`). Cero superficie nueva.

**Alternatives considered**: un check type dedicado a automatizaciones —
descartado, `entity_state` ya sirve tal cual.

## 2. Entidades de Frigate (33) — cómo condicionar al contenedor (FR-005, FR-006, FR-007)

**Decision**: 33 entradas nuevas en `ha_monitor.CHECKS`, tipo
`entity_available` (ya existe), más un campo nuevo `requires_container:
"frigate"`. `check_status()` gana una comprobación previa: si el check
trae `requires_container` y ese contenedor no está corriendo, devuelve
`(True, "<contenedor> parado — no aplica", "")` sin llegar a consultar
HA — mismo contrato de retorno `(ok, detalle, motivo)` que ya usan los
otros tipos, sin tocar su forma.

**Cómo se comprueba "¿está corriendo?"**: `subprocess.run(["docker",
"inspect", "-f", "{{.State.Running}}", "frigate"])`, cacheado en un
diccionario a nivel de módulo la primera vez que se pide dentro de una
misma ejecución de `main()` — evita 33 llamadas a `docker inspect` por
ciclo de 15 min, sin necesitar coordinación entre procesos (el caché
vive y muere con cada ejecución del cron).

**Rationale**: `entity_available` ya hace exactamente lo que hace falta
para 32 de las 33 (¿tiene un valor, o está `unavailable`/`unknown`?) —
la única pieza que faltaba es el "y solo si Frigate está encendido",
que se resuelve con una comprobación añadida al dispatcher, no con un
tipo de check nuevo. `docker inspect` es el mismo patrón sin
dependencias que ya usan `docker_monitor.py` y
`beszel_hosts_monitor.py` — no se introduce Docker SDK ni nada nuevo.

**Alternatives considered**:
- Comprobar el contenedor una vez por cada uno de los 33 checks sin
  caché — descartado por ineficiente sin necesidad (33× `docker
  inspect` cada 15 min es un coste evitable con una línea).
- Un check "agregado" único que resuma las 33 entidades en una sola fila
  — descartado: rompe el patrón ya establecido en este mismo fichero de
  una fila por entidad (los 8 checks de batería, por ejemplo, no están
  agregados), y pierde el detalle de cuál falló.

## 3. `entity_category` como intencionado (FR-001, FR-002, FR-003)

**Decision**: `is_intentional()` en `evaluate.py`, rama `entidad_ha`,
gana una segunda condición además de `disabled_by`: `entity_category`
en `("config", "diagnostic")` **y** el componente no está en las 5
excepciones de seguridad **ni** es una de las entidades de Frigate
(esas se rigen por el punto 2, no por esta regla). La lista de
excepciones de seguridad es una constante fija en `sources.py` (no
tiene otra fuente de verdad posible). La lista de entidades de Frigate
**no** es una constante fija a secas — ver la nota de sincronización
más abajo.

**Rationale**: `entity_category` ya viaja en `raw.meta` desde
`sources.py` (feature 001) — no hace falta ninguna lectura adicional al
registro de HA, solo una condición más en una función que ya existe.

**Alternatives considered**: una lista fija de ~115 `entity_id` copiada
a mano — descartada explícitamente: se recalcula sola si HA reclasifica
una entidad en el futuro (Edge Cases de `spec.md`), una lista fija no.

**Nota de sincronización (hallazgo M1 de `/speckit-analyze`,
2026-08-09)**: las 33 entidades de Frigate también aparecen en
`ha_monitor.CHECKS` (punto 2) — dos copias de la misma lista, una en
este repo (`sources.py`) y otra en el script privado, sin comprobación
automática de que coincidan. Una entidad de Frigate añadida a un sitio
sin el otro caería por la regla genérica de `entity_category` en vez de
por la lógica condicionada al contenedor — un fallo silencioso.

**Decision (revisada)**: en vez de una constante fija, `sources.py`
expone una función `entidad_ha_frigate()` que **prioriza la lista en
vivo** — `bridge.ha_monitor_conditional_entities()` (nueva, lee
`requires_container` de `ha_monitor.CHECKS`, punto 2) — y solo cae a la
constante fija (`_ENTIDAD_HA_FRIGATE_FALLBACK`, ver `data-model.md`)
cuando esa lista en vivo está vacía. Antes de desplegar User Story 3
(`ha_monitor.py` todavía sin las 33 entradas), la lista en vivo está
vacía y se usa el fallback — preserva la independencia de User Story 1
(`spec.md`, "Independent Test"). Después de desplegar User Story 3, la
lista en vivo deja de estar vacía y pasa a mandar — la copia fija en
`sources.py` deja de ser la fuente activa, así que ya no puede
desincronizarse de forma que importe (una futura limpieza podría
retirarla, no bloqueante para este feature).

## 4. `esta_vigilado` para `entidad_ha`: de "está en la lista" a "está sano ahora" (hallazgo central)

**El problema encontrado al diseñar FR-004/FR-006**: hoy,
`_vigilancia_entidad_ha()` en `evaluate.py` es:

```python
checked = raw.componente.nombre_actual in bridge.ha_monitor_checked_entities()
return checked, checked, (...)
```

Es decir, `esta_vigilado` es *pura membresía* en `ha_monitor.CHECKS` —
no mira si el check está pasando o fallando ahora mismo. Es el mismo
patrón que usa `_vigilancia_por_heartbeat()` para `infra_monitorizacion`
(mide si el vigilante está vivo, nunca si lo vigilado está sano). Con
ese modelo, una automatización apagada seguiría marcando
`esta_vigilado=True` para siempre en cuanto se añadiera a `CHECKS` — el
inventario nunca reflejaría que está incumpliendo su estado esperado,
justo lo contrario de lo que pide el escenario 2 de `User Story 2`
("aparece como brecha real, no como 'sin declaración'").

**Decision**: `_vigilancia_entidad_ha()` pasa a leer el resultado real
del check desde `ha_monitor_state.json` (vía una función nueva en
`_homelab_bridge.py`, `ha_monitor_check_result(entity_id)`, que mapea
`entity_id → id de check` a partir de `ha_monitor.CHECKS` y devuelve la
entrada de estado correspondiente). `esta_vigilado` pasa a ser el `ok`
real del último ciclo, no la membresía.

**Por qué se aplica a los 15 checks existentes también, no solo a los
50 nuevos**: separar la lógica en dos caminos (membresía para los 15
antiguos, resultado real para los 50 nuevos) sería más código y una
inconsistencia dentro de la misma categoría sin ningún beneficio — el
propio significado de "vigilado" pasa a ser uniforme y más correcto
para los 65. Se comprobó el riesgo antes de decidirlo: los 15 checks
actuales están todos en `ok` en este momento (2026-08-09), así que este
cambio no genera ninguna brecha nueva de golpe sobre los ya existentes.

**Consecuencia en el tipo de brecha**: con este cambio, una entidad
`declarada=True` (está en `CHECKS`) pero `vigilado=False` (el check
falla ahora mismo) caía hoy en `classify_gap()` bajo `"sin_vigilancia"`
— cuyo mensaje ("no está vigilado por ningún mecanismo conocido") sería
falso: sí está vigilado, es que está fallando. Se añade un tipo de
brecha nuevo, `condicion_incumplida` (`model.py::TIPOS_BRECHA`), con su
propio mensaje en `gap_context()` — ver `data-model.md`.

**Alternatives considered**: dejar `esta_vigilado` como membresía y
usar otro campo para "incumple lo esperado" — descartado, habría creado
un segundo eje de brecha paralelo al que ya existe (`tiene_estado_
declarado` / `esta_vigilado` / `llega_a_dashboard`) en vez de encajar
en el modelo de tres preguntas ya establecido.

## 5. Por qué este feature no toca `app.py` (Constraints)

**Decision**: ninguno de los 50 checks nuevos necesita una tarjeta
dedicada en el dashboard. `llega_a_dashboard="si"` se calcula igual que
hoy (`"si" if vigilado else "no"`), y es honesto sin cambiar `app.py`
porque el recuento "Domótica X/Y" del panel (`haIds.length`/
`haOkCount`) ya itera **todas** las claves de `ha_monitor_state.json`
(`Object.keys(haChecks)`), no una lista fija — comprobado en el código
de `app.py` línea 1898-1899. Los 50 checks nuevos ya mueven ese número
en cuanto existen, sin ninguna edición del dashboard.

**Rationale**: las tarjetas individuales (`HA_CONNECTIVITY_IDS`,
`HA_DEVICE_IDS`, `HA_BATTERY_IDS`) sí son listas fijas y no mostrarán
las 50 entidades nuevas una a una — pero `spec.md` no pide eso
(`FR-009`, ninguna interfaz nueva); pide que Miquel pueda saberlo "sin
revisar Home Assistant a mano", y eso ya lo cubren el recuento agregado
y el aviso de Telegram que `ha_monitor.py` ya manda en cada cambio de
estado, sin cambio de `app.py`.

**Alternatives considered**: añadir las 50 a las listas fijas para que
tengan tarjeta propia — descartado, fuera del alcance que pide `spec.md`
y engordaría innecesariamente 3 secciones del dashboard con datos de
baja frecuencia de cambio (automatizaciones domésticas, Frigate cuando
está parado casi siempre).
