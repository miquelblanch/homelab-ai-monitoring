# Data Model — Inventario Sistemático de Cobertura del Homelab

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Persistencia: SQLite, tablas nuevas junto a `homelab.db` (ver
`research.md` §2). Todas las tablas de este feature son **append-only**
salvo donde se indique lo contrario (Clarification 2 — sin límite de
tiempo, sin purga).

## Entidades

### `componentes`

Registro canónico de cada **Componente del homelab** (spec, Key Entities)
detectado alguna vez. Una fila por componente conocido, no por ejecución.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | interno |
| `categoria` | TEXT | `contenedor` \| `integracion` \| `entidad_ha` \| `host_externo` \| `hermes` \| `telegram` \| `infra_monitorizacion` (FR-001 a FR-006) |
| `nombre_actual` | TEXT | último nombre visto |
| `identificador_estable` | TEXT NULL | nombre de contenedor/servicio compose para Docker, `unique_id` para entidades HA, `NULL` si la fuente no ofrece ninguno (research.md §3) |
| `origen_sin_id_estable` | BOOLEAN | `true` cuando `identificador_estable` es `NULL` a propósito — un cambio de nombre futuro se tratará como baja+alta (FR-015, Clarification 1) |
| `primera_ejecucion_id` | FK → `ejecuciones.id` | cuándo se vio por primera vez |
| `es_intencionadamente_no_vigilado` | BOOLEAN | `frigate`, entidad muda de la cerradura, y equivalentes (FR-012) |
| `last_reviewed_at` | DATE NULL | última revisión confirmada por Miquel del estado esperado declarado — base de la caducidad a 90 días (FR-007, Clarification 3) |

**Regla de identidad** (Clarification 1): al procesar una ejecución nueva,
un elemento detectado se empareja con una fila existente de `componentes`
por `identificador_estable` si la fuente lo ofrece; si no, por
`nombre_actual` exacto. Si no hay coincidencia por ninguna vía, es un
componente nuevo (alta). Si un componente conocido no aparece en la
ejecución actual y su fuente no tiene identificador estable, no se borra:
queda como candidato a "baja", visible en el diff (FR-015).

### `hallazgos`

Una fila por componente **y** por ejecución: la respuesta a las tres
preguntas en ese momento. Es el detalle que junto compone el listado
completo de `User Story 1`.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `ejecucion_id` | FK → `ejecuciones.id` | |
| `componente_id` | FK → `componentes.id` | |
| `tiene_estado_declarado` | BOOLEAN | FR-007 |
| `estado_declarado_status` | ENUM | `vigente` \| `caducada` \| `ausente` (FR-007, umbral de 90 días) |
| `esta_vigilado` | BOOLEAN | FR-008 |
| `mecanismo_vigilancia` | TEXT NULL | qué lo vigila, p. ej. `docker_monitor.py`, `ha_monitor.py`, `beszel` — `NULL` si `esta_vigilado` es falso (FR-008) |
| `llega_a_dashboard` | ENUM | `si` \| `no` \| `sin_evidencia` (FR-009) |
| `es_brecha` | BOOLEAN | derivado: falso si `es_intencionadamente_no_vigilado` es verdadero en `componentes`, o si las tres respuestas son plenamente satisfactorias; verdadero en cualquier otro caso (FR-010, FR-012) |

**Regla de completitud** (FR-010): no puede existir una fila de
`hallazgos` con algún campo de las tres preguntas sin valor — el "sin
evidencia" de `llega_a_dashboard` es un valor válido, un `NULL` no lo es.

### `brechas`

