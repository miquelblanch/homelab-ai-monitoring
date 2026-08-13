# Research — Remediación Automática, Primera Pieza (Rotación de Logs)

**Feature**: [spec.md](./spec.md)

## §1 — Por qué esta feature no depende del motor DeepSeek, y qué significa "diagnóstico" aquí

**Hallazgo real**, comprobado antes de especificar (`BRIEFING.md`,
"Feature 019 — material de partida"):

```
$ sqlite3 diagnostico.db "SELECT conclusion_tipo, count(*) FROM diagnosticos GROUP BY conclusion_tipo;"
no_diagnosticable|36
```

De los 36 diagnósticos reales producidos por `src/diagnostico/`
(features 007-017), **ninguno** ha concluido `causa_probable`. Atar
esta feature a que el motor confirme una causa la dejaría sin ningún
caso real contra el que validarla — rompería la disciplina de este
proyecto (siempre contra evidencia real, nunca solo sintética,
comprobada en cada feature desde 007).

**Decisión, confirmada con Miquel (AskUserQuestion, 2026-08-13)**: la
v1 actúa sobre condiciones deterministas verificables en el momento —
mismo patrón que `docker_monitor.py`, que tampoco usa ningún LLM.

**Sobre el Principio IV** ("Ninguna acción correctiva se ejecuta sin
un diagnóstico que la justifique"): este proyecto usa la palabra
"diagnóstico" en dos sentidos distintos, y hasta ahora coincidían
porque solo existía el sentido específico:

1. El artefacto formal de `src/diagnostico/` — la entidad
   `Diagnostico`/`Hipotesis`, producto de contrastar hipótesis contra
   evidencia con DeepSeek (007-017).
2. El sentido genérico de la palabra: una causa conocida y verificada,
   no inventada ni adivinada.

Una condición determinista y comprobada en el momento —"este fichero
concreto supera este umbral de tamaño porque nada lo rota"— es un
diagnóstico en el segundo sentido: conocido, verificable, sin ninguna
especulación de por medio. El *rationale* del Principio IV ("actuar
sin diagnóstico repite el problema que originó este proyecto:
reinicios automáticos sin conocer la causa") se cumple igual: aquí sí
se conoce la causa exacta antes de actuar, solo que no hace falta un
LLM para conocerla. Se documenta esta distinción explícitamente para
que quede escrita, no implícita — mismo criterio que ya aclaró el
alcance real del Principio XI en el feature 016.

**Sobre el Modelo Operacional B**: el texto actual dice "actúa de
forma autónoma únicamente en acciones reversibles y de bajo riesgo
definidas en la lista cerrada... Todo lo demás es propuesta que
espera aprobación humana explícita." Esta feature añade una capa: aun
estando en la lista cerrada, un tipo de acción **no** actúa de forma
autónoma hasta que Miquel lo activa explícitamente (FR-002/FR-003) —
la lista cerrada es condición necesaria, nunca suficiente por sí sola.
No contradice el modelo, lo precisa: el modelo nunca decía que estar
en la lista bastara para actuar sin más.

## §2 — `remediacion.db`, paquete independiente de `diagnostico`

**Decisión**: `src/remediacion/` no importa nada de
`src/diagnostico/`, y `remediacion.db` es una base nueva, sin relación
de esquema con `diagnostico.db` — mismo aislamiento que ya separa
`inventory` de `diagnostico` (paquetes hermanos, sin dependencia
cruzada). Un puente entre ambos (remediación disparada por un
`causa_probable` real del motor) queda fuera de esta feature — sin
ningún caso real hoy que lo justifique (research.md §1); es candidato
a un feature futuro si el motor empieza a producir causas ciertas.

## §3 — Estado esperado declarado: la lista cerrada de logs y su umbral

**Decisión**: `LOGS_VIGILADOS`, constante en `acciones.py` — lista
cerrada de `(nombre, nombre_fichero, umbral_bytes)`, con nombres de
fichero fijos (universo cerrado, no un dato externo — mismo criterio
que `MONITOR_JOBS` en `evidencia.py`, feature 017). El **directorio**
donde viven sí es configurable por variable de entorno —mismo patrón
que `MONITOR_HEARTBEATS_DIR`/`DASHBOARD_SOCAT_LOG` en features
anteriores—, precisamente para poder apuntar la validación por CLI de
`quickstart.md` a un directorio de prueba con ficheros del mismo
nombre, sin tocar nunca los reales hasta el escenario final deliberado:

```python
REMEDIACION_LOGS_DIR = Path(
    os.environ.get("REMEDIACION_LOGS_DIR", str(Path.home() / "Library/Logs"))
)
UMBRAL_ROTACION_BYTES_DEFAULT = int(
    os.environ.get("REMEDIACION_UMBRAL_ROTACION_BYTES", str(10 * 1024 * 1024))  # 10 MB
)
LOGS_VIGILADOS = [
    ("health-docker", "health-docker.log", UMBRAL_ROTACION_BYTES_DEFAULT),
    ("health-ha", "health-ha.log", UMBRAL_ROTACION_BYTES_DEFAULT),
]
# ruta real de cada uno = REMEDIACION_LOGS_DIR / nombre_fichero
```

**Por qué 10 MB**: comprobado en vivo el 2026-08-13 —
`health-docker.log` a 71 MB, `health-ha.log` a 11,6 MB, ambos sin
ninguna rotación y creciendo desde julio. 10 MB es un umbral holgado
(muy por debajo de los 71 MB reales, ligeramente por debajo de los
11,6 MB reales — los dos logs reales disparan la condición hoy mismo,
útil para la validación en vivo) sin ser tan bajo que rote logs sanos
de uso normal.

**Por qué solo estos 2 logs**: son los dos casos reales y activos del
barrido de agosto que siguen sin resolver — comprobado explícitamente
antes de especificar que los otros candidatos (los 4 plists corruptos,
`beszel-agent.log`) ya no son problemas reales hoy (`BRIEFING.md`,
"Feature 019"). Ampliar la lista de logs vigilados es un cambio de
alcance explícito, no algo que este feature deba anticipar.

## §4 — Rotar y deshacer, sin pérdida de datos nunca

**Decisión, la propiedad de diseño más importante de esta feature**
(FR-009/FR-010, SC-003/SC-004):

**Rotar** (`ejecutar_rotar_log`): renombra `foo.log` →
`foo.log.rotado-<YYYYMMDDTHHMMSS>` y crea un `foo.log` vacío nuevo.
Nunca trunca ni borra — el contenido anterior sigue existiendo
íntegro, solo con otro nombre.

**Deshacer** (`deshacer_rotar_log`) — el caso que exige más cuidado,
señalado explícitamente en spec.md Edge Cases: entre que se rotó un
log y que Miquel decide deshacerlo, pueden haberse escrito líneas
nuevas en el `foo.log` que quedó vacío tras la rotación. Sobreescribir
ese fichero con el rotado destruiría esas líneas nuevas — inaceptable
(SC-003: "0% de las rotaciones destruye contenido", aplicado también
al propio deshacer). Procedimiento:

1. Si `foo.log` existe y tiene contenido (algo se escribió desde la
   rotación), renombrarlo a `foo.log.tras-deshacer-<YYYYMMDDTHHMMSS>`
   — se conserva, nunca se pierde.
2. Renombrar el fichero rotado (`foo.log.rotado-...`) de vuelta a
   `foo.log`.

Resultado: el contenido de antes de la rotación vuelve a ser el
`foo.log` activo; lo que se hubiera escrito después de la rotación
sigue existiendo, con otro nombre, nunca destruido. Ningún paso de
este procedimiento borra ni trunca nada — coherente con Principio VI
("reversible significa que la vuelta atrás está documentada antes de
ejecutar la acción").

## §5 — Qué queda fuera del barrido de agosto, y por qué

Comprobado en vivo el 2026-08-13, antes de especificar:

| Hallazgo del barrido (01-08) | Estado real hoy | ¿Entra en esta feature? |
|---|---|---|
| 3 plists con JSON en vez de XML + 1 con XML mal formado | `plutil -lint` da OK en los 4 — ya arreglados | No — ya no es un problema real |
| `beszel-agent.log` sin rotar (217 MB) | El fichero ya no existe | No — ya no es un problema real |
| `health-docker.log` sin rotar (63 MB) | **71 MB, sigue creciendo** | **Sí — único caso de esta feature** |
| `health-ha.log` sin rotar (8,1 MB) | **11,6 MB, sigue creciendo** | **Sí — único caso de esta feature** |
| Seis relays escriben su log en `/tmp` | No investigado en esta sesión | No — candidato a feature futuro |
| 25/41 contenedores sin healthcheck | No investigado en esta sesión | No — candidato a feature futuro, y no es una "acción reversible" en el mismo sentido (cambiar un Dockerfile no es una acción operativa puntual) |
| Deduplicación de alertas | Es un fix de código del monitor, no una acción reversible sobre un componente | No — nunca encajó en el modelo de "acción reversible ejecutada por el agente" |

## §6 — CLI: mismo patrón que `diagnostico.cli`

**Decisión**:

```
python3 -m remediacion.cli comprobar
python3 -m remediacion.cli pendientes
python3 -m remediacion.cli aprobar INTENTO_ID
python3 -m remediacion.cli rechazar INTENTO_ID
python3 -m remediacion.cli deshacer INTENTO_ID
python3 -m remediacion.cli modo rotar_log --automatico
python3 -m remediacion.cli modo rotar_log --manual
python3 -m remediacion.cli historial rotar_log
python3 -m remediacion.cli --selftest
```

`comprobar` es el único punto de entrada que evalúa la condición
determinista — se ejecuta bajo demanda por Miquel en v1 (sin
LaunchAgent propio, FR-014 ya excluye notificación automática; un
cron que la dispare sola queda para cuando haya confianza suficiente
como para no necesitar revisar cada ejecución a mano).

## §7 — Ampliación de `LOGS_VIGILADOS`, 2026-08-13, mismo día tras validar

**Hallazgo real, pedido por Miquel al revisar el tamaño de los dos
logs rotados**: `health-docker.log`/`health-ha.log` no eran casos
aislados — ningún log de `~/Library/Logs/` tenía rotación, solo los
de `~/.hermes/profiles/bautista/logs/` (cubiertos por
`rotate_hermes_logs.sh`, mecanismo distinto y ya existente, con sus
propios umbrales de 500 KB-2 MB). El resto (`dashboard-socat.log` a
1,78 MB, `hermes-dashboard.log` a 1,34 MB...) tenía el mismo problema
de fondo, solo que más joven — sin límite, seguirían creciendo igual.

**Decisión**: ampliar `LOGS_VIGILADOS` de 2 a 17 entradas — todos los
ficheros `.log` que aparecen como `StandardOutPath`/`StandardErrorPath`
de un LaunchAgent `amsterdam9.*` en `~/Library/Logs/`, confirmado por
`grep` directo sobre los `.plist` reales (no una lista aproximada de
`ls`). Mismo umbral por defecto (10 MB) para los 17 — ninguno se
acercaba siquiera a 2 MB al ampliar la lista, así que no hace falta
un umbral distinto por fichero todavía; se puede ajustar por variable
de entorno si algún caso real lo pidiera más adelante.

**Quedan fuera, explícitamente**: los 4 logs de
`~/.hermes/profiles/bautista/logs/` (ya cubiertos por el mecanismo
existente — ampliar aquí también sería un tercer sistema de rotación
compitiendo con uno que ya funciona, violando el Principio VII, un
actor por acción); `metrics-retention.out`/`.err` (extensión distinta,
`.out`, no `.log` — mismo criterio de lista cerrada y explícita, no se
amplía el patrón sin comprobarlo primero); los logs de
`ebook2audiobook` (viven en un subdirectorio propio, no directamente
en `~/Library/Logs/`); y ficheros que no son logs de este proyecto en
absoluto (`.DS_Store`, `PhotosUpgrade.aapbz`, `SparkleUpdateLog.log`,
`fsck_hfs.log` — artefactos de macOS/apps de terceros, fuera del
universo que este feature debe tocar).

## §8 — Retención de rotaciones: 4 como mucho, mismo número que rotate_hermes_logs.sh

**Hallazgo real**: nada purgaba nunca los ficheros `.rotado-*` — cada
rotación se queda archivada para siempre, así que `~/Library/Logs/`
acabaría acumulando un fichero más por cada rotación de cada log, sin
límite. Encontrado al usar el dashboard (feature 020) y ver que los
dos logs ya rotados dejaban su histórico visible.

**Decisión, confirmada con Miquel**: `ROTACIONES_A_CONSERVAR = 4` —
mismo número que ya usa `rotate_hermes_logs.sh` (`KEEP=4`) para el
otro mecanismo de rotación del homelab, por consistencia. Con el
ritmo de crecimiento real observado (`health-docker.log` tardó ~12
días en pasar de 63 a 71 MB sin rotar), 4 rotaciones cubren varios
meses de histórico; en el peor caso (los 17 logs rotando justo al
umbral de 10 MB) son ~680 MB — nada frente a los TBs libres del
homelab.

`_purgar_rotaciones_antiguas()` se llama automáticamente al final de
`ejecutar_rotar_log()` — cada rotación deja como mucho 4 ficheros
`.rotado-*` para ese log, borrando los más antiguos por fecha (el
formato `%Y%m%dT%H%M%S` del propio nombre ordena igual
alfabéticamente que cronológicamente, sin necesidad de leer ningún
`mtime`). Nunca lanza — un fallo al purgar no debe romper la rotación
que ya se hizo.

**Efecto secundario real, documentado explícitamente**: `deshacer`
(User Story 5) ya no puede garantizarse para siempre — si han pasado
4 rotaciones más desde que se ejecutó un intento concreto, su fichero
rotado ya se purgó. `resolver_deshacer()` lo detecta explícitamente
antes de intentar el rename y falla con un mensaje claro
(`ValueError`), en vez de dejar escapar un `OSError` sin explicar —
mismo criterio de honestidad que el resto del proyecto: la
reversibilidad (Principio VI) sigue siendo real mientras la rotación
esté dentro de la ventana de retención, y se dice explícitamente
cuándo deja de estarlo, en vez de fingir que siempre es posible.

## §10 — Subcomando `tipos` (2026-08-13, sin nuevo número de feature)

**Hallazgo real, encontrado por Miquel al preguntar "¿cómo sé los tipos
de acción de remediación? ¿Cómo los obtengo?"**: no había ninguna
respuesta desde el propio programa. `modo` y `historial` exigen ya
saber el nombre del tipo como argumento posicional — ninguno sirve
para descubrirlo. La única vía hasta ahora era leer `acciones.py` o
consultar `configuracion_accion` a mano.

Agravante de diseño ya existente: `configuracion_accion` solo tiene
fila para un tipo tras su primer `get_modo()` (inserción perezosa,
FR-002) — así que ni siquiera consultar la tabla a mano habría
mostrado un tipo nuevo que todavía no se hubiera evaluado nunca.

**Decisión**: `acciones.TIPOS_ACCION = (TIPO_ACCION_ROTAR_LOG,)` —
registro explícito en código de todos los tipos que existen, única
fuente de verdad a extender el día que haya un segundo tipo.
`store.listar_modos(conn, tipos_conocidos)` cruza ese registro con
`configuracion_accion`, sin escribir nunca — a diferencia de
`get_modo()`, un tipo sin fila se reporta `manual` (mismo default de
FR-002) sin crearla. Expuesto como `python3 -m remediacion.cli tipos`,
solo lectura, coherente con la garantía 9 del contrato (sin escritura
fuera de una rotación real).
