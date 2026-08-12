# Research — Generalizar el Diagnóstico a los Hosts Externos

**Feature**: [spec.md](./spec.md)

## §1 — Sin migración de esquema: `origen` ya es TEXT libre

**Decisión**: `episodios.origen` gana un séptimo valor real,
`'host_externo'`, sin ningún `ALTER TABLE` — misma situación que
010 §1/011 §1/012 §1/013 §1.

## §2 — Identificador: `NOMBRE`, simétrico en vivo y en diferido (como inventario, no como relays)

**Decisión**: `componente` es siempre el nombre canónico del host —
mismo criterio que `check_id` de HA (010 §2), `label` de disco (009
§2) y `nombre_actual` de inventario (013 §3). A diferencia de relays
(012 §2, asimétrico porque la evidencia agregada no permite
identificar ningún relay concreto), aquí sí existe un host concreto
en ambos modos: en vivo, el estado ya calculado de ese host; en
diferido, la densidad de muestras de ese host en una ventana. El CLI
combina `NOMBRE@MOMENTO_ISO` en diferido (mismo orden que
`LABEL@MOMENTO_ISO`/`CHECK_ID@MOMENTO_ISO`), pero solo `NOMBRE` se
guarda en `episodios.componente` — mismo patrón que esos dos orígenes.

