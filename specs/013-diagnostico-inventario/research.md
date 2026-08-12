# Research — Generalizar el Diagnóstico al Inventario de Cobertura

**Feature**: [spec.md](./spec.md)

## §1 — Sin migración de esquema: `origen` ya es TEXT libre

**Decisión**: `episodios.origen` gana un sexto valor real,
`'inventario'`, sin ningún `ALTER TABLE` — misma situación que
010 §1/011 §1/012 §1.

## §2 — Reutiliza `inventory.store`/`inventory.diff` por import, no releyendo SQL a mano

**Hallazgo real durante la investigación previa a planificar**: a
diferencia de `homelab.db` (generada por `docker_monitor.py`, código
que vive **fuera** de este repo, en
`/Volumes/FastData/homelab/scripts/`) o de `socat_relays.json`/
`dashboard-socat.log` (ficheros de texto/JSON sin ningún lector
reutilizable), `inventario.db` la genera `src/inventory/`, un paquete
de **este mismo repo**, con funciones ya probadas que hacen
exactamente lo que este feature necesita:
`inventory.store.hallazgos_de_ejecucion(conn, ejecucion_id)`,
`inventory.store.brechas_de_ejecucion(conn, ejecucion_id)` y
`inventory.diff.compare_runs(conn, actual_id, previa_id)` — esta
última ya es la función que usa `--since` en `inventory.cli`.

**Decisión**: `diagnostico/evidencia.py` importa `inventory.store`,
`inventory.diff` e `inventory.model` directamente (`from inventory
import store as inv_store, diff as inv_diff` — ambos paquetes ya
conviven bajo `src/`, mismo mecanismo de import que ya usan
`tests/selftest/test_diff.py`/`test_identity.py` para probar
`inventory` desde fuera de su propio paquete). Ninguna consulta SQL
nueva contra `inventario.db` — todo pasa por funciones ya existentes y
ya cubiertas por el selftest de `inventory`.

**Rationale**: releer el esquema de `inventario.db` a mano en
`diagnostico/evidencia.py` (como si fuera un fichero externo)
duplicaría lógica ya escrita, probada y mantenida en `inventory/`, y
divergiría en silencio si ese esquema cambia en un feature futuro del
propio Frente 1. Es la primera vez que este motor importa un paquete
de aplicación en vez de leer una fuente de datos externa — decisión
tomada explícitamente, no por descuido.

**`inventory.store.connect()` es segura para solo lectura aquí**:
ejecuta `CREATE TABLE IF NOT EXISTS` de forma idempotente al abrir
(ver docstring de `store.py`) — no hay riesgo de mutar
`inventario.db` real por el mero hecho de conectar; este feature nunca
llama a ninguna función de escritura (`insert_*`, `save_run`,
`populate_brechas`).

## §3 — Identificador: `NOMBRE`, simétrico en vivo y en diferido (a diferencia de 012)

**Decisión**: `componente` es siempre `nombre_actual` del componente
— mismo criterio que `check_id` de HA (010 §2) y `label` de disco
(009 §2). A diferencia de relays (012 §2, asimétrico porque la
evidencia agregada no permite identificar ningún relay concreto), aquí
**sí** existe un componente concreto en ambos modos: en vivo, el de la
última ejecución del inventario; en diferido, el de la ejecución que
Miquel señale. La asimetría de este origen no está en *qué* se
identifica, sino en *qué ejecución* se consulta.

En el CLI, el modo diferido combina dos piezas —
`--inventario-historico "NOMBRE@EJECUCION_ID"`, mismo orden
`identificador@localizador-temporal` que `LABEL@MOMENTO_ISO`/
`CHECK_ID@MOMENTO_ISO` de discos/HA— pero, igual que en esos dos
orígenes, **solo `NOMBRE` se guarda en `episodios.componente`**;
`EJECUCION_ID` vive dentro del propio `snapshot_evidencia`
(`inventario_ejecucion_id`), no en un campo del modelo `Episodio` — no
hace falta ningún campo nuevo (research.md, `data-model.md`).

