# Research — Generalizar el Diagnóstico a Home Assistant

**Feature**: [spec.md](./spec.md)

## §1 — Sin migración de esquema: `origen` ya es TEXT libre

**Decisión**: `episodios.origen` gana un tercer valor real, `'ha'`, sin
ningún `ALTER TABLE`. La migración de 009
(`_migrar_episodios_contenedor_a_componente`) ya dejó la columna como
`TEXT NOT NULL DEFAULT 'contenedor'`, sin ninguna restricción `CHECK` de
valores permitidos — cualquier string es válido desde entonces.

**Rationale**: a diferencia de 009 (que sí tuvo que renombrar
`contenedor` → `componente` y añadir la columna `origen` desde cero),
aquí no hay ningún cambio de forma que hacer — solo un valor nuevo en un
campo que ya acepta cualquier texto. Confirmar esto explícitamente
evita repetir el trabajo de migración de 009 sin necesidad.

**Alternativas consideradas**: añadir un `CHECK (origen IN
('contenedor', 'disco', 'ha'))` para que el esquema documente los
valores válidos. Rechazada — SQLite exigiría recrear la tabla para
añadir un `CHECK` a una columna existente (no se puede con `ALTER TABLE
ADD CONSTRAINT`), coste real sin beneficio funcional: los valores
válidos ya están documentados en `model.py` (`Episodio.origen`) y en
este documento, y ningún camino de código escribe un `origen` fuera de
`{"contenedor", "disco", "ha"}`.

## §2 — Identificador de un episodio de HA: `check_id`, no `entity_id`

**Decisión**: un episodio de HA se identifica en el CLI y en
`episodios.componente` por el `check_id` de `ha_monitor.CHECKS`
(`"bateria_interruptor_salon"`, `"ha_recorder_corrupto"`, `"ha_api"`,
...), no por el `entity_id` de Home Assistant
(`"sensor.interruptor_salon_battery"`).

**Rationale**: mismo argumento que 009 §2 usó para preferir `label`
sobre `path` en discos — `check_id` es el nombre estable y legible que
ya usa el propio informe de `ha_monitor.py`. Además, a diferencia de un
disco (que siempre tiene un `path`), un check de HA no siempre tiene un
`entity_id` — `ha_recorder_corrupto` y `ha_api` no tienen ninguna
entidad asociada (research.md §4) — así que `entity_id` ni siquiera
podría ser el identificador universal.

## §3 — Fuente de los checks de HA: leer `ha_monitor.CHECKS` en vivo, nunca copiarlo

**Decisión**: `_homelab_bridge.py` de `diagnostico` gana una función
`ha_checks() -> list[dict]` que expone `ha_monitor.CHECKS` tal cual,
más `ha_history()`/`ha_recorder_corrupt_files()` (research.md §4), todas
con el mismo contrato de "nunca lanza, `[]`/`None` si `ha_monitor.py`
no está disponible" que ya usan `docker_critical()`/`docker_never_restart()`
en el mismo fichero.

**Rationale**: `src/inventory/_homelab_bridge.py` (feature 004) ya
resuelve exactamente este mismo problema —leer `ha_monitor.CHECKS` en
vivo sin copiarlo al repo público— con `ha_monitor_checked_entities()`/
`ha_monitor_check_result()`. `diagnostico/_homelab_bridge.py` es "una
copia mínima deliberada" de ese fichero (docstring propio) que
deliberadamente no incluía las funciones de `ha_monitor` porque 007/009
no tocaban HA. Este feature es exactamente el motivo por el que sí hace
falta ahora — se añade el mismo patrón, no uno nuevo.

