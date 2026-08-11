# Research — Visor de Diagnósticos en Alarmas

**Feature**: [spec.md](./spec.md)

## §1 — Lectura de `diagnostico.db`: mismo patrón `mode=ro` que `speedtest.db`

**Decisión**: `sqlite3.connect(f"file:{DIAGNOSTICO_DB_PATH}?mode=ro", uri=True, timeout=3)`,
exactamente el patrón que `app.py` ya usa para leer `speedtest.db` (única
lectura SQLite existente en el dashboard hasta ahora). `DIAGNOSTICO_DB_PATH`
por defecto `/data/diagnostico.db` (mismo directorio que
`inventario.db`/`homelab.db`, ya montado — confirmado en vivo:
`docker exec homelab-dashboard ls /data/` muestra `diagnostico.db`,
81920 bytes, escrito por la validación real de 007).

**Rationale**: reutilizar exactamente lo que ya existe en vez de
inventar un segundo patrón de lectura SQLite en el mismo fichero.

**Alternativas consideradas**: leer con `sqlite3.connect()` normal (sin
`mode=ro`). Rechazada — `mode=ro` ya es el patrón establecido en este
fichero para bases ajenas, y no hay ninguna razón para desviarse aquí
(a diferencia de `research.md` §4 de 007, que rechazó `mode=ro` contra
`homelab.db` por un problema de ruta de red — `diagnostico.db` aquí se
lee desde dentro del mismo contenedor donde vive el fichero, sin ese
problema).

## §2 — Emparejamiento: `down_since` ya es el ancla, no hace falta aproximarlo

**Hallazgo real, no anticipado al escribir el spec ni al proponer
"Alarmas" a Miquel**: la alarma de un contenedor caído no solo lleva
`antiguedad_s` (segundos transcurridos, recalculado en cada petición) —
`get_active_alarms()` lo calcula a partir de un timestamp real,
`down_since`, que `get_containers()` ya lee de
`docker_monitor_state.json` (`_parse_iso_age_s(c.get("down_since"))`,
`app.py`). Ese timestamp real existe y es exactamente el ancla que este
feature necesita: el momento en que la caída actual empezó.

**Decisión**: la función nueva recibe `down_since` directamente (no
`antiguedad_s`, que ya perdió el timestamp original al convertirse en
segundos) y busca en `episodios` (mismo `contenedor`) el que tenga
`ventana_inicio` más próxima a `down_since`, dentro de una tolerancia
de **30 minutos** — mismo orden de magnitud que la ventana de
`container_metrics` que ya usa `congelar --historico` (research.md §5
de 007). Si el episodio más próximo cae fuera de esa tolerancia, o es
anterior a `down_since` por más margen del razonable (Clarifications
Q2 — nunca mostrar una caída anterior ya resuelta), no se muestra
ningún diagnóstico.

**Sobre zonas horarias — más simple de lo que parecía con "Correcciones"**:
`down_since` lo escribe `docker_monitor.py`, que corre directamente en
el host (Mac Mini) — misma convención de hora local sin marca de zona
que `episodios.ventana_inicio`/`ventana_fin` (ambos derivan, directa o
indirectamente, de `container_metrics.timestamp`; confirmado en vivo:
última muestra `2026-08-11T18:56:39` coincide con `date` local, no con
`date -u`). **No hace falta ninguna conversión de zona horaria para
emparejar** — a diferencia del descarte de diseño sobre "Correcciones"
(que sí la habría necesitado, por `alarm_history.json` calcularse
dentro de un contenedor en UTC). Sigue haciendo falta normalizar
`diagnosticos.creado_en` (UTC explícito, `store.py` de 007) al mostrar
la fecha del intento de diagnóstico (FR-005) — ver §4.

**Rationale**: usar el timestamp real ya existente es estrictamente
mejor que reconstruir uno aproximado a partir de `antiguedad_s` (que
además cambia en cada petición según cuándo se calcule, mientras que
`down_since` es estable mientras la caída siga activa).