## §4 — Evidencia: el hallazgo de la ejecución + comparación automática contra `primera_ejecucion_id - 1`

**Decisión**: `_hallazgo_de_componente(conn_inv, ejecucion_id, nombre)`
y `_brecha_de_componente(conn_inv, ejecucion_id, nombre)` recorren
`hallazgos_de_ejecucion`/`brechas_de_ejecucion` de esa ejecución
buscando `nombre_actual == nombre` — sin nueva consulta SQL (§2). Si
existe una brecha de uno de los 5 tipos en alcance,
`brecha["primera_ejecucion_id"]` ya dice en qué ejecución empezó esa
racha (`populate_brechas()` la hereda de la brecha anterior del mismo
componente+tipo mientras no se resuelva — no se recalcula en cada
ejecución nueva). La comparación se hace siempre contra
`primera_ejecucion_id - 1`, **nunca contra `ejecucion_id - 1`**: es la
única ejecución garantizada de no tener esa brecha, sea cual sea la
ejecución concreta que Miquel señale dentro de la racha.

```python
comparacion = None
if brecha is not None and brecha["primera_ejecucion_id"] > 1:
    comparacion = inv_diff.compare_runs(
        conn_inv, ejecucion_id, brecha["primera_ejecucion_id"] - 1
    )
    # acotado antes de entrar en el snapshot — ver §11
```