**`HOSTS_EXTERNOS`**: `{"Host de Uptime Kuma": "UptimeKuma", "Host de
AdGuard Home (DNS primario)": "AdGuardHome"}` — mismos literales que
`scripts/beszel_hosts_monitor.py::HOSTS` y `app.py::EXTERNAL_HOSTS`
(fuera de este repo, documentado en `BRIEFING.md` "Feature 014 —
material de partida"). Un `NOMBRE` que no está en este dict no es un
error — mismo criterio ya establecido para `check_id`/`label`/nombre
de relay/componente de inventario inexistentes: el episodio se
congela igual, con evidencia vacía.

## §3 — Evidencia en vivo: reproduce exactamente la política de frescura de `app.py::get_external_hosts()`

**Decisión**: `_host_externo_actual(nombre)` replica la lógica exacta
de `get_external_hosts()` (fuera de este repo, en
`docker/homelab-dashboard/scripts/app.py`, comprobada en vivo antes de
diseñar) — no la reimporta (no es un paquete de este repo, a
diferencia de `inventory` en 013 §2), la reproduce con la misma
constante:

```python
BESZEL_HOSTS_MAX_AGE_S = 900  # mismo valor exacto que app.py — no se
# recalcula ni se relaja, mismo criterio de "usar el veredicto ya
# calculado" que ha_check_status en 010.
```

Lee `beszel_hosts.json` (`generated_at`, `hosts[nombre].status`) y el
latido `data/heartbeats/beszel-hosts.json` (`epoch`) — **las dos
edades deben estar dentro de 900s a la vez**, exactamente como hace
`app.py`. Tres estados posibles, mismos literales que el dashboard:
`"arriba"` (raw_status == "up"), `"caido"` (fresco pero raw_status ≠
"up"), `"sin_evidencia"` (dato caducado, latido caducado/ausente, o el
nombre no aparece en `beszel_hosts.json`).

**`"sin_evidencia"` es evidencia real, no un caso vacío** (spec.md
Edge Cases): a diferencia de un nombre inexistente en `HOSTS_EXTERNOS`
(que sí produce un snapshot vacío), un host válido con estado
`"sin_evidencia"` lleva sus edades reales (`data_age_s`/`hb_age_s`) en
el snapshot — el motor puede formular hipótesis sobre por qué la
propia vigilancia se quedó sin datos frescos.

## §4 — Primera conversión de huso horario del motor: Madrid → UTC

**Hallazgo real**: todos los orígenes anteriores comparan `momento`
(convención ya establecida: hora local sin marca de zona) directamente
contra columnas que ya están en hora local (`disk_metrics.timestamp`,
el nombre de fichero de un log de backup, las líneas de
`dashboard-socat.log`). La tabla `system_stats` del hub de Beszel es
la primera fuente cuya columna `created` está en **UTC** (comprobado
en vivo: `'2026-08-12 20:23:28.042Z'` con el reloj local en
22:23 CEST) — compararla directamente contra un `momento` naive
produciría una ventana desplazada 1-2h según la época del año (CET/CEST).

**Decisión**: `_a_utc_madrid(momento)` interpreta `momento` como hora
de Europe/Madrid (mismo huso que usa `DIAGNOSTICO_MADRID_TZ` en
`app.py` para mostrar diagnósticos, aunque ese uso es de
visualización, no de consulta) vía `zoneinfo.ZoneInfo`, y lo convierte
a UTC antes de construir los límites de la consulta SQL — corrige el
desfase de forma correcta todo el año, sin hardcodear un offset fijo
que se rompería en el cambio de hora.

## §5 — Evidencia en diferido: resumen de densidad, nunca un booleano "caído"

**Decisión**: `_consultar_beszel_hub(beszel_name, inicio_utc, fin_utc)`
ejecuta una consulta de solo lectura parametrizada (nunca interpolación
de texto en SQL, research.md §7) contra `system_stats`, y
`_resumen_system_stats(filas)` la reduce a:

```json
{"total_muestras": 3, "primera": "2026-07-30 01:40:00.043Z",
 "ultima": "2026-07-30 17:40:00.047Z",
 "por_tipo": {"480m": 3}}
```

o, sin ninguna muestra: `{"total_muestras": 0, "primera": null,
"ultima": null, "por_tipo": {}}`.

**Por qué un resumen y no una lista de muestras** (mejora de diseño
basada en lecciones ya aprendidas, no una sorpresa descubierta tarde):
011 (`BACKUP_ANOMALIA_MAX_LINEAS`), 012 (`RELAY_AGREGADO_MAX_LINEAS`) y
013 (`INVENTARIO_COMPARACION_MAX_ENTRADAS`) tuvieron que acotar listas
sin límite después de encontrar (012/013, en vivo) o prever (011) un
caso real que las desbordaba. Aquí, con una ventana de ±24h (§6) y 5
resoluciones de retención simultáneas, una lista sin resumir podría
crecer igual de descontrolada (potencialmente decenas de muestras de
tipo `1m` para un momento reciente). Resumir desde el diseño —
recuento, primera, última, por tipo— evita el problema en vez de
acotarlo después, y es más útil para el modelo que una lista de
timestamps: la densidad y el rango ya dicen si el host reportaba con
normalidad o no, sin que el modelo tenga que contarlos él mismo.

**Nunca un booleano "caído"** (FR-006a): `total_muestras == 0` es
"sin datos en esta ventana", no "host caído confirmado" — puede
deberse al host real caído, pero también a un fallo del agente de
Beszel en ese host, a un problema de red entre el hub y el host, o a
que el propio hub dejó de registrar (origen aparte, #8). El prompt
(§8) se lo indica explícitamente al modelo.

## §6 — Ventana: `VENTANA_HOST_EXTERNO_MINUTOS = 1440` (±24h), justificada por la cadencia real de retención

**Investigado en vivo antes de fijar el valor**: la resolución más
gruesa que sobrevive más allá de 5 días (`480m`, 8h) escribe una
muestra cada 8h durante operación sana — comprobado en la ventana
2026-08-08/09: `22:20, 06:20, 14:20, 22:20`, exactamente cada 8h. Una
ventana más estrecha que esa cadencia (por ejemplo, las ±30min/±180min
que usan otros orígenes) podría caer entre dos muestras `480m`
legítimas y mostrar "0 muestras" durante un periodo sano — una falsa
señal de caída causada por el propio muestreo, no por ningún fallo
real. `±1440min` (24h) cubre 2-3 muestras `480m` esperadas durante
operación sana, así que una ventana con 0 muestras en absoluto es una
señal fiable de ausencia real, no un artefacto de resolución.

## §7 — `_consultar_beszel_hub`: parámetros SQL vía `argv`, nunca interpolación de texto

**Decisión**: el script Python ejecutado dentro del contenedor
`python:3.11-alpine` recibe `beszel_name`/`inicio_utc`/`fin_utc` como
argumentos de `sys.argv`, nunca formateados dentro del propio texto
del script (`python3 -c "..."`) — la consulta SQL usa `?` con
`con.execute(query, (sys.argv[1], sys.argv[2], sys.argv[3]))`, la
misma disciplina de parámetros que ya exige cualquier consulta contra
`homelab.db` en `evidencia.py`. Evita por completo cualquier riesgo de
que un valor con comillas rompa la sintaxis del script o de la
consulta, sin depender de escapar manualmente ningún carácter.

**Primera vez que este motor ejecuta `docker run`** (arranca un
contenedor nuevo), no solo `docker inspect`/`docker logs`/`docker ps`
(`_run_ro()`, introspección de contenedores ya existentes) — se
implementa como función dedicada (`_consultar_beszel_hub`), no como
una entrada más en la lista blanca de `_run_ro()`: el riesgo y el
propósito son distintos (arrancar un contenedor efímero de solo
lectura contra un volumen ajeno, mismo patrón exacto ya en producción
en `beszel_hosts_monitor.py`, ejecutado cada 5 min sin incidentes) y
merece su propia función explícita, no mezclarse con la lista blanca
de subcomandos de introspección.

## §8 — Prompt de DeepSeek: generalizado una séptima vez, con cláusula nueva (FR-006a)

**Decisión**: `_PROMPT_INSTRUCCIONES` añade "...o un host físico
externo que Beszel ya vigila (feature 014:
specs/014-diagnostico-hosts-externos/) — Uptime Kuma o AdGuard Home,
en vivo con su estado ya calculado, en diferido con la densidad de
muestras de rendimiento que reportó" a la lista ya existente.
**Cláusula nueva** (aplicable cuando `snapshot["host_externo_stats"]`
no es `null`, es decir, episodio en diferido): el modelo NUNCA debe
presentar `total_muestras == 0` como prueba de que el host estaba
caído — debe tratarlo como ausencia de datos y considerar, si la
evidencia no permite descartarlas, otras causas (fallo del agente de
Beszel en ese host, fallo de red hub↔host, el propio hub sin
registrar) antes de concluir una causa concreta.

**`es_critico` para host externo — siempre `False`**: igual que
discos, HA, backups, relays e inventario.

**Por qué FR-006a queda solo en el prompt, sin validación en código
(a diferencia de FR-006 de 012 y FR-010 de 013)**: los dos casos
anteriores validan en código porque comprueban algo **discreto y
verificable mecánicamente** contra el propio dato de entrada — si un
nombre de relay real aparece como subcadena literal del texto (012), o
si el tipo de una brecha ya conocida es `condicion_incumplida` (013).
FR-006a pide algo distinto: que el modelo no trate la ausencia de
muestras como prueba concluyente *sin considerar alternativas* — un
juicio sobre la calidad del razonamiento, no un hecho verificable por
coincidencia de texto (buscar palabras como "caído"/"confirmado" daría
falsos rechazos: una `causa_probable` que legítimamente concluya "el
host estaba caído" tras contrastar y descartar las demás hipótesis es
una respuesta correcta, no una violación). Es la misma naturaleza que
la instrucción general "nunca inventes una causa sin evidencia" de
`_PROMPT_INSTRUCCIONES`, vigente para los siete orígenes desde 007 y
nunca validada en código más allá del invariante estructural de
`parsear_respuesta()` — coherente con ese precedente, no una omisión.

## §9 — CLI: dos flags simétricos

**Decisión**:

```
python3 -m diagnostico.cli congelar --host-externo-vivo NOMBRE
python3 -m diagnostico.cli congelar --host-externo-historico "NOMBRE@MOMENTO_ISO"
```

`NOMBRE` puede contener espacios (`"Host de Uptime Kuma"`) — se
entrecomilla igual que ya hace `--relay-vivo`/`--inventario-vivo`.
`MOMENTO_ISO` sigue la convención ya establecida (hora local de
Madrid, sin marca de zona) — la conversión a UTC (§4) ocurre dentro de
`congelar_host_externo_historico`, nunca la ve el usuario.

## §10 — Nombre inexistente o consulta al hub fallida: se congela igual, con evidencia vacía — y `None` no es lo mismo que `[]`

**Decisión**: mismo criterio ya establecido en 009-013. Un `NOMBRE`
fuera de `HOSTS_EXTERNOS`, o una consulta a `beszel_hosts.json`/al hub
que falle (fichero ausente, `docker run` sin éxito, Docker no
disponible), no lanzan — el episodio se congela con la evidencia
correspondiente en `None`/vacía, y el diagnóstico resultante concluye
`no_diagnosticable` honestamente.

**Distinción explícita, para no confundir dos casos reales distintos**
en `congelar_host_externo_historico()`: si `nombre` no está en
`HOSTS_EXTERNOS`, `host_externo_stats` queda `None` directamente, sin
llamar a `_consultar_beszel_hub()`. Si `nombre` es válido pero
`_consultar_beszel_hub()` devuelve `None` (la consulta en sí falló —
Docker no disponible, `docker run` con código de salida distinto de 0),
`host_externo_stats` también queda `None` — **nunca** se le pasa `None`
a `_resumen_system_stats()`, que espera una lista (aunque sea vacía) y
lanzaría si recibiera `None`. Si la consulta tuvo éxito pero no hay
ninguna fila en la ventana, `_consultar_beszel_hub()` devuelve `[]` (no
`None`), y `host_externo_stats = _resumen_system_stats([])` =
`{total_muestras: 0, primera: None, ultima: None, por_tipo: {}}` — esto
sí es evidencia real (la consulta funcionó, no había datos), distinta
de "no se pudo consultar". La misma distinción `None` (sin poder
comprobar) vs. `[]`/evidencia vacía (comprobado, sin datos) que ya usa
`ha_history_window()` de 010.

## §11 — La línea base real: la misma avería, comprobada en las dos fuentes

**Comprobado en vivo antes de escribir el plan**: `system_stats` tiene
un hueco idéntico para los dos hosts, del 2026-07-30 (00:00-01:40)
al 2026-08-07 (22:20) — ocho días sin ninguna muestra en ninguna
resolución. Coincide exactamente con la avería ya documentada en el
`CLAUDE.md` general del homelab (routing de contenedores roto tras un
reinicio, sin ruta a la LAN, resuelta con los relays `socat` de
Beszel del 2026-08-07) — a diferencia de 007 (causa nunca encontrada)
o 013 (causa "la categoría se introdujo sin declarar, se corrigió
después"), aquí la causa raíz real ya está documentada de forma
independiente por otro artefacto del propio homelab, no inferida por
este feature. La validación de este feature (SC-005) se apoya
directamente en esta avería real.

## §12 — Fallo real de implementación, encontrado en la propia validación: `host_externo_stats` sin identificar el host (hallazgo real, 2026-08-12)

**Hallazgo real**: la primera implementación de
`congelar_host_externo_historico()` llamaba a `_resumen_system_stats()`
y guardaba el resultado tal cual en `host_externo_stats` — sin
`nombre` ni `beszel_name`, pese a que `data-model.md` ya documentaba
esas dos claves desde el diseño. Diagnosticando en vivo el primer
episodio real de la avería conocida (T020, componente "Host de Uptime
Kuma", ventana 2026-08-01T12:00 a 2026-08-03T12:00,
`total_muestras=0`), la conclusión de DeepSeek fue honesta pero
reveladora: *"ni siquiera se puede determinar qué componente del
homelab estaba en episodio"* — cierto, porque la evidencia tal como se
serializaba de verdad no llevaba el nombre del host en ningún sitio;
`episodio.componente` es metadato del propio episodio, nunca viaja
dentro del JSON que lee el prompt.

**Corregido inmediatamente**, antes de repetir la validación:
`congelar_host_externo_historico()` añade `nombre`/`beszel_name` al
resumen después de calcularlo (`_resumen_system_stats()` en sí sigue
siendo agnóstica al host, útil también fuera de este contexto). Mismo
patrón que `host_externo_actual` (T003), que sí llevaba `nombre` desde
el principio — la asimetría entre los dos modos fue la causa real del
descuido, no una decisión consciente.

**Por qué se documenta como hallazgo de validación, no como error
silencioso**: es la misma disciplina que 012 (F1) y 013 (U1) — un
defecto de diseño encontrado por evidencia real, corregido en el
código y en `data-model.md` a la vez, no solo parcheado.