**Alternativas consideradas**: aproximar el inicio de la caída con
`ahora - antiguedad_s`. Rechazada tras encontrar que `down_since` ya
existe sin necesidad de aproximar nada — más preciso y más simple.

## §3 — Algoritmo de emparejamiento, versión final (corregida contra un caso real)

**Corrección durante `/speckit-implement` (2026-08-11)**: la primera
versión de este algoritmo comparaba `down_since` contra un único punto,
`ventana_inicio`. Probado contra un episodio real `congelar --vivo`
(minipaint, episodio 14), **falló** el caso de uso más común de este
feature — diagnosticar en vivo poco después de que empezara la caída:
`ventana_inicio` de un episodio `--vivo` es el principio de **todo el
contexto de métricas disponible** (hasta ~1h antes del momento de
congelar, `evidencia.py` de 007), no el inicio real de la caída. Con
`down_since` a solo 2 minutos de `ventana_fin` pero a una hora larga de
`ventana_inicio`, la distancia a un solo punto lo rechazaba en falso.

**Algoritmo corregido** — distancia al **rango** `[ventana_inicio,
ventana_fin]`, no a un punto:

1. Buscar en `episodios` (mismo `contenedor` que `componente`) el que
   minimice la distancia de `down_since` al rango
   `[ventana_inicio, ventana_fin]` — `0` si `down_since` cae dentro del
   rango (cubre el caso `--vivo` de arriba, y también `--historico`,
   cuya ventana está centrada en el evento real); si cae fuera, la
   distancia al borde más próximo.
2. Si esa distancia está dentro de 30 minutos, es el episodio de esta
   caída — usarlo (si hay varios dentro de esa tolerancia, el de
   `creado_en` más reciente, spec.md Edge Cases).
3. Si la distancia supera 30 minutos, no se muestra ningún diagnóstico
   — incluye tanto "ningún episodio existe todavía" como "el episodio
   más cercano es de una caída anterior ya resuelta" (Clarifications
   Q2) — se trata igual que "sin episodio asociado" (spec.md FR-007).
4. Con el episodio elegido, tomar su intento de diagnóstico
   (`diagnosticos`) más reciente (`creado_en` más alto) — spec.md
   FR-005.

**Rationale**: FR-001/FR-004 exigen explícitamente que el episodio
corresponda a la caída actual, no a cualquier caída pasada del mismo
contenedor — la distancia-al-rango con tolerancia acotada sigue
trazando esa línea sin ambigüedad, y además cubre correctamente el caso
`--vivo` que el diseño original no anticipó. Verificado en vivo
(2026-08-11): con la corrección, el episodio 14 (minipaint, `--vivo`)
empareja correctamente; los casos que ya funcionaban (`beszel`, caída
antigua fuera de tolerancia → `None`) siguen funcionando igual.

**Alternativas consideradas**: ampliar solo la tolerancia (por ejemplo,
a 90 minutos) en vez de cambiar la métrica de distancia. Rechazada —
no resuelve el problema de fondo (la asimetría del rango `--vivo`) y
además debilita la garantía de SC-006 al aceptar coincidencias más
lejanas también para el caso `--historico`, donde sí importa la
precisión.

## §4 — Normalización de fechas para mostrar (FR-005, SC-005)

**Corrección tras probar contra `diagnostico.db` real (2026-08-11,
durante `/speckit-implement`)**: `episodios.creado_en` **no** es hora
local sin marca, como decía la versión anterior de este párrafo —
confirmado con una fila real: `'2026-08-10T12:59:34.678434+00:00'`, con
offset UTC explícito. Usa el mismo `_now_iso()` de `store.py` que
`diagnosticos.creado_en` — ambos campos `creado_en` (el momento en que
`diagnostico.cli` persistió la fila) son UTC; solo
`episodios.ventana_inicio`/`ventana_fin` (el momento real del episodio,
derivado de `container_metrics` vía `evidencia.py`) son hora local sin
marca. §2 de este documento seguía aplicando bien la distinción
correcta para el **emparejamiento** (`down_since` vs `ventana_inicio`,
ambos locales) — el error estaba solo aquí, en qué convención tiene
`creado_en`.