**Rationale**: esto es exactamente lo que describía el material de
partida de `BRIEFING.md` ("el diff... contra la ejecución
inmediatamente anterior a la que introdujo la brecha,
`primera_ejecucion_id - 1`, ya guardado por componente") — Miquel no
necesita saber ni pasar esa ejecución anterior, el propio dato ya
persistido la resuelve. `compare_runs()` da un diff global (todos los
componentes que cambiaron entre las dos ejecuciones, no solo el
diagnosticado) — mismo comportamiento que `--since` ya expone hoy en
producción; se acepta como evidencia de contexto útil (qué más cambió
al mismo tiempo), no como ruido a filtrar.

**Caso sin ejecución anterior** (`primera_ejecucion_id == 1`, o
`brecha is None`): `comparacion` queda `None` — se declara
explícitamente en el snapshot, nunca se inventa un "antes" (spec.md
Edge Cases).

**`_brecha_de_componente()` nunca filtra por tipo** (hallazgo U1 de
`/speckit-analyze`, 2026-08-12): debe devolver cualquiera de los 6
tipos de brecha si existe, incluido `condicion_incumplida` — filtrar
aquí dejaría a `_validar_tipo_brecha_inventario()` (§5) sin nada que
rechazar, vaciando FR-010 en silencio. Una primera redacción de
`data-model.md`/`tasks.md` describía esta función como si "filtrara a
los 5 tipos en alcance salvo para la comprobación de FR-010" —
contradictorio consigo mismo, corregido antes de implementar.

## §5 — FR-010 (`condicion_incumplida` fuera de alcance) validado en código, mismo patrón que la cerradura en 010

**Decisión**: antes de construir cualquier snapshot,
`_validar_tipo_brecha_inventario(brecha)` comprueba si la brecha
encontrada es de tipo `condicion_incumplida` y, si lo es, lanza
`ValueError` — el episodio nunca se congela. Mismo patrón exacto que
`_validar_check_ha()` (010 §7 de `specs/010-diagnostico-ha/research.md`)
bloqueando los 3 checks de la cerradura: un rechazo explícito de
alcance, no una evidencia vacía que terminaría en
`no_diagnosticable` por falta de datos.

**Por qué en código desde el diseño, no como corrección posterior**:
012 tuvo que corregir esto (hallazgo F1 de `/speckit-analyze`,
`research.md §10` de 012) después de diseñar solo una cláusula de
prompt para la restricción hermana de ese feature ("nunca nombres un
relay concreto"). Aquí la restricción es más fuerte todavía —
`condicion_incumplida` no es "no reveles X", es "no aceptes esto como
entrada en absoluto" — y se puede comprobar determinísticamente contra
el propio dato (`brecha["tipo"]`) sin depender de ningún LLM: se
valida en `evidencia.py`, antes de llamar a DeepSeek, no en
`deepseek.py` después de recibir su respuesta.

## §6 — Principio X: sin categoría de dato nueva

**Comprobado explícitamente, a diferencia de 012** (que sí encontró
IPs de la LAN en `socat_relays.json` y tuvo que justificarlas): los
campos que aporta la evidencia de inventario —
`categoria`/`tipo`/`contexto`/`mecanismo_vigilancia`/`nombre_actual`—
son nombres de software del propio homelab (por ejemplo,
`"amsterdam9.bautista.heartbeat"`, `"Agente Hermes/Bautista"`,
`"hermes"`) — misma naturaleza que `check_id`/`entity` ya enviados sin
objeción desde 010. Ninguna IP, credencial ni identificador de
dispositivo físico aparece en `gap_context()`
(`src/inventory/evaluate.py`) para los 5 tipos de brecha en alcance.
Sin justificación nueva que documentar para este feature.

## §7 — Prompt de DeepSeek: generalizado una sexta vez

**Decisión**: `_PROMPT_INSTRUCCIONES` añade "...o una brecha de
cobertura del propio inventario de monitorización (feature 013:
specs/013-diagnostico-inventario/) — un componente que se quedó sin
declaración de estado esperado, con la declaración caducada, sin
vigilancia, o cuyo fallo no llegaría al dashboard" a la lista ya
existente. **Sin cláusula nueva de restricción de contenido** (a
diferencia de la de relays en 012 §7): este origen no tiene ningún
invariante equivalente a "nunca nombres X" que dependa de lo que
responda el modelo — la única restricción de alcance
(`condicion_incumplida`) se aplica antes de la llamada, sobre el propio
dato de entrada (§5), no sobre la respuesta.

**`es_critico` para inventario — siempre `False`**: igual que discos,
HA, backups y relays.

## §8 — CLI: dos flags simétricos

**Decisión**:

```
python3 -m diagnostico.cli congelar --inventario-vivo NOMBRE
python3 -m diagnostico.cli congelar --inventario-historico "NOMBRE@EJECUCION_ID"
```

`NOMBRE` puede contener espacios (`"Agente Hermes/Bautista"`, `"Canal
de Telegram"`) — se entrecomilla igual que ya hace `--relay-vivo`.
`EJECUCION_ID` es un entero (`int(...)`, mismo tipo que `--since` en
`inventory.cli`) — a diferencia de `MOMENTO_ISO` en los demás orígenes
en diferido, aquí el localizador es un identificador de ejecución
discreto, no un instante continuo: las ejecuciones del inventario no
tienen cadencia fija (`disparador` puede ser manual o programado), así
que pedir un `MOMENTO_ISO` y buscar "la ejecución más cercana"
introduciría una tolerancia arbitraria que `EJECUCION_ID` evita del
todo — Miquel ya puede consultarlo con `python3 -m inventory.cli
--gaps` o revisando el histórico antes de diagnosticar.

## §9 — Nombre o ejecución inexistentes: se congela igual, con evidencia vacía

**Decisión**: mismo criterio ya establecido en 009/010/011/012para un
`check_id`/`label`/`nombre de relay` inexistente. Si `EJECUCION_ID` no
existe en `inventory.store.get_ejecucion()`, o si `NOMBRE` no aparece
entre los hallazgos de esa ejecución, el episodio se congela con
`inventario_hallazgo`/`inventario_brecha`/`inventario_comparacion` en
`None` — el diagnóstico resultante concluye `no_diagnosticable`
honestamente, nunca un error que impida congelar.

**Ventana temporal cuando la ejecución existe**: `ventana_inicio` =
`ventana_fin` = `ejecucion["fecha"]` — el momento real en que se
ejecutó el inventario, no `datetime.now()` (misma lección de 011 §9/012
§9: congelar el momento del episodio, no el momento de invocar
`congelar`). Cuando la ejecución no existe, no hay ninguna fecha real
que usar — se usa el momento de invocar `congelar` como único valor
disponible, igual que hace `congelar_relay_vivo` cuando no hay ninguna
muestra de referencia.

## §10 — Validación contra la línea base real: `EJECUCION_ID` es la última aparición, no la primera

**Hallazgo real, corrigiendo una lectura apresurada del material de
partida**: `BRIEFING.md` describe `#19`/`#28`/`#31`/`#52` como las
ejecuciones "hasta" las que cada brecha existió — es decir, la
**última** vez que aparecieron antes de resolverse, no la primera.
Comprobado en vivo contra `inventario.db`: las cuatro brechas reales
comparten `primera_ejecucion_id = 3` — nacieron todas en la misma
ejecución temprana (2026-08-07, cuando esas categorías se introdujeron
por primera vez en el inventario) y persistieron sin interrupción hasta
resolverse cada una en su propio feature (`#19`→`#20` el
2026-08-08 14:14-14:21, `#28`, `#31`, `#52` con patrones similares).

**Decisión de validación** (no de código): la validación en diferido
usa `EJECUCION_ID = 19/28/31/52` tal cual — son ejecuciones reales
donde la brecha existía, que es todo lo que pide FR-001. El propio
mecanismo de §4 resuelve la comparación contra `primera_ejecucion_id -
1 = 2` automáticamente, sin que Miquel tenga que calcular ni conocer
ese número — es precisamente el valor que demuestra que el mecanismo
funciona sin intervención manual, no algo que haya que elegir para
"maximizar la señal".

## §11 — Límite defensivo en `inventario_comparacion` (hallazgo real, investigando la línea base antes de implementar)

**Hallazgo real**: la ejecución #2 (el ancla real de las cuatro
brechas conocidas, según §10) tiene **0 brechas registradas** — parece
anterior a que `populate_brechas()` se conectara al flujo normal del
CLI (bootstrap de feature 001, no un estado "sano" real que comparar).
Consecuencia medida: `compare_runs(19, 2)` marca como "brecha nueva"
**319** de las 319 brechas reales de la ejecución #19 (`sin_declaracion`
sola ya son 308, la cola larga de `entidad_ha` sin triar todavía en esa
fecha — no se resolvió hasta 004/005). `compare_runs(52, 2)` da un
orden de magnitud similar. Enviar una lista de cientos de nombres sin
relación real con el componente diagnosticado es la misma categoría de
riesgo que ya motivó `HA_HISTORIAL_MAX_ENTRADAS` (010 §6) y
`BACKUP_ANOMALIA_MAX_LINEAS` (011 §3): ruido que puede alargar el
razonamiento del modelo sin aportar señal, con el mismo riesgo de
truncamiento por `finish_reason: "length"` ya documentado en 012 §11.

