# Research — Generalizar el Diagnóstico a Discos

**Feature**: [spec.md](./spec.md)

## §1 — Migración de esquema: `contenedor` → `componente` + `origen`, idempotente sobre datos reales

**Decisión**: `episodios.contenedor` se renombra a `episodios.componente`
(genérico: nombre de contenedor o etiqueta de disco) y se añade
`episodios.origen TEXT NOT NULL DEFAULT 'contenedor'`. La migración se
aplica dentro de `store.connect()`, en el mismo punto donde hoy se
ejecuta `_SCHEMA` (`CREATE TABLE IF NOT EXISTS`): tras crear las tablas
si no existen, comprobar con `PRAGMA table_info(episodios)` si la
columna `origen` ya existe; si no, ejecutar
`ALTER TABLE episodios RENAME COLUMN contenedor TO componente` seguido
de `ALTER TABLE episodios ADD COLUMN origen TEXT NOT NULL DEFAULT
'contenedor'` (SQLite ≥ 3.25, ya disponible en el runtime real —
verificado). Las 14 filas ya persistidas por 007 quedan con
`origen='contenedor'` automáticamente por el `DEFAULT`, sin tocar su
contenido.

**Rationale**: `CREATE TABLE IF NOT EXISTS` no migra una tabla ya
existente — sin este paso, desplegar este feature contra el
`diagnostico.db` real de producción dejaría el código nuevo esperando
una columna `componente`/`origen` que no existe, rompiendo tanto lo
nuevo como lo ya desplegado por 007. La comprobación por
`PRAGMA table_info` hace la migración idempotente (mismo criterio que
"no fallar al ejecutar `init_db()` dos veces" que ya exige el propio
test de 007, `test_store.py`).

**Alternativas consideradas**: crear una tabla `episodios_v2` nueva y
migrar los datos con `INSERT ... SELECT`. Rechazada — más compleja sin
necesidad; `RENAME COLUMN`/`ADD COLUMN` son operaciones atómicas de
SQLite que no exigen reescribir filas.

## §2 — Identificador de un disco: `label`, no `path`

**Decisión**: un disco se identifica en el CLI y en `episodios.componente`
por su `label` (`"FastData"`, `"Storage"`, `"Sistema"`) — el mismo campo
que ya usan `disk_metrics`/`disk_metrics_near()` y que ya se muestra en
el dashboard, no por `path` (`/Volumes/FastData`, `/Volumes/Storage`,
`/`).

**Rationale**: `label` es el nombre estable y legible que Miquel ya
reconoce (mismo argumento que 007 usó para preferir el nombre del
contenedor sobre su ID interno, research.md de 007). `path` es
igualmente estable en este homelab, pero introduce un carácter (`/`)
incómodo como argumento de CLI y como valor de `componente` — sin
ninguna ganancia real sobre `label`.

## §3 — Evidencia de un episodio de disco: `disk_metrics`, mismo criterio de ventana que contenedores

**Zona horaria de `MOMENTO_ISO` (añadido 2026-08-11, hallazgo U2 de
`/speckit-analyze`)**: se interpreta como hora local sin marca de zona
— misma convención que ya tiene `disk_metrics.timestamp` (escrito por
`docker_monitor.py`, que corre en el host, no en un contenedor;
confirmado en vivo durante la sesión de 008: la última muestra de
`container_metrics`/`disk_metrics` coincide con `date` local, no con
`date -u`). La comparación contra `disk_metrics.timestamp` es directa,
sin ninguna conversión — mismo criterio que ya usa `congelar_historico()`
con `restart_history.timestamp` para contenedores. Esto es lo mismo que
ya vale para `--historico`/`--vivo` de contenedores; se deja explícito
aquí porque la sesión de 008 (mismo paquete) encontró un bug real por
una suposición de zona horaria equivocada — no repetir ese error aquí
por no haberlo dejado escrito.

**Decisión**:
- **Histórico** (`--disco-historico "LABEL@MOMENTO_ISO"`): ventana
  `[momento - 30 min, momento + 30 min]` sobre `disk_metrics` — misma
  `VENTANA_METRICAS_MINUTOS` que ya usa `congelar_historico()` para
  contenedores. Sin equivalente a `container_metrics_hourly` (no existe
  agregado horario permanente para discos hoy — `disk_metrics_daily`
  está vacía, comprobado en vivo al escribir el material de partida) —
  si la ventana no tiene muestras, el episodio queda con evidencia
  vacía y el propio motor concluye `no_diagnosticable`, igual que ya
  hace con contenedores fuera de retención.
- **En vivo** (`--disco-vivo LABEL`): las últimas N muestras disponibles
  de `disk_metrics` para ese disco (mismo patrón que
  `container_metrics_recientes()`), para que el modelo pueda razonar
  sobre una tendencia (¿está creciendo el uso?), no solo un punto.