**Resolución de un `check_id` inexistente**: si `check_id` no aparece en
`ha_monitor.CHECKS` (o `ha_monitor.py` no está disponible),
`ha_check_by_id()` devuelve `None` y `congelar_ha_vivo`/
`congelar_ha_historico` crean el episodio igual, con
`componente=check_id` y todos los campos de evidencia de HA en `null`
— **no es un error**, es el mismo criterio que ya spec.md fija en Edge
Cases ("el motor concluye que no se puede diagnosticar — mismo criterio
que un contenedor o disco inexistente"). El `no_diagnosticable`
resultante viene de la evidencia vacía que ya maneja el prompt de
DeepSeek, no de una comprobación explícita nueva.

## §4 — Evidencia por tipo de check, tres caminos distintos

**Decisión**: `ha_monitor.CHECKS` tiene tres formas de check, cada una
con su propia fuente de evidencia:

| `type` en `ha_monitor.CHECKS` | Checks de ejemplo | Evidencia |
|---|---|---|
| `entity_state`, `entity_available`, `entity_value_below`, `entity_age_below` | `z2m_bridge`, `sal_nivel`, `bateria_interruptor_salon`, `ha_backup_reciente` | Historial de `check["entity"]` vía `/api/history/period/` de la API REST de HA (§5) |
| `recorder_corrupto` | `ha_recorder_corrupto` (único) | Ficheros `*.corrupt.*` presentes (`ha_monitor._recorder_corrupt_files`) + logs recientes del contenedor `homeassistant` |
| `api_ping` | `ha_api` (único) | Logs recientes del contenedor `homeassistant` — sin entidad asociada (Clarifications 2026-08-12, FR-003) |

**Rationale**: no hay una única fuente de evidencia genérica para "un
check de HA" — la propia estructura de `ha_monitor.CHECKS` ya distingue
estos tres tipos (campo `type`), así que el código de evidencia
despacha por ese mismo campo en vez de inventar una taxonomía paralela.

**Historial de entidad — reutilizar `ha_get_detallado`, no reimplementar
la llamada HTTP**: el historial se pide con
`ha_monitor.ha_get_detallado(f"/api/history/period/{inicio_iso}?filter_entity_id={entity}&end_time={fin_iso}")`,
vía la función nueva `ha_history()` de `_homelab_bridge.py`. Esta
función ya resuelve credenciales (`HA_URL`/`TOKEN`, leídas de
`.secrets/ha.env` por `ha_monitor.py` al importarse), timeout (8 s) y
distinción 404/401/403/otros — reimplementarla en `diagnostico`
duplicaría exactamente la lógica que `ha_get_detallado` ya tiene
correcta y probada en producción.

**Alternativas consideradas para el historial de entidad**: conectar
directamente al SQLite del recorder (montado en un volumen Docker desde
el 2026-08-11, según spec.md Assumptions) y hacer `SELECT` sobre
`states`/`states_meta`. Rechazada — exigiría aprender el esquema interno
del recorder de HA (no estable entre versiones, a diferencia de la API
REST, que sí es un contrato público) y un mecanismo nuevo de acceso al
volumen Docker; la API REST ya resuelve esto con el mismo mecanismo que
`ha_monitor.py` usa para todo lo demás.

**Ficheros de corrupción y logs — reutilizar, no reimplementar**:
`_recorder_corrupt_files(contenedor, ruta)` de `ha_monitor.py` ya hace
`docker exec <contenedor> sh -c "ls -1 <ruta>/*.corrupt.* 2>/dev/null"`
(función privada, pero se reutiliza igual vía `_homelab_bridge`, mismo
criterio que `inventory/_homelab_bridge.py::ha_monitor_check_result()`
ya lee el `STATE_FILE` "privado" de `ha_monitor.py`). Los logs
reutilizan `evidencia.docker_logs_tail()`, ya existente desde 007 — sin
ninguna entrada nueva en la lista blanca de subprocesos (`("docker",
"logs")` ya está whitelisted).

## §5 — El check `ha_api` (Clarifications 2026-08-12)

**Decisión**: `ha_api` (tipo `api_ping`, sin entidad) entra en el
alcance de este feature con evidencia = logs recientes del contenedor
`homeassistant`, constante `_HA_API_CONTENEDOR = "homeassistant"` en
`evidencia.py` (no viene de `ha_monitor.CHECKS`, que para este check no
tiene campo `contenedor` — a diferencia de `ha_recorder_corrupto`, que
sí lo tiene).

**Rationale**: decisión tomada en `/speckit-clarify` (spec.md
Clarifications 2026-08-12) — un fallo de `/api/` normalmente refleja un
problema del propio proceso HA (caída, reinicio, cuelgue), así que sus
logs son la evidencia natural, reutilizando exactamente el mismo
mecanismo ya necesario para `recorder_corrupto`.

## §6 — Ventanas de tiempo: distintas de `VENTANA_METRICAS_MINUTOS`, y un límite aceptado para `recorder_corrupto`/`api_ping`

**Decisión — historial de entidad**: constante nueva
`VENTANA_HA_ENTIDAD_HORAS = 12` (horas, no minutos). En vivo: ventana
`[ahora - 12h, ahora]`. Histórico: ventana `[momento - 12h, momento +
12h]` — mismo patrón "centrado" que `congelar_disco_historico`, pero
con una ventana mucho más ancha que los 30 minutos de
`VENTANA_METRICAS_MINUTOS`.

**Rationale**: `container_metrics`/`disk_metrics` se muestrean cada 5
minutos por diseño (`docker_monitor.py`), así que una ventana de 30
minutos ya contiene varias muestras casi siempre. Las entidades de HA
no se muestrean por intervalo fijo — solo registran un cambio de estado
cuando ocurre (un sensor de batería puede tardar horas en volver a
reportar). Una ventana de 30 minutos dejaría casi cualquier check de
batería sin ningún dato real la mayoría de las veces, no porque el
sistema esté sano sino porque la ventana es demasiado estrecha para el
patrón de muestreo real — un `no_diagnosticable` "por diseño" en vez de
uno honesto. 12 horas cubre el ciclo de reporte típico de un sensor de
batería Zigbee sin ser una ventana desmesurada.

**Nota de implementación, a verificar en tareas**: la API de historial
de HA (`GET /api/history/period/<timestamp>`) suele incluir, además de
los cambios dentro de la ventana, el estado que ya estaba activo justo
al principio del periodo — si es así, incluso una ventana estrecha
tendría al menos un punto. No se asume este comportamiento como cierto
sin comprobarlo contra la API real del homelab (mismo criterio que 009
§1 verificó la versión de SQLite antes de asumir `RENAME COLUMN`
disponible) — la ventana de 12h se mantiene como valor de partida
razonable independientemente de lo que confirme esa comprobación.

**Decisión — `recorder_corrupto`/`api_ping`**: en vivo, evidencia =
estado *actual* (ficheros de corrupción presentes ahora, `docker logs
--tail 200` del contenedor ahora) — sin cambios respecto al mecanismo
ya usado para contenedores. **En histórico, la misma evidencia
"actual"** se congela bajo la etiqueta de `ventana_inicio`/`ventana_fin`
del momento pedido — no existe ningún mecanismo para saber si había
ficheros de corrupción presentes en un momento pasado (se renombran o
se limpian, no dejan rastro histórico) ni para pedir los logs del
contenedor *tal y como estaban* en un momento pasado sin un mecanismo
nuevo no justificado por ningún caso real todavía.

**Rationale de esta limitación aceptada**: spec.md Assumptions ya lo
anticipa explícitamente — "no existe hoy ningún incidente histórico
real de ningún tipo de check de HA con un registro reutilizable... ni
para el check de recorder corrupto, que además es un check nuevo...
sin ningún historial anterior a su propia existencia" — y fija que "la
validación se apoya en `congelar --vivo` contra el estado sano actual".
Construir un mecanismo de logs verdaderamente históricos (`docker logs
--since/--until`) para un caso sin ningún incidente real que lo
justifique sería exactamente el tipo de complejidad prematura que el
proyecto evita en el resto de su código. Si aparece un incidente real
de `ha_recorder_corrupto`/`ha_api` mientras se desarrolla (spec.md,
Assumptions), este mecanismo se revisita entonces, con un caso real
delante en vez de uno hipotético.

**No compromete FR-002/SC-001**: la reproducibilidad exigida por FR-002
es sobre un snapshot *ya congelado* — `diagnosticar` nunca vuelve a
tocar HA ni Docker (mismo invariante que 007/009). Que el propio acto de
`congelar --ha-historico` para estos dos tipos lea estado actual en vez
de histórico es una limitación de *qué* evidencia se reúne, no una
violación de que un snapshot ya escrito produzca siempre la misma
conclusión al diagnosticarlo.

## §7 — Exclusión de la cerradura (FR-010): bloqueo explícito, no evidencia vacía

**Decisión**: constante `CHECKS_HA_EXCLUIDOS_CERRADURA = {"cerradura_up",
"bateria_cerradura", "bateria_critica_cerradura"}` en `evidencia.py`.
`congelar_ha_vivo`/`congelar_ha_historico` comprueban esta lista **antes**
de resolver el check contra `ha_monitor.CHECKS` y lanzan `ValueError`
con un mensaje explícito si `check_id` está en ella — mismo patrón que
ya usa `congelar_historico()` cuando un `restart_history_id` no existe
(`ValueError`, sin capturar en `cli.py`, termina el proceso con
traceback y código de salida 1).

**Rationale**: FR-010 es un "NO DEBE" sobre un conjunto conocido de
checks, no una ausencia de evidencia — tratarlo igual que un
`check_id` inexistente (§3, evidencia vacía → `no_diagnosticable`)
enterraría la exclusión como un resultado indistinguible de "no hay
datos", en vez de un rechazo explícito y auditable. Los tres IDs cubren
las dos categorías que cita FR-010 textualmente: `cerradura_up`
(conectividad) y `bateria_cerradura`/`bateria_critica_cerradura`
(batería, dos checks con distinto umbral sobre el mismo concepto).

**Alternativas consideradas**: derivar la exclusión por convención de
nombre (cualquier `check_id` que contenga `"cerradura"`). Rechazada —
frágil ante un renombrado futuro en `ha_monitor.py` (ya pasó una vez,
ver CLAUDE.md general del homelab, "Entidad renombrada = falsa alarma
indistinguible") y menos auditable que una lista explícita con su
propia justificación escrita aquí.

## §8 — Prompt de DeepSeek: generalizado una tercera vez

**Decisión**: `_PROMPT_INSTRUCCIONES` (`deepseek.py`) cambia de nuevo
solo su frase de encuadre: de *"...puede ser un contenedor Docker caído
o un disco con uso alto"* a *"...puede ser un contenedor Docker caído,
un disco con uso alto, o un check de Home Assistant (una entidad con
batería baja o estado inesperado, su recorder corrupto, o su API sin
responder)"*. El resto del prompt (estructura del JSON, semántica de
"confirmada", la cláusula de crítico) no cambia — ninguna causa nueva
de ambigüedad distinta de las que 007/009 ya corrigieron con evidencia
real.

**Rationale**: mismo argumento que 009 §5 — cambiar solo la frase de
encuadre es el cambio mínimo que generaliza sin arriesgar una regresión
sobre invariantes ya validados (FR-006, `parsear_respuesta()`).

**`es_critico` para HA — siempre `False`**: igual que discos (009 §4) —
no existe concepto de "check de HA crítico" (spec.md Assumptions), así
que `congelar_ha_vivo`/`congelar_ha_historico` fijan `es_critico=False`
siempre; ningún episodio de HA lleva la cláusula de crítico del prompt.

## §9 — CLI: dos flags nuevos, mismo patrón `congelar`/`diagnosticar`/`mostrar`

**Decisión**: `congelar` gana dos opciones nuevas en su grupo
mutuamente excluyente ya existente:

```
python3 -m diagnostico.cli congelar --ha-vivo CHECK_ID
python3 -m diagnostico.cli congelar --ha-historico "CHECK_ID@MOMENTO_ISO"
```

`diagnosticar`, `mostrar` y `--selftest` no cambian su firma — ya
operan sobre `episodio_id`, agnóstico al origen.

**Rationale**: mismo razonamiento que 009 §6 — reutiliza exactamente el
mismo verbo (`congelar`) y el mismo patrón `LABEL@MOMENTO_ISO` que
`--disco-historico` ya validó, en vez de introducir una sintaxis nueva.
`CHECK_ID@MOMENTO_ISO` es directamente análogo a `LABEL@MOMENTO_ISO` —
mismo separador, mismo formato de fecha, misma interpretación en hora
local sin marca de zona (research.md §3 de 009).

**`MOMENTO_ISO` — misma convención de zona horaria que 009 §3**: hora
local sin marca de zona, comparada directamente contra los timestamps
que ya use la evidencia de HA — sin conversión a UTC ni offset añadido,
mismo criterio ya fijado para contenedores y discos.

## §10 — `parsear_respuesta()`: respaldo en `reasoning_content` (corrección real, 2026-08-12)

**Hallazgo real durante la validación en vivo de este feature**: el
modelo de razonamiento de DeepSeek a veces escribe la respuesta
completa y válida en `reasoning_content` y deja `content` vacío, pese a
`finish_reason: "stop"` — mismo síntoma que el CLAUDE.md general del
homelab ya documenta para el backend local de los crons de Bautista
(`qwen/qwen3.5-9b`), aquí en el propio DeepSeek de la nube.
`parsear_respuesta()` solo leía `content`, así que estas respuestas
—completas, solo en el campo equivocado— se descartaban como
"inconsistentes" y quemaban gasto real (tokens ya facturados) sin
producir ningún diagnóstico. Afecta al motor compartido por 007/009/010
por igual, no solo a episodios de HA.

**Decisión**: `parsear_respuesta()` intenta `content`; si viene vacío,
prueba `reasoning_content` antes de descartar la respuesta. Si tampoco
es JSON válido (narrativa de razonamiento sin la respuesta final, o la
generación se cortó por `max_tokens` antes de llegar a ella), se
rechaza exactamente igual que antes — este respaldo nunca empeora el
caso ya manejado, solo recupera casos que antes se perdían sin motivo.

**No se tocó**: `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` (2000) — valor ya
fijado deliberadamente en 007 (research.md §6 de 007, hallazgo B1 de
`/speckit-analyze`: "cifra concreta, no un margen prudente sin
definir"). Cuando la generación se corta genuinamente por agotar el
presupuesto (`finish_reason: "length"` sin que `reasoning_content`
llegue a contener la respuesta), no hay nada que recuperar — es una
limitación de coste aceptada, no un bug.

## §11 — `docker_logs_tail()`: `stderr` se combina con `stdout` (corrección real, 2026-08-12)

**Hallazgo real**: `docker logs homeassistant` escribe su salida en
`stderr`, no en `stdout` (confirmado en vivo). `_run_ro()` (007,
`evidencia.py`) solo capturaba `stdout`, así que
`docker_logs_tail("homeassistant")` devolvía siempre `""` pese a haber
logs reales — vaciando por completo la evidencia que FR-003 promete
para `ha_recorder_corrupto` y `ha_api` ("los logs del contenedor
homeassistant"). Sin este arreglo, ambos tipos de check quedaban
diagnosticando con la mitad de su evidencia prometida, en silencio.

**Decisión**: `_run_ro()` combina `stderr` con `stdout` (`stderr=
subprocess.STDOUT`) — el mismo comportamiento que ve Miquel si teclea
`docker logs homeassistant` en una terminal, sin redirección. Sin
efecto sobre `docker inspect`/`docker ps` (ya escriben en `stdout` en
el caso normal).

## §12 — `ha_check_status`: el veredicto ya calculado, como cuarto campo de evidencia (corrección real, 2026-08-12)

**Hallazgo real**: diagnosticar en vivo `ha_api` **sano** (API
respondiendo con normalidad) producía `causa_probable`, citando un
error real pero no relacionado (una integración `command_line` con una
clave SSH inaccesible) encontrado en los logs compartidos del
contenedor — violación directa de SC-004. Causa raíz: nada en la
evidencia le decía al modelo si *este check concreto* estaba fallando
ahora mismo; con 111 checks compartiendo el mismo log de contenedor,
casi siempre hay *algún* error real de *otra* integración que el
modelo, siguiendo la instrucción de "nunca inventes una causa sin
evidencia real", reportaba como si fuera la causa de este check. El
mismo problema de fondo —el modelo reconstruyendo por su cuenta si algo
está mal, en vez de que se lo digan— también explica la reasoning
inusualmente larga (y los fallos por `finish_reason: "length"`)
observada en `ha_backup_reciente` (`entity_age_below`): el modelo tenía
que hacer aritmética de fechas él mismo para saber si el backup estaba
caducado.

**Decisión**: `congelar_ha_vivo`/`congelar_ha_historico` congelan
también `ha_monitor.check_status(check)` — el mismo veredicto
`(ok, detalle, motivo)` que ese módulo ya calcula cada 15 minutos para
el informe real — como snapshot key `ha_check_status`
(`_homelab_bridge.py::ha_check_status()`, wrapper directo, mismo
patrón que el resto del bridge). `construir_prompt()` (`deepseek.py`)
añade una cláusula nueva cuando el snapshot trae `ha_check_status`
resuelto: si `ok` es `true`, el modelo DEBE concluir
`no_diagnosticable` — no hay episodio real de *ese* check que explicar,
aunque el resto de la evidencia muestre problemas reales de otras
partes del sistema.

**Validado en vivo tras el arreglo**: `ha_api` sano → `no_diagnosticable`
explícito citando que los errores de SSH "son ajenos a este check"
(episodio 27, dos intentos consecutivos). `ha_recorder_corrupto` sano
→ igual (episodio 28); con un fichero de corrupción simulado →
`causa_probable` correcto (episodio 29).

**Alternativas consideradas**: filtrar los logs para quedarse solo con
líneas relevantes al check antes de enviarlos. Rechazada — más frágil
(depende de heurísticas de qué es "relevante") y no resuelve el
problema de `ha_backup_reciente`, que no usa logs en absoluto; darle al
modelo el veredicto ya calculado resuelve ambos síntomas con un único
mecanismo, reutilizando código ya real y probado (`check_status()`) en
vez de inventar uno nuevo.

## §13 — Límite de historial acotado: `HA_HISTORIAL_MAX_ENTRADAS = 50` (revisión real de §6, 2026-08-12)

**Hallazgo real**: `sal_nivel` (`entity_value_below` sobre un sensor de
voltaje) devolvió 1.962 cambios de estado en la ventana de 12h — un
prompt de 280.454 tokens que agotó el presupuesto de razonamiento sin
producir ningún diagnóstico. La premisa original de §6 ("las entidades
de HA solo registran un cambio de estado cuando ocurre") es cierta para
sensores event-driven (baterías Zigbee, disponibilidad) pero falsa para
sensores de medición continua, que pueden reportar cada pocos segundos.

**Decisión**: `_simplificar_historial()` en `evidencia.py` recorta el
historial devuelto por `ha_history_window()` a las
`HA_HISTORIAL_MAX_ENTRADAS = 50` entradas más recientes, y reduce cada
entrada a `state`/`last_changed` — descarta `entity_id` (redundante con
`ha_check.entity`) y `attributes` (metadata repetida en cada entrada:
unidad, `device_class`, nombre — no aporta señal nueva). Acota el peor
caso para cualquier entidad sin importar su frecuencia real de reporte,
y reduce el tamaño incluso en el caso normal.

**Validado en vivo tras el arreglo**: el mismo `sal_nivel` pasó de
280.454 a ~1.900 tokens de entrada; diagnosticado con éxito al cuarto
intento (`no_diagnosticable`, ruido de sensor por debajo del umbral,
4 hipótesis).