**Decisión, tomada en el diseño y no descubierta tarde** (mismo
espíritu que el hallazgo F1 de 012, aplicado esta vez antes de escribir
código): `INVENTARIO_COMPARACION_MAX_ENTRADAS = 30` — cada una de las
cuatro listas de `Comparacion` (`componentes_nuevos`,
`componentes_de_baja`, `brechas_nuevas`, `brechas_resueltas`) se
envuelve en `{"total": N, "muestra": lista[:30]}` antes de entrar en el
snapshot: el modelo ve el volumen real (que por sí solo ya es una
pista — "319 componentes sin declarar a la vez" sugiere un problema
sistémico, no uno aislado) sin recibir el listado completo. 30 es
holgado frente al caso real más pequeño con señal genuina (`brechas
nuevas` de `#28`/`#31`/`#52` individualmente rondan 1-2 entradas
relevantes de la propia categoría, aunque el total incluya cientos de
otras) y sigue siendo una fracción pequeña del peor caso medido (319).

**Alternativas consideradas**: filtrar la comparación a solo el
componente diagnosticado (descartada — pierde precisamente el contexto
de "qué más cambió a la vez" que justifica incluir el diff, §4).
Aumentar el límite a un número mayor porque el caso real está muy por
encima de 30 — descartada por ahora: el propio total (`"total": 319`)
ya transmite la magnitud sin gastar presupuesto de tokens en enumerarla
entera; si la validación en vivo demuestra que 30 es insuficiente para
una conclusión bien formada, es una revisión de constante, no de
diseño.