**Decisión (sin cambios en el comportamiento, la función ya era
correcta)**: una única función de normalización sirve para ambos casos
sin necesidad de distinguirlos por campo — si el valor llega sin marca
de zona, se le añade el offset de `Europe/Madrid`
(`zoneinfo.ZoneInfo`, librería estándar, sin dependencia nueva); si ya
la trae (como de hecho ya trae `episodios.creado_en`), se sirve tal
cual. `diagnostico_fecha` (de `diagnosticos.creado_en`, siempre UTC) no
pasa por la función — se sirve directamente. Ambas llegan al JSON como
ISO 8601 con offset — el consumidor JS nunca necesita saber qué
convención tenía cada una en origen.

**Rationale**: mismo criterio de "normalizar en el punto de lectura,
no en el de escritura" que research.md §2 de la versión anterior de
este documento ya había decidido para el caso de "Correcciones" —
sigue aplicando aquí para la parte de fechas que sí cruza convenciones
(`diagnosticos.creado_en`), aunque el emparejamiento en sí (§2) ya no
lo necesite.

## §5 — Dónde vive el código nuevo en `app.py`

**Decisión**: una función nueva junto a `get_active_alarms()`:
- `get_diagnostico_para_alarma(componente, down_since)` — implementa
  §2-§4, devuelve `None` o un dict con la forma de `data-model.md`.
- `get_gasto_diagnostico_hoy()` — lee `gasto_diario` para el día
  natural en curso (mismo criterio de "día natural, hora local" que
  `research.md` §6 de 007 ya fijó para escribir ese dato).

Dentro de `get_active_alarms()`, en la rama `origen == "contenedores"`
que ya llama a `add(..., _parse_iso_age_s(c.get("down_since")))`, se
añade la llamada a `get_diagnostico_para_alarma(c["name"],
c.get("down_since"))` y su resultado se adjunta al alarm dict como
campo `diagnostico`. El endpoint `/api/data` añade `gasto_diagnostico`
como campo nuevo de nivel superior (mismo patrón que `research.md` §4
de 006 documentó para `corrections`).

**Rationale**: mismo nivel de abstracción y misma ubicación que el
código que ya calcula las alarmas de contenedor — no se crea un módulo
nuevo para ~60 líneas que un solo consumidor usa (mismo criterio de
"no abstracción prematura" que research.md §7 de 007 ya aplicó).

## §6 — Renderizado: bloque nuevo dentro de la fila de alarma, sin tocar el resto

**Decisión**: `renderAlarmas(alarms)` (JS, `app.py`) añade, cuando
`a.diagnostico` existe, un bloque bajo la fila ya existente de esa
alarma — conclusión y fecha siempre visibles (spec.md FR-002, SC-005);
el detalle de hipótesis (User Story 2) detrás de una acción explícita
(clic), mismo patrón de "progressive disclosure" que ya usa el resto
del dashboard para contenido denso. El gasto diario
(`gasto_diagnostico`) se muestra una vez en la pestaña, no por alarma.

**Rationale**: Miquel dio libertad explícita para rediseñar la
superficie de esta funcionalidad — no hay ninguna restricción de
layout heredada que respetar más allá de FR-007 (una alarma sin
diagnóstico de la caída actual se ve exactamente igual que hoy).

**Alternativas consideradas**: mostrar siempre el detalle completo de
hipótesis sin colapsar. Rechazada por ahora — con `causa_probable` y
varias hipótesis, el texto por alarma puede ser largo; colapsar por
defecto mantiene la pestaña Alarmas escaneable de un vistazo, que es
su propósito actual (ver críticas cuando hay muchas alarmas activas a
la vez).