**Rationale**: reutilizar exactamente `disk_metrics` (ya real, 13.992
filas) con el mismo criterio de ventana que 007 ya validó para
contenedores — ninguna decisión de diseño nueva, solo aplicar el mismo
patrón a una tabla distinta.

**Alternativas consideradas**: usar `disk_metrics_daily` como respaldo
para episodios fuera de la retención de `disk_metrics` (mismo papel que
`container_metrics_hourly`). Rechazada por ahora — la tabla existe pero
está vacía (nadie la rellena todavía, causa no investigada, fuera de
alcance de este feature); documentar la limitación es más honesto que
construir un respaldo que lee una tabla sin datos.

## §4 — `es_critico` para un episodio de disco: siempre `False`

**Decisión**: `congelar_disco_vivo`/`congelar_disco_historico` fijan
`es_critico=False` siempre — no se consulta `docker_critical()` (no
tiene sentido para un disco) ni se inventa una lista de "discos
críticos" nueva (spec.md, Assumptions).

**Rationale**: FR-008 de este feature prohíbe cualquier acción sobre
discos igual que FR-012 de 007 la prohíbe sobre contenedores — el campo
`es_critico` solo existe para que el prompt le diga a DeepSeek "no
propongas ninguna acción", y ese aviso ya aplica a todo episodio de
disco sin condición.

## §5 — Prompt de DeepSeek: generalizado sin perder la precisión ya conseguida

**Decisión**: `_PROMPT_INSTRUCCIONES` (`deepseek.py`) cambia su primera
frase de *"Eres un diagnosticador de causas probables para episodios de
contenedores Docker en un homelab doméstico"* a *"Eres un diagnosticador
de causas probables para episodios de un homelab doméstico — puede ser
un contenedor Docker caído o un disco con uso alto"*. El resto del
prompt (estructura del JSON, semántica exacta de `"confirmada"`, la
cláusula de contenedor crítico) no cambia — la corrección de la
ambigüedad de "confirmada" (`BITACORA.md`, sesión de 007) no es
específica de contenedores y sigue aplicando igual. `construir_prompt()`
recibe el `origen` del episodio y solo añade la cláusula de "sin acción
sobre críticos" cuando `es_critico` es cierto — que para discos nunca lo
es (§4), así que ningún disco lleva esa cláusula, pero tampoco la
necesita (FR-008 ya se cumple prohibiendo cualquier acción en el propio
alcance del feature, no en el prompt).

**Rationale**: cambiar solo la frase de encuadre y mantener intacta la
estructura ya validada (invariante FR-007, semántica de "confirmada")
es el cambio mínimo que generaliza sin arriesgar una regresión sobre lo
que 007 ya corrigió con evidencia real.

**Alternativas consideradas**: dos prompts completamente distintos, uno
por origen. Rechazada — duplicaría la lógica de invariantes (FR-007,
`parsear_respuesta()`) sin necesidad; la única diferencia real entre un
episodio de contenedor y uno de disco es la evidencia que se les pasa
(ya distinta por construcción, el propio JSON del snapshot), no las
reglas de conclusión.

## §6 — CLI: dos flags nuevos, mismo patrón `congelar`/`diagnosticar`/`mostrar`

**Decisión**: `congelar` gana dos opciones nuevas en su grupo
mutuamente excluyente ya existente
(`--historico`/`--vivo`/`--disco-historico`/`--disco-vivo`):

```
python3 -m diagnostico.cli congelar --disco-vivo LABEL
python3 -m diagnostico.cli congelar --disco-historico "LABEL@MOMENTO_ISO"
```

`diagnosticar`, `mostrar` y `--selftest` no cambian su firma — ya
operan sobre `episodio_id`, agnóstico al origen.

**Rationale**: mínimo cambio de superficie — reutiliza exactamente el
mismo verbo (`congelar`) y el mismo patrón mutuamente excluyente que ya
existe, en vez de introducir un verbo nuevo (`congelar-disco`) que
duplicaría explicación en `contracts/cli.md` sin necesidad real.

**Alternativas consideradas**: un flag `--origen {contenedor,disco}`
genérico combinado con `--vivo`/`--historico` ya existentes (por
ejemplo, `congelar --origen disco --vivo FastData`). Rechazada — el tipo
del argumento de `--historico` (un `int`, id de `restart_history`) no
tiene sentido para un disco (que se identifica por `LABEL@MOMENTO`, un
string compuesto) — mezclar los dos bajo el mismo flag habría exigido
parsear el mismo argumento de dos formas distintas según un flag
aparte, más confuso que dos flags nuevos y explícitos.