Vista derivada de `hallazgos` filtrada a `es_brecha = true`, más el
seguimiento de continuidad entre ejecuciones que pide `FR-011` y `FR-015`.
Se modela como tabla (no vista SQL pura) para poder guardar
`primera_ejecucion_id` de forma barata.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `hallazgo_id` | FK → `hallazgos.id` | |
| `tipo` | ENUM | `sin_declaracion` \| `declaracion_caducada` \| `sin_vigilancia` \| `no_llega_a_dashboard` \| `riesgo_concentrado_telegram` (Edge Case FR-006) |
| `primera_ejecucion_id` | FK → `ejecuciones.id` | si coincide con `ejecucion_id` del hallazgo actual, es una brecha **nueva**; si no, es **conocida** (FR-011, FR-015) |
| `conocida_por_barrido_previo` | TEXT NULL | referencia libre a `BARRIDO-*.md` si aplica — poblada a mano desde un mapeo curado (`tasks.md` T039), no detectada automáticamente por coincidencia de texto (User Story 2, escenario 2) |
| `contexto` | TEXT | explicación suficiente para decidir sin reinvestigar (FR-011) |

### `ejecuciones`

Una fila por **Ejecución del inventario** (spec, Key Entities). Nunca se
borra ni se purga (Clarification 2).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `fecha` | DATETIME | inicio de la ejecución |
| `disparador` | ENUM | `manual` \| `programado` (FR-014) |
| `total_componentes` | INTEGER | tamaño del snapshot, para `SC-001` |
| `total_brechas` | INTEGER | para `SC-002` (comparación contra la línea base de 11) |
| `es_linea_base_referencia` | BOOLEAN | marca la ejecución que representa el barrido 2026-08-01 a efectos de `SC-002`, si se llega a cargar retroactivamente; de lo contrario la comparación es literal contra el número 11 (Principio IX) |

## Relaciones

```
ejecuciones (1) ──< hallazgos >── (1) componentes
hallazgos (1) ──< brechas
componentes (1) ──< brechas.primera_ejecucion_id (vía ejecuciones)
```

## Transiciones de estado

- **Declaración**: `ausente → vigente` (Miquel la declara) → `caducada`
  (pasan 90 días sin `last_reviewed_at` actualizado) → `vigente` (Miquel la
  revisa y confirma) — nunca "caducada → ausente" automáticamente; alguien
  tiene que borrar la declaración a propósito.
- **Brecha**: `nueva` (su `primera_ejecucion_id` coincide con la ejecución
  actual) → `conocida` (aparece de nuevo en una ejecución posterior) →
  desaparece del listado filtrado cuando `hallazgos.es_brecha` pasa a falso
  en una ejecución (no se borra la fila histórica, solo deja de aparecer
  como brecha activa — Principio VIII, registro de lo que pasó).
- **Componente**: `nuevo` (alta) → `activo` → `de baja` (no aparece en la
  ejecución más reciente y no tiene identificador estable para reconciliar,
  o su fuente confirma la baja explícitamente, p. ej. `docker ps` ya no lo
  lista) — un componente de baja no se borra de `componentes`, para no
  perder su historial de `hallazgos`.

## Validación derivada de los requisitos

- FR-001 a FR-006 → `categoria` debe cubrir las seis familias de origen; la
  ausencia de una fila para cualquier contenedor/integración/entidad/host
  conocido en la última ejecución es en sí misma detectable comparando
  contra el `docker ps` / listado de fuentes real en tiempo de ejecución
  (no es un chequeo que viva en el modelo, sino en la lógica de `sources.py`
  descrita en `plan.md`).
- FR-007/FR-009/FR-010 → constraints `NOT NULL` en los tres campos de
  respuesta de `hallazgos` salvo los que tienen un valor "vacío" legítimo
  ya modelado como enum (`ausente`, `sin_evidencia`).
- FR-012 → `componentes.es_intencionadamente_no_vigilado` excluye la fila
  de `brechas` aunque sus respuestas en `hallazgos` no serían
  satisfactorias por sí solas.
- FR-015 → la regla de identidad de `componentes` (arriba) es la única
  fuente de verdad para "mismo componente entre ejecuciones".
- FR-017 → ninguna migración de este feature incluye una operación de
  purga sobre `ejecuciones`, `hallazgos`, `brechas` o `componentes`.