## §12 — Truncamiento real en episodios de inventario en diferido (hallazgo real, validación en vivo, 2026-08-12)

**Hallazgo real**: diagnosticando en vivo el episodio del componente
"Agente Hermes/Bautista" en la ejecución #19 (`--inventario-historico
"Agente Hermes/Bautista@19"`, `inventario_comparacion.brechas_nuevas.total
= 314`), la llamada real a través del CLI con
`DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` en su valor por defecto (2000)
terminó en `respuesta de DeepSeek inconsistente con el formato
esperado`. Investigado replicando el mismo prompt manualmente dos veces
más: el primer intento repitió `finish_reason: "length"` con
`reasoning_content` de 8.584 caracteres sin JSON final (mismo patrón
que 012 §11); el segundo, más inusual, dio `finish_reason: "stop"` pero
con `content` igualmente vacío y `reasoning_content` cortado a media
frase (8.714 caracteres) — el modelo "paró" sin haber llegado a escribir
la respuesta estructurada, un tercer patrón de fallo distinto tanto de
la recuperación vía `reasoning_content` de 010 (donde ese campo sí
contenía el JSON completo) como del truncamiento por `finish_reason:
"length"` ya conocido. Repetir la misma llamada con
`DIAGNOSTICO_DEEPSEEK_MAX_TOKENS=6000` sí produjo una respuesta
completa y correcta: `causa_probable`, coincidiendo con la causa real
conocida por los commits de 001-006 ("el heartbeat no tiene ruta hasta
el dashboard").

**No se tocó `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS`**: mismo criterio que
§10 de `specs/010-diagnostico-ha/research.md` y §11 de
`specs/012-diagnostico-relays/research.md` — es un valor ya fijado
deliberadamente (007, hallazgo B1 de `/speckit-analyze`) y es una
decisión de coste que afecta a los seis orígenes por igual, reservada
para Miquel. El propio mecanismo de SC-005 no exige que la llamada a
presupuesto por defecto tenga éxito — exige "causa probable o 'no se
puede diagnosticar' honesto", y `no_diagnosticable: respuesta de
DeepSeek inconsistente con el formato esperado` cumple la letra del
criterio sin inventar nada.

**La misma validación también tuvo un éxito limpio a presupuesto por
defecto**: diagnosticando el episodio de "Host de Uptime Kuma" en la
ejecución #28, la llamada real produjo `no_diagnosticable` bien
razonado (4 hipótesis, distinguiendo correctamente "brecha estructural
de cobertura" de "evidencia de que el host esté caído ahora mismo") sin
ningún síntoma de truncamiento — confirma que el problema no es
sistemático para todo episodio de inventario en diferido, solo para
los que combinan una `primera_ejecucion_id` muy antigua (como la #3
compartida por las cuatro brechas conocidas) con un `inventario_comparacion`
grande, igual que 012 encontró que la tasa de truncamiento variaba
según el tamaño real de la evidencia agregada, no era constante en
todo el origen.
