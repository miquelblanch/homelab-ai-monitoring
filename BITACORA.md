# Bitácora

> Una línea por sesión, con fecha — ver `METODO.md`. Qué medir: tiempo
> especificar vs implementar, ambigüedades que encontró `clarify`, tareas
> que salieron bien sin intervención, veces que se corrigió el spec en
> vez del código, veces que se reescribió el spec entero, si el spec
> sigue describiendo lo que hay al cerrar el hito.

## 2026-08-13 — Auditoría de staleness tras cerrar los dos candidatos diferidos

Miquel preguntó "¿y ahora qué falta?" tras el trabajo de relays/healthchecks
y la eliminación de `adguardhome-sync`. Como en las veces anteriores esta
misma sesión, la respuesta correcta salió de investigar de cero, no de la
memoria de la conversación — y otra vez salió staleness real:

- **`constitution.md` llevaba dos amends con el pie de versión
  desincronizado**: el Sync Impact Report decía `1.2.2 → 1.2.3`, pero el pie
  del documento seguía en `1.2.0 | Last Amended: 2026-08-07`. Corregido a
  `1.2.4` (con este mismo cambio) y sincronizado.
- **"Alcance y Límites" de la constitución y el cierre de `README.md`**
  seguían listando los relays en `/tmp` y los contenedores sin healthcheck
  como "candidatos futuros" — ya resueltos el mismo día, ver la entrada
  anterior. Corregidos ambos para no dejar constancia de un candidato ya
  cerrado, aclarando que se resolvió por intervención directa sobre el
  homelab, no como un nuevo tipo de acción de `remediación automática`.
- **`CLAUDE.md` de este repo seguía diciendo "sin investigar todavía"** para
  los casos 3 y 4 de los cuatro que motivaron el proyecto (Beszel no vigila
  bien sus 3 sistemas; recordatorios de Nextcloud que no llegan) — ambos
  quedaron cerrados por `specs/003-latidos-beszel-calendario/` (implementado
  el 09-08, después de investigarse en `BARRIDO-2026-08-07.md`), pero la
  frase motivadora original nunca se actualizó tras cerrar el feature.
  Corregida para apuntar a la investigación y al feature que los cerró.
- **Dato para el método**: la staleness no aparece solo en los documentos
  que se tocan al cerrar un feature (`constitution.md`, `README.md`) — el
  `CLAUDE.md` de arranque, que se lee una vez al principio y rara vez se
  vuelve a abrir, llevaba semanas describiendo como abiertos dos casos ya
  cerrados. Cualquier fichero que declare "esto está sin resolver" es una
  promesa que hay que revisar cuando lo que describe deja de ser cierto,
  no solo cuando se toca por otro motivo.

## 2026-08-13 — Cobertura de los dos candidatos diferidos: relays en `/tmp` y contenedores sin healthcheck

Trabajo de infraestructura pura sobre el homelab privado (fuera de este
repo — sin `spec.md`, sin código versionado aquí), motivado por los dos
"candidatos futuros" que quedaron explícitos en la última corrección de
`constitution.md` (1.2.3). No es un defecto del proyecto: es la propia
constitución documentando dónde falta cobertura sistemática y
resolviéndolo cuando llega el turno.

**1. 16 relays `socat` escribían a `/tmp/*.log`, no a `~/Library/Logs/`.**
Un log en `/tmp` no sobrevive un reinicio y no lo vigila nada — el mismo
patrón de "sin estado esperado declarado" que motiva el Principio XIII.
Migrados uno a uno (confirmado con Miquel: "uno a uno, verificando cada
vez"), cada uno con `plutil -lint` → `bootout` → `bootstrap` →
verificación de `launchctl list` + `lsof -i :<puerto>` + fichero de log
nuevo. Cero fallos en los 16. Efecto secundario: al revisar los 16 salió
que 3 relays `com.homeassistant.tapo-*` siguen vivos pese a que
`tapo_control` está permanentemente deshabilitado, y los 2
`amsterdam9.frigate.relay-*` siguen vivos pese a que Frigate está
parado y en `NEVER_RESTART` — ninguno de los dos se ha tocado, quedan
pendientes de decisión de Miquel.

**2. 19 contenedores sin `HEALTHCHECK` → 17 resueltos (2 ya iban de un
piloto previo: `mosquitto`, `syncthing`).** Cada uno con: comprobar
herramientas disponibles dentro del contenedor (`curl`/`wget`/`nc`/CLI
propio), diseñar un check real (nunca uno que solo confirme que el
binario arranca), backup del `docker-compose.yml`, y para ficheros
compartidos con contenedores CRÍTICOS (`homeassistant` con
`mosquitto`/`matter-server`/`zigbee2mqtt`; `pangolin-server` con
`gerbil`/`traefik`/`crowdsec`/`cloudflare-ddns`) recrear solo el
servicio objetivo por nombre, nunca `docker compose up -d` a secas.
Los 17: `beszel`, `beszel-agent`, `beszel-docker-proxy`, `zigbee2mqtt`,
`matter-server`, `crowdsec`, `homelab-dashboard`,
`homelab-dashboard-proxy`, `n8n`, `speedtest-tracker`, `audiobookshelf`,
`qbittorrent`, `gbrain`, `minipaint`, `caldav-bridge` — 15 con
healthcheck real. Los otros 2, deliberadamente sin healthcheck:

- **`cloudflare-ddns`**: imagen `scratch`, sin shell, sin cliente HTTP,
  sin subcomando de estado ni endpoint propio. Cualquier check habría
  sido un placebo (`--version` solo confirma que el binario existe, no
  que el proceso vivo funciona). Mejor ninguno que uno falso.
- **`adguardhome-sync`**: tiene un endpoint documentado (`/healthz`),
  pero está roto — ver más abajo.

**Hallazgo real, no buscado: `adguardhome-sync` lleva roto desde al
menos el 28-06-2026.** Al probar su `/healthz` (el endpoint que la
propia documentación recomienda para Docker) la petición se quedaba
colgada sin límite. Los logs explican por qué: cada sincronización
(cada 15 min, 1.424 líneas de error en el log retenido) falla contra
**los dos** extremos —
  - Origen (Pi, `192.168.4.174`): `dial tcp ...:80: i/o timeout` — el
    mismo patrón "los contenedores de este Mac no alcanzan la LAN" ya
    documentado para Beszel el 2026-08-07, ahora confirmado en un
    cuarto contenedor.
  - Réplica (este Mac, `192.168.4.87`): `404 Not Found` en
    `/control/status` — el contenedor sí llega al Mac (coherente con
    el patrón conocido), pero el puerto/ruta configurados están mal.
  `/healthz` internamente repite esa misma llamada rota, así que
  cuelga en vez de responder — no es seguro apuntarle un healthcheck
  hasta arreglar el problema de fondo. Ninguno de los dos fallos se ha
  tocado — reportado a Miquel, pendiente de decisión.
  Efecto lateral notado de paso: su `docker-compose.yml`
  (`/Volumes/FastData/docker/adguard_home_sync/docker-compose.yml`)
  tiene las credenciales de AdGuardHome en texto plano, en contra de
  la regla 1 del `CLAUDE.md` general — tampoco tocado, solo anotado.
- **Dato para el método**: un candidato "diferido" en la constitución
  no es una tarea de checklist mecánica — investigar el segundo de los
  dos (`adguardhome-sync`) sacó a la luz un bug real de sincronización
  de seis semanas que nadie había visto, exactamente el tipo de hueco
  que el Principio XIII pide cubrir. La cobertura sistemática encuentra
  cosas que una lista de casos conocidos no habría encontrado.

## 2026-08-13 — Dos totales agregados en la sección de remediación (sin nuevo número de feature)

Miquel pidió ver, además de la tabla por log, el total de los
ficheros activos y el total de todo (activos + rotaciones archivadas).

- `escribir_snapshot()` ahora calcula `total_activos_bytes` (suma de
  los 17 ficheros activos) y `total_con_rotaciones_bytes` (+ todas
  las rotaciones `.rotado-*` de cada uno, research.md §8 de 019) — se
  recalculan enteros en cada `comprobar`, nunca se acumulan.
- Mostrados en la cabecera de la sección del dashboard, no como filas
  nuevas de la tabla. Sin ningún control nuevo — sigue siendo
  estrictamente de lectura, verificado igual que antes por inspección
  del JS servido.
- Validado en vivo: `total_activos_bytes` ≈ 6,25 MB (los 17 logs
  activos, pequeños tras la rotación reciente),
  `total_con_rotaciones_bytes` ≈ 89,35 MB (+ los ~83 MB de los dos
  ficheros ya rotados de `health-docker`/`health-ha`) — cuadra con lo
  esperado.
- Aprendida la lección de la sesión anterior: el test de
  `escribir_snapshot()` que ya aislaba el snapshot en una ruta propia
  se amplió para cubrir los totales sin tocar nunca el fichero real
  — verificado de nuevo con el `mtime` antes/después.

## 2026-08-13 — Bug real: `--selftest` sobreescribía el snapshot de producción del dashboard

Miquel reportó que la pestaña "Sistema" del dashboard solo mostraba
una línea (`health-docker`) en vez de los 17 logs.

- **Causa raíz**: `test_cli_comprobar_y_pendientes` y
  `test_cli_aprobar_rechazar_deshacer`
  (`tests/selftest/test_remediacion_cli.py`) llaman a
  `cli.main(["comprobar"])`, que desde el feature 020 también ejecuta
  `escribir_snapshot()`. Los dos tests parcheaban
  `REMEDIACION_LOGS_DIR`/`LOGS_VIGILADOS`/`store.db_path` para no
  tocar datos reales, pero **no** `acciones._snapshot_path` — así que
  cada `--selftest` sobreescribía el `remediacion_estado.json` **real**
  con datos de prueba (un solo log falso, tamaño fijo de 11 MB,
  apuntando a un directorio temporal ya borrado). Cada vez que se
  ejecutó el selftest tras validar la feature 020 (varias veces,
  incluida la sesión de retención de rotaciones), se pisó el snapshot
  real sin que ningún test lo detectara — los propios tests solo
  comprobaban códigos de salida, nunca el contenido del fichero.
- **Arreglo**: los dos tests ahora parchean también
  `acciones._snapshot_path` a una ruta temporal propia, con una
  aserción nueva que confirma explícitamente que el snapshot de
  prueba se escribió en su sitio — no solo que el comando devolvió 0.
  Verificado con un antes/después del `mtime` real: el selftest ya no
  lo toca.
- **Snapshot real regenerado**: `remediacion.cli comprobar` de verdad,
  vuelve a mostrar los 17 logs reales en el dashboard.
- **Dato para el método**: un test que aísla la mayoría de los efectos
  secundarios de una función pero se olvida de uno solo puede seguir
  contaminando datos reales en producción sin que el propio test lo
  note — la aserción "el comando terminó en 0" no basta cuando el
  comando tiene más de un efecto lateral. Aislar TODOS los efectos
  secundarios de una llamada nueva a una función ya wireada en el CLI,
  no solo los que motivaron el test.

## 2026-08-13 — Retención de rotaciones: 4 como mucho (sin nuevo número de feature)

Al usar el visor nuevo del dashboard, Miquel notó que los dos logs ya
rotados dejaban su histórico visible y preguntó qué era — llevó a
descubrir que nada purgaba nunca los ficheros `.rotado-*`.

- **Hallazgo real**: cada rotación se archiva para siempre —
  `~/Library/Logs/` acumularía un fichero más por cada rotación de
  cada uno de los 17 logs, sin ningún límite, indefinidamente.
- **Decisión, confirmada con Miquel**: `ROTACIONES_A_CONSERVAR = 4` —
  mismo número que ya usa `rotate_hermes_logs.sh` para el otro
  mecanismo de rotación del homelab, por consistencia. Con el ritmo
  de crecimiento real observado, cubre varios meses; en el peor caso
  (los 17 logs rotando justo al umbral) son ~680 MB, nada frente a
  los TBs libres.
- **Efecto secundario real, encontrado y corregido en el mismo
  cambio**: `resolver_deshacer()` no comprobaba si el fichero rotado
  seguía existiendo — con la purga nueva, deshacer un intento de más
  de 4 rotaciones atrás habría dejado escapar un `OSError` crudo sin
  explicar. Corregido para fallar con un mensaje claro
  (`ValueError`) antes de intentar el `rename()`.
- **Un fallo real en mi propio test durante la primera pasada**: el
  valor esperado de una aserción tenía un error de copiado (le
  faltaba el sufijo de hora a la marca de tiempo) — el código de
  retención era correcto desde el principio; el test comparaba mal.
  Corregido tras verificar el comportamiento real por separado antes
  de tocar nada más.
- **Sin ciclo SDD nuevo**: extensión de la feature 019 ya cerrada
  (documentada como research.md §8 de esa misma feature), no una
  capacidad nueva. Selftest: 5 aserciones nuevas, ~442 en total, todas
  en verde.

## 2026-08-13 — Feature 020, ciclo completo (specify → implement): primera superficie visual de remediación en el dashboard

Miquel pidió ver la lista de logs vigilados con sus tamaños "en alguna
pestaña del dashboard" — primera vez que el Frente 2/remediación tiene
una superficie visual, no solo CLI.

- **Hallazgo real que cambió la arquitectura, encontrado antes de
  diseñar nada**: el contenedor `homelab-dashboard` no monta
  `~/Library/Logs/` (comprobado en `docker-compose.yml`) — nunca ha
  podido leer esos ficheros directamente. Confirmado con
  `AskUserQuestion`: mismo patrón que ya usa el resto del homelab
  (`dump_socat_status.py`, `docker_monitor.py`) — un proceso en el
  host escribe un JSON a `/data` (ya montado), el dashboard solo lee.
  Sin tocar `docker-compose.yml` ni recrear el contenedor por ese
  motivo.
- **Tres piezas nuevas**: `escribir_snapshot()` en
  `src/remediacion/acciones.py` (este repo), conectada al final de
  `comprobar`; un LaunchAgent nuevo,
  `amsterdam9.remediacion.comprobar` (cada 15 min, `RunAtLoad=true`,
  mismo patrón que el resto de `amsterdam9.*`); y una sección nueva de
  solo lectura en `app.py`, dentro del panel "Sistema &
  almacenamiento" — sin ningún botón ni control, verificado
  explícitamente por inspección del HTML/JS servido (ni `button` ni
  `onclick` en el bloque nuevo).
- **Validado en vivo, extremo a extremo**: `comprobar` real escribe el
  snapshot con los 17 logs; el dashboard reconstruido lo sirve en
  `/api/data` (`remediacion.logs` con 17 entradas, `modo_rotar_log`,
  `generado_en`); quitar el fichero a mano confirma que el resto del
  dashboard sigue en `200` sin romperse (FR-007); cambiar el modo por
  CLI a `automatico` y volver a `comprobar` lo refleja en el
  dashboard en el siguiente ciclo, sin ningún control para cambiarlo
  desde ahí. El LaunchAgent se cargó de verdad
  (`launchctl bootstrap`) y su primera ejecución (`RunAtLoad`) ya
  actualizó el snapshot — la periodicidad de 15 min en sí no se
  esperó en vivo dentro de la sesión, es una propiedad estándar de
  `StartInterval` de launchd, igual que el resto de monitores del
  homelab.
- **Selftest**: ~8 aserciones nuevas para `escribir_snapshot()`
  (forma del JSON, log ausente ⇒ `tamano_bytes: 0`, nunca lanza ante
  un fallo real de escritura), sin romper ninguna de las ~440
  existentes.
- **Con esto, remediación automática deja de ser solo-CLI** — mismo
  hito que 008/018 marcaron para el motor de diagnóstico, ahora para
  su remediación.

## 2026-08-13 — Amplía `LOGS_VIGILADOS` de 019 de 2 a 17 logs (sin nuevo número de feature)

Al ver los tamaños reales de los logs recién rotados, Miquel preguntó
si el resto de `~/Library/Logs/` tenía el mismo problema.

- **Investigación real**: `grep` directo sobre los `StandardOutPath`/
  `StandardErrorPath` de los `.plist` de `amsterdam9.*` (no una lista
  aproximada de `ls`) — 16 ficheros `.log` reales, ninguno con
  rotación. Encontrado también un mecanismo de rotación **ya
  existente** (`rotate_hermes_logs.sh`, diario a las 04:00) pero
  limitado a `~/.hermes/profiles/bautista/logs/`, una carpeta
  distinta — por eso `~/Library/Logs/` llevaba sin ningún límite
  desde siempre.
- **Ampliación**: `LOGS_VIGILADOS` pasa de 2 a 17 entradas, mismo
  umbral (10 MB) para todas — ninguna se acercaba ni a 2 MB al
  ampliar. Quedan fuera explícitamente los 4 logs ya cubiertos por
  `rotate_hermes_logs.sh` (no duplicar un mecanismo que ya funciona,
  Principio VII) y los ficheros que no son logs de este proyecto
  (`.DS_Store`, artefactos de macOS/apps de terceros).
- **Sin ciclo SDD nuevo**: es una extensión de datos de la feature 019
  ya cerrada (mismo mecanismo, ya validado a fondo), no una capacidad
  nueva — documentada como research.md §7 de esa misma feature, con
  un test nuevo que fija la lista real (17, sin duplicados, ninguna
  coincide con un componente crítico).
- **Validado en vivo**: `comprobar` contra los 17 logs reales no crea
  ninguna propuesta — los 15 nuevos siguen muy por debajo del umbral,
  confirmando que la ampliación no genera falsos positivos.

## 2026-08-13 — Feature 019, ciclo completo (specify → implement): remediación automática, primera pieza — el sistema escribe sobre el homelab real por primera vez

Mismo modo que 013-018: investigación propia en esta sesión, material
de partida escrito antes de especificar. Es el feature de mayor riesgo
real de todo el proyecto — el primero que actúa sobre el homelab, no
solo lo lee.

- **Qué se pidió**: Miquel pidió arrancar Frente 2/remediación con un
  sistema de interruptor manual/automático por tipo de acción, que él
  controla siempre, sin que el sistema se autopromueva.
- **Tres decisiones de diseño confirmadas por `AskUserQuestion` (todas
  la opción recomendada)**: granularidad por tipo de acción (no por
  componente individual), interfaz solo CLI, y el requisito para pasar
  a automático es únicamente la decisión de Miquel (con historial
  visible, sin barrera de aciertos mínimos).
- **Hallazgo real que obligó a repensar el alcance**: de los 36
  diagnósticos reales producidos por el motor DeepSeek (007-017),
  **ninguno** ha concluido `causa_probable` — todos honestos
  `no_diagnosticable`. Atar la remediación a ese motor la habría
  dejado sin ningún caso real que validar hoy. Segunda ronda de
  `AskUserQuestion`, también recomendada: la v1 actúa sobre
  condiciones deterministas (mismo patrón que `docker_monitor.py`, sin
  IA), y el primer y único tipo de acción es "rotar un log sin rotar",
  comprobado como problema real y activo (`health-docker.log` a 71 MB,
  `health-ha.log` a 11,7 MB) — los otros candidatos del barrido de
  agosto (plists corruptos, `beszel-agent.log`) ya estaban arreglados
  o el fichero ya no existía.
- **Tensión real con el Principio IV y el Modelo Operacional B,
  documentada explícitamente en el plan**: "diagnóstico" se usa en dos
  sentidos en este proyecto (el artefacto formal de `src/diagnostico/`
  y el sentido genérico de causa conocida y verificada); una condición
  determinista satisface el segundo sentido. Y estar en la lista
  cerrada de acciones reversibles es condición necesaria para actuar,
  nunca suficiente por sí sola — cada tipo de acción sigue empezando
  en modo manual hasta que Miquel lo activa. Mismo criterio de
  honestidad ya aplicado al Principio XI en 016.
- **Analyze encontró una inconsistencia real**: `data-model.md` listaba
  un estado `"aprobado"` intermedio que el diseño real nunca escribe
  (`aprobar` ejecuta la rotación en la misma llamada) — corregido en
  spec.md, data-model.md y tasks.md antes de implementar.
- **Paquete nuevo, `src/remediacion/`**, independiente de
  `src/diagnostico/` — sin DeepSeek, sin dependencia cruzada. La
  propiedad de diseño más cuidada: la rotación de un log **nunca
  trunca ni borra**, siempre renombra; deshacer tiene un procedimiento
  de dos pasos para nunca sobreescribir contenido escrito después de
  la rotación (verificado explícitamente con un test que escribe
  contenido nuevo tras rotar y comprueba que sobrevive).
- **Validación en vivo, incluyendo la producción real** — con permiso
  explícito de Miquel (`AskUserQuestion`) para el paso final: los 6
  escenarios de `quickstart.md`, los 5 primeros contra logs de prueba
  en un directorio temporal (nunca los reales), y el sexto contra
  `health-docker.log`/`health-ha.log` de verdad — **aprobados y
  rotados de verdad**: 71,4 MB y 11,7 MB conservados íntegros en sus
  ficheros rotados, originales a 0 bytes, listos para que los
  LaunchAgents sigan escribiendo en el siguiente ciclo sin reiniciar
  nada.
- **Selftest**: ~35 aserciones nuevas repartidas en 3 módulos
  (`test_remediacion_store`, `test_remediacion_acciones`,
  `test_remediacion_cli`), un fallo propio encontrado y corregido en
  la primera pasada (un test de CLI comprobaba el tamaño del fichero
  *después* de ya haber llamado `deshacer`, no antes) — no un fallo
  del código, del propio test.
- **Dato para el método**: la disciplina de "investigar antes de
  especificar" pagó de la forma más importante hasta ahora — sin
  comprobar cuántos `causa_probable` reales existían, esta feature se
  habría diseñado atada a un motor sin ningún caso real que ofrecerle,
  y se habría descubierto el problema mucho más tarde, con código ya
  escrito. Encontrarlo en la fase de investigación costó una consulta
  SQL.

## 2026-08-13 — Cierra la limitación de `relay` documentada en 012 (sin feature, sin ciclo SDD)

Tras el feature 018, Miquel preguntó por la limitación de `relay`
("nunca cuál relay concreto en diferido") y pidió comprobar si de
verdad no había manera de arreglarla de cara al futuro — la respuesta
inicial fue correcta pero incompleta: sí hay una manera, solo que
excede el alcance de este repo (Frente 1, no Frente 2). Se arregló en
dos partes.

- **Parte 1, fuera de este repo**: `dump_socat_status.py`
  (`/Volumes/FastData/homelab/scripts/`, sin control de versiones) solo
  logueaba el recuento agregado (`"X/Y ok"`) en
  `dashboard-socat.log`. Se cambió para que, cuando falle algún relay,
  liste también sus nombres (`"1/3 ok — fallan: HA Shelly, Beszel
  AdGuard"`). Copia de seguridad hecha antes de editar; verificado que
  el regex que ya usa `evidencia.py` (`_PATRON_LINEA_RELAY`) sigue
  emparejando el `X/Y ok` de ambos formatos sin romperse.
- **Parte 2, en este repo**: generalizado `_agregado_relays_ventana()`
  para capturar el grupo nuevo "fallan" (lista vacía en cualquier línea
  de antes del 2026-08-13, honesto con el histórico que no puede
  recuperarse); nueva función `nombres_relay_evidenciados()`. La
  cláusula del prompt (`_PROMPT_CLAUSULA_RELAY_AGREGADO`) y la
  comprobación en código que rechazaba cualquier mención a un relay en
  diferido (hallazgo F1 de 012) se reescribieron para permitir nombrar
  un relay **solo si aparece de verdad en la evidencia de esa
  ventana** — antes rechazaba cualquier nombre, ahora solo los que no
  tienen respaldo real.
- **Validación en vivo real, no solo tests**: simulado un log con una
  línea `fallan: HA Shelly`, congelado un episodio histórico real
  contra él (`--relay-historico`), y diagnosticado — DeepSeek nombró
  "HA Shelly" en la conclusión y **no fue rechazado**, confirmando el
  circuito completo (log → evidencia → prompt → validación de
  respuesta) de punta a punta. Selftest: 2 tests existentes
  actualizados (dependían del texto literal de la cláusula vieja) y 4
  nuevos, todos en verde.
- **Retroactividad, honesta**: el cambio no repara el histórico ya
  escrito (dashboard-socat.log tiene detalle solo desde ahora) — se
  documentó explícitamente en los docstrings y en la cláusula del
  prompt, mismo criterio de "no inventar evidencia que no existe" que
  el resto del proyecto.
- **Dato para el método**: cuando Miquel insiste en revisar algo que
  ya se dio por cerrado ("revísalo bien"), vale la pena — la primera
  respuesta (§ sesión anterior) era cierta pero se quedaba corta: "no
  hay forma" es distinto de "no hay forma dentro del alcance actual, y
  nadie la ha construido todavía". La segunda revisión, más a fondo
  (leer el script real en vez de fiarse del resumen de research.md ya
  escrito), encontró que sí era arreglable y de hecho trivial.

## 2026-08-13 — Feature 018, ciclo completo (specify → implement): generaliza el visor del dashboard a los 9 orígenes restantes — y encuentra un bug crítico en producción

Mismo modo que 013-017: investigación propia en esta sesión, material
de partida escrito antes de especificar. Punto 2 del listado de "qué
falta" de esta misma sesión, tras cerrar la deuda documental (punto 4)
y los latidos de monitores (punto 3, feature 017).

- **Qué se pidió**: extender el visor de diagnósticos del dashboard
  (feature 008, solo mostraba `contenedor`) a los otros 9 orígenes ya
  generalizados en `src/diagnostico/` (007-017).
- **Hallazgo crítico, encontrado investigando antes de especificar**:
  el visor de `contenedor` estaba **roto en producción desde hacía dos
  días**. `get_diagnostico_para_alarma()` seguía consultando `WHERE
  contenedor = ?`, columna que el feature 009 renombró a
  `componente`+`origen` el mismo día 2026-08-11, después de 008.
  Comprobado ejecutando la consulta real contra `diagnostico.db`:
  `Error: in prepare, no such column: contenedor`. El fallo se traga
  en silencio (a propósito, para no tumbar `/api/data`), así que nadie
  lo había notado — violación activa del Principio XII (Precisión del
  Dashboard, NO NEGOCIABLE). Se arregló como User Story 1 (P1), antes
  de generalizar nada.
- **Complejidad real encontrada al mapear los 10 orígenes de alarma
  contra `diagnostico.db`**: ni la identidad de emparejamiento ni la
  disponibilidad de una ventana temporal son uniformes. Cuatro
  orígenes usan un identificador real distinto de lo que muestra la
  alarma (HA: `cid` no `label`; latido: `job` no `label`; agente:
  `label` completo no `short`; host externo: nombre canónico no el de
  pantalla). Dos orígenes (`backup`, `hub_beszel`) no tienen ninguna
  identidad estable — su `componente` es el momento del propio
  diagnóstico. Ocho de los diez no tienen ningún ancla temporal real
  en la alarma (solo `contenedor` y `ha` la tienen). `relay` solo
  puede emparejar diagnósticos hechos en vivo por nombre — en
  diferido, la evidencia agregada nunca identifica cuál relay
  concreto, limitación real del motor (012), no de este feature. Y los
  Crons de Hermes, que comparten la alarma visual `agentes` con los
  LaunchAgents, quedan fuera de alcance: ningún origen del motor los
  cubre.
- **Decisión de diseño**: una única función generalizada,
  `get_diagnostico_para_origen(origen, identidad, down_since=None)`,
  sustituye a la rota `get_diagnostico_para_alarma()` — tres ramas
  según haya o no identidad y ancla temporal.
- **Analyze**: pase limpio (comprobación cruzada manual de que los
  campos "antigüedad" de backup/monitores/beszel_hub son duraciones,
  no momentos ISO, confirmando que no debían tratarse como
  `down_since`).
- **Bug real encontrado en la validación en vivo, no en analyze**: la
  primera implementación de `_diagnostico_episodio_mas_reciente()`
  devolvía la lista entera de `_diagnostico_db_query()` en vez de su
  primer elemento — `TypeError: list indices must be integers` al
  probar el primer caso real (contenedor). Corregido antes de seguir
  validando el resto.
- **Validación en vivo, contra el dashboard real reconstruido**: los
  10 orígenes probados uno a uno contra episodios reales
  (`docker exec homelab-dashboard python3 -c ...`) — contenedor
  (bug corregido), disco, latido, HA (por `cid`), backup, hub_beszel,
  agente (por `label` completo), host externo (nombre canónico),
  inventario, y la limitación de relay confirmada explícitamente (un
  episodio en diferido no empareja con un nombre de relay). Contrato
  verificado contra `/api/data` real: 0 alarmas sin la clave
  `diagnostico`, 0 agrupadas con diagnóstico, 0 crons con diagnóstico.
  Contenedor sano tras la reconstrucción (`docker compose up -d
  --build`), 0 huérfanos en `diagnostico.db` (24 episodios, 35
  diagnósticos tras la sesión).
- **Riesgo operativo real, distinto de cualquier feature anterior**:
  todo el código vive en `homelab-dashboard/scripts/app.py`, **sin
  control de versiones** — se hizo copia de seguridad con marca de
  tiempo antes de editar, y verificación de salud del contenedor
  (`docker ps` + `curl /api/data`) tras cada reconstrucción.
- **Dato para el método**: la tercera vez consecutiva (tras 016, 017)
  que la investigación previa a especificar encuentra algo que nadie
  sabía — esta vez no una limitación documentable, sino una regresión
  activa en producción. Vale la pena, antes de generalizar cualquier
  pieza ya construida, comprobar que la pieza original todavía
  funciona contra el estado real del sistema, no solo contra lo que
  dice su propia documentación.

## 2026-08-13 — Feature 017, ciclo completo (specify → implement): décimo y último mecanismo relacionado — cierra los latidos de monitores

Mismo modo que 014/015/016: investigación propia en esta sesión,
material de partida escrito antes de especificar, sin pausas. Punto 3
del listado de "qué falta" de esta misma sesión (tras cerrar la deuda
documental del punto 4).

- **Qué se pidió**: el último mecanismo relacionado con la Central de
  Alarmas que quedó explícitamente pendiente desde 016 — los latidos
  de monitores (`get_monitor_heartbeats()`), que detecta un monitor
  cargado pero colgado en silencio (a diferencia de 016, que detecta
  si el propio proceso desapareció).
- **Tres hallazgos reales encontrados investigando antes de
  especificar, ninguno conocido de antemano**:
  1. Existen **dos listas independientes** de "qué jobs tienen
     latido" que no coinciden: `app.py::MONITOR_JOBS` (8 jobs, la que
     alimenta el dashboard y las alarmas reales) y
     `heartbeat.py::DEFAULT_MANIFEST` (7 jobs, la que alimenta
     `heartbeat.py --report` y el informe de Telegram). Tres jobs
     (`telegram-monitor`, `beszel-hosts`, `bautista-calendar`)
     escriben su latido pero son invisibles para el informe de las
     09:00. Documentado y decidido: este feature usa la lista del
     dashboard, por ser la que da nombre al mecanismo excluido en 016.
  2. El propio cálculo de `ok` de `get_monitor_heartbeats()` depende
     **únicamente** de la edad del latido, nunca del campo `status`
     que cada latido también guarda — un job a tiempo con
     `status:"error"` se muestra sano en el dashboard hoy. Distinto
     del cálculo de `heartbeat.py::report()`, que sí combina ambos.
     Una **tercera** inconsistencia real entre los dos mecanismos,
     encontrada leyendo el código exacto antes de implementar.
  3. Ninguna de las dos inconsistencias se corrige en este feature —
     son defectos reales del homelab privado (`heartbeat.py`/`app.py`
     no viven en este repo), documentados y dejados fuera
     explícitamente (FR-010), igual que 012 no amplió la vigilancia de
     relays.
- **Analyze encontró una inconsistencia real de severidad MEDIA**,
  autocorregida antes de implementar: el texto literal para "sin
  latido nunca leído" estaba mezclado entre dos frases de mecanismos
  distintos (`"nunca ha latido"` de `heartbeat.py::report()`, que no
  es el mecanismo replicado, vs. `"sin latido"` de
  `get_monitor_heartbeats()`, que sí lo es) — corregido en
  `data-model.md`, `tasks.md`, `contracts/cli.md` y `plan.md` antes de
  tocar código.
- **Segundo feature de la serie sin modo diferido** (el primero fue
  016, mismo tipo de limitación real: cada `<job>.json` se sobreescribe
  en cada ciclo, sin tabla histórica en ningún sitio del homelab).
  Estructuralmente casi idéntico a 016 salvo por una pieza nueva de
  verdad: sí hay un veredicto `ok` ya calculado que replicar con
  precisión (como en HA/010), así que sí lleva una cláusula de prompt
  nueva (`_PROMPT_CLAUSULA_LATIDO_ESTADO`) — 016 no la necesitaba.
- **Validación en vivo** (quickstart.md, 6 escenarios): episodio 6
  (007) intacto; dos jobs reales sanos (`docker-monitor`,
  `inventario-cobertura`) concluyen `no_diagnosticable` sin inventar
  causa; job inexistente entre los 8 congela con evidencia vacía y
  concluye honesto; mismo episodio diagnosticado dos veces da el mismo
  `conclusion_tipo` (SC-001); límite de gasto a 0 € bloquea la llamada;
  `congelar --help` no muestra ningún `--latido-historico`. 0
  huérfanos en `diagnostico.db` tras la sesión (16 episodios, 28
  diagnósticos, 52 hipótesis, acumulado real desde 007).
- **Selftest**: ~19 aserciones nuevas, todas en verde a la primera
  ejecución (`Todo OK`).
- **Fidelidad del spec**: sigue describiendo exactamente lo que hay al
  cerrar — ninguna sorpresa de última hora en implementación.
- **Dato para el método**: la investigación previa a especificar sigue
  encontrando hallazgos reales no triviales incluso en el feature "más
  simple" de la serie por segunda vez consecutiva (el primero fue 016)
  — comparar el código exacto de los dos mecanismos relacionados
  (`heartbeat.py` vs. `app.py`) antes de decidir cuál replicar evitó
  construir sobre una lista equivocada de jobs, y sirvió además para
  documentar (sin corregir) un defecto real del propio homelab que
  nadie había notado hasta ahora.
- **Con este feature se cierran los 10 de 10** — los 9 orígenes de la
  Central de Alarmas (006) más el mecanismo relacionado que había
  quedado pendiente desde 016. No se conoce ningún origen ni mecanismo
  relacionado sin generalizar. El Frente 2 del proyecto (diagnóstico)
  queda completo en su generalización; la remediación automática
  (Principios V-VI) y la superficie en el dashboard para 9 de los 10
  orígenes siguen fuera de alcance, sin cambios respecto a lo decidido
  en features anteriores.

## 2026-08-13 — Corrección de deuda documental en la constitución (sin feature, sin ciclo SDD)

Tras cerrar los 9 orígenes con el feature 016, se preguntó a Miquel qué
quedaba pendiente del proyecto. Entre los cuatro puntos identificados
(remediación automática nunca iniciada, visor del dashboard limitado
al origen `contenedor`, "Latidos de monitores" fuera de alcance de
016, y esta deuda documental), eligió el de menor detalle.

- **Qué se corrigió**: `.specify/memory/constitution.md`, sección
  "Alcance y Límites → Fuera de alcance en v1", seguía diciendo
  "diagnóstico de Home Assistant y relays socat" como fuera de
  alcance, pese a llevar implementados desde los features 010 y 012.
  Se había detectado ya durante el `/speckit-analyze` del feature 015
  y quedó anotado sin corregir.
- **Cambio**: se retira esa mención del "fuera de alcance" y se añade
  un párrafo explícito listando los nueve orígenes ya generalizados
  (contenedor, disco, HA, backup, relay, inventario, host externo, hub
  de Beszel, agente), dejando claro que lo que sigue fuera de alcance
  para 009–016 es la capa de **remediación automática**, no el
  diagnóstico. Versión de la constitución: 1.2.0 → 1.2.1 (aclaración,
  sin cambio de principios).
- **No es una sesión SDD**: no se ejecutó `/speckit-*` — es una
  corrección directa de un documento de gobierno, fuera del ciclo de
  features.
- **Dato para el método**: una nota de "detectado pero no corregido"
  dejada durante un `/speckit-analyze` (como la de 015) puede
  quedarse pendiente varias sesiones sin que nadie la retome hasta que
  se pregunta explícitamente "¿qué falta?". Vale la pena que ese tipo
  de nota incluya dónde vive el defecto exacto (fichero y sección),
  no solo que existe — aquí sí lo tenía, y eso fue lo que hizo la
  corrección trivial en vez de una nueva investigación.

## 2026-08-12 — Feature 016, ciclo completo (specify → implement), noveno y último origen — cierra la Central de Alarmas

**Mismo modo que 014/015**: investigación propia en esta sesión,
material de partida escrito antes de especificar, sin pausas.

- **Qué se pidió**: el último origen de los 9 — los LaunchAgents
  (`amsterdam9.*`, `com.homeassistant.*`, `ai.hermes.*`) que ejecutan
  toda la automatización del homelab.
- **Ambigüedad real encontrada en el propio histórico de
  `BRIEFING.md`, resuelta antes de especificar**: la tabla de orígenes
  original (feature 006) listaba **dos** filas de "Automatización":
  `LaunchAgents` y `Latidos de monitores`. La segunda desapareció de la
  lista de "orígenes restantes" entre los materiales de 011 y 012
  **sin que ningún feature la cerrara** — inconsistencia real del
  propio proyecto, no una decisión tomada. Documentada explícitamente:
  este feature cierra `LaunchAgents` (uso consistente del término
  "agentes" en el resto de `BRIEFING.md` desde 012), `Latidos de
  monitores` queda fuera, disponible para un feature futuro si Miquel
  decide cerrarlo — no se amplió el alcance sin que él lo decidiera.
- **El hallazgo estructural más importante de la serie**: este es el
  **único origen sin ningún modo diferido posible**, no por decisión
  de alcance sino por ausencia real de datos — comprobado
  explícitamente: `launchagents_raw.txt` se sobreescribe cada 5 min sin
  historial; su log tiene 9.392 líneas, todas vacías (`launchctl
  list > fichero` no escribe nada en `stdout` por sí solo); ninguna
  base de datos del homelab tiene una tabla histórica de LaunchAgents.
  Documentado explícitamente en el `Constitution Check` del plan como
  cumplimiento **parcial** del Principio XI (Reproducibilidad
  Diferida) — la primera vez en el proyecto que un principio "DEBE" no
  se cumple en su sentido literal completo para un origen, justificado
  por una limitación real y verificada, no forzado con un mecanismo
  ficticio ni ocultado.
- **El feature más simple de toda la serie**: una sola función de
  evidencia (`_agente_actual`), sin subprocesos, sin husos horarios,
  sin consultas externas — un fichero de texto plano ya existente, con
  el mismo cálculo exacto que ya usa el dashboard.
- **`/speckit-analyze` no encontró hallazgos propios** — segunda vez
  consecutiva (015, 016) sin ninguna corrección antes de implementar.
- **Tareas implementadas sin intervención: 15 de 15** — sin ningún
  hallazgo de implementación en la validación en vivo. Un detalle
  menor descubierto en vivo, no un error: el label real del agente que
  ejecuta `docker_monitor.py` es `amsterdam9.health.docker`, no
  `amsterdam9.docker-monitor` como se supuso al planificar el
  Escenario 2 — el intento fallido sirvió, sin querer, como el propio
  Escenario 3 (label inexistente).
- **Validación real**: los 6 escenarios de `quickstart.md` contra
  `launchagents_raw.txt` real y DeepSeek real — dos agentes reales
  sanos (`amsterdam9.morning-report`, `amsterdam9.health.docker`),
  ambos `no_diagnosticable` bien razonado (SC-004). Coste nuevo:
  ~0,008 €.
- **Veces que se corrigió el spec en lugar del código**: 0.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí.
- **Dato para el método — cierre del objetivo del proyecto**: con este
  feature se generalizan los **9 de 9** orígenes de la Central de
  Alarmas (contenedores, discos, HA, backups, relays, inventario,
  hosts externos, hub de Beszel, agentes) al motor de diagnóstico de
  episodios. Ningún origen queda pendiente. El Frente 2 del proyecto
  (diagnóstico) queda completo en su generalización; la remediación
  automática (Principios V-VI de la constitución) sigue fuera de
  alcance, sin cambios respecto a lo decidido en la sesión de feature
  006.

## 2026-08-12 — Feature 015, ciclo completo (specify → implement), octavo origen, el feature con menos infraestructura nueva de la serie

**Mismo modo que 014**: "hazlo directamente todo tú", investigación
propia en esta sesión, material de partida escrito antes de
especificar.

- **Qué se pidió**: octavo origen de la Central de Alarmas — el
  propio hub de Beszel, distinto del host externo individual (014, ya
  cerrado): no "¿está arriba el host X?", sino "¿el hub sigue
  vigilando *algo* de verdad, o se quedó colgado?". El mecanismo ya
  existía (`app.py::get_beszel_hub_status()`, feature 003) — sano solo
  si no todos los sistemas registrados están caducados a la vez.
- **Hallazgo real que cambió la validación esperada, comprobado antes
  de escribir el spec**: se esperaba reutilizar la avería real que
  validó 014 (routing de contenedores roto, 30 jul-7 ago). No sirve
  para este origen — comprobado en vivo: `Mac Mini Server` (el tercer
  sistema del hub, el propio Mac) no tuvo ningún hueco en todo el mes
  de retención, porque su agente se comunica con el hub en local, sin
  pasar por el routing que se rompió. Durante toda esa avería el hub
  estuvo `sano=True` en todo momento — nunca fue un episodio de "hub
  caído". Documentado explícitamente en spec.md/research.md como
  ausencia de línea base real, mismo tratamiento honesto que 009/010/011
  tuvieron al arrancar — no se inventó un caso sintético para
  evitarlo.
- **El feature con menos infraestructura genuinamente nueva de toda la
  serie**: reutiliza tal cual, sin reimplementar nada, cuatro
  constantes y tres funciones ya construidas en 014
  (`BESZEL_HOSTS_JSON`, `BESZEL_HOSTS_MAX_AGE_S`, `BESZEL_HUB_VOLUME`,
  `_docker_bin()`, `_a_utc_madrid()`, `_resumen_system_stats()`). Las
  únicas piezas nuevas: `_hub_beszel_actual()` (mismo cálculo que
  `get_beszel_hub_status()`, con datos que ya existían),
  `_consultar_beszel_hub_todos_sistemas()` (la misma consulta de 014
  con un `LEFT JOIN` en vez de filtrar por sistema) y
  `_resumen_por_sistema()` (agrupa y reutiliza
  `_resumen_system_stats()` por sistema). Sin identificador de
  componente, mismo patrón que backup (011) — solo hay un hub.
- **`/speckit-analyze` no encontró hallazgos propios de este feature**
  — primera vez desde 011 sin ningún hallazgo nuevo que corregir antes
  de implementar. Nota aparte, no de este feature: `constitution.md`
  sigue diciendo "diagnóstico de Home Assistant y relays socat" está
  "fuera de alcance en v1" pese a que 010/012 ya lo implementaron —
  deuda de documentación acumulada, anotada sin tocarla.
- **Tareas implementadas sin intervención: 21 de 21** — sin ningún
  error de test propio ni hallazgo de implementación encontrado en la
  validación en vivo, primera vez en la serie 012-015 sin ninguna
  corrección de última hora.
- **La garantía central del feature (SC-005), verificada sin línea
  base real**: diagnosticar en diferido un momento dentro de la
  avería de 014 confirmó exactamente lo esperado —
  `todos_sin_muestras=false` (Mac Mini Server con 6 muestras reales,
  los otros dos sistemas con 0) — y el diagnóstico distinguió
  correctamente "el hub no está caído" de "esos dos sistemas
  concretos tienen un problema", sin inventar una causa ni confundir
  ausencia parcial con caída total.
- **Veces que se corrigió el spec en lugar del código**: 0.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí.
- **Validación real, con coste real**: los 6 escenarios de
  `quickstart.md` contra `beszel_hosts.json` real, el hub de Beszel
  real y DeepSeek real. Coste nuevo: ~0,004 €.
- **Dato para el método**: octavo origen cerrado (contenedores,
  discos, HA, backups, relays, inventario, hosts externos, hub de
  Beszel) de los 9 de la Central de Alarmas — queda 1: agentes.

## 2026-08-12 — Feature 014, ciclo completo (specify → implement), séptimo origen, primera línea base con causa raíz ya conocida

**Distinto de 011/012/013**: el usuario pidió explícitamente "hazlo
todo esta vez" — sin pasar por `AskUserQuestion` para decidir quién
ejecuta, y sin material de partida ya escrito en `BRIEFING.md` de una
sesión anterior (a diferencia de 013). Toda la investigación previa
(qué hosts, dónde vive la evidencia, qué línea base real existe) se
hizo en esta misma sesión, contra el sistema real, antes de escribir
el material de partida y arrancar `/speckit-specify`.

- **Qué se pidió**: séptimo origen de la Central de Alarmas — los 2
  hosts físicos externos que Beszel vigila (Uptime Kuma, AdGuard Home),
  distinto del hub de Beszel en sí (origen #8, pendiente) y de los
  relays `socat` (012, ya cerrado).
- **El material de partida original resultó equivocado en un punto
  central, corregido antes de escribir ningún código**: se asumió por
  analogía con relays que el log del propio mecanismo
  (`beszel-hosts-reader.log`) sería la evidencia histórica. Comprobado
  en vivo (1.139 líneas): no lo es — solo registra si el ciclo completo
  tuvo éxito o falló, nunca el estado por host. La evidencia real
  estaba en otro sitio, dos niveles más adentro: la propia base de
  datos del hub de Beszel (`system_stats`, con retención escalonada en
  5 resoluciones, desde el 2026-07-14).
- **Hallazgo inesperado que mejoró la validación del feature**:
  investigando esa tabla se encontró un hueco idéntico de 8 días
  (2026-07-30 a 2026-08-07) para los dos hosts — y coincide
  exactamente con una avería ya documentada e independientemente
  explicada en el `CLAUDE.md` general del homelab (routing de
  contenedores roto tras un reinicio). Es la primera vez en el
  proyecto que la línea base de validación tiene una causa raíz
  externa ya conocida, no solo el hecho de que el episodio existió
  (007, 012, 013) ni una limitación aceptada (009, 010, 011).
- **`/speckit-analyze` encontró 1 hallazgo (MEDIUM), corregido antes de
  implementar**: `_consultar_beszel_hub()` puede devolver `None`
  (consulta fallida) o `[]` (consulta con éxito, sin filas) — dos casos
  reales que `tasks.md`/`data-model.md` no distinguían y que, sin
  corregir, habrían hecho fallar `_resumen_system_stats(None)` con un
  `TypeError` real la primera vez que Docker no estuviera disponible.
- **Decisión de diseño explícita, documentada antes de implementar**:
  a diferencia de 012 (F1, corregido tras el hecho) y 013 (FR-010,
  validado en código desde el diseño), la restricción de contenido de
  este feature (FR-006a, nunca presentar la ausencia de muestras como
  "caído confirmado") se dejó **solo en el prompt**, con la razón
  escrita en `research.md` §8: es un juicio sobre la calidad del
  razonamiento, no un hecho verificable por coincidencia de texto como
  los otros dos casos — intentar detectarlo con una búsqueda de
  palabras habría producido falsos rechazos de conclusiones legítimas.
- **Tareas implementadas sin intervención: 22 de 23** — la única
  excepción real, encontrada en la propia validación en vivo (T020, no
  en el selftest): `congelar_host_externo_historico()` nunca añadía
  `nombre`/`beszel_name` al resumen de evidencia, pese a que
  `data-model.md` ya los documentaba desde el diseño. El primer
  diagnóstico real contra la avería conocida lo delató solo: concluyó
  honestamente que "ni siquiera se puede determinar qué componente...
  estaba en episodio" — cierto, la evidencia serializada no llevaba el
  nombre en ningún sitio. Corregido de inmediato (research.md §12),
  con el mismo tratamiento que el hallazgo F1 de 012 y el U1 de 013:
  documentado como hallazgo de validación, no parcheado en silencio.
  Aparte, un error de test propio (buscar una frase partida por un
  salto de línea del prompt) — mismo tipo de error ya visto en 012.
- **La garantía central del feature (SC-005), verificada contra los 2
  hosts reales dentro de la avería conocida**: los dos diagnósticos
  concluyeron `no_diagnosticable` bien razonado, citando explícitamente
  las alternativas que pide FR-006a (fallo del agente, fallo de red
  hub↔host, hub sin registrar) en vez de afirmar "caído" sin más — sin
  ningún síntoma de truncamiento esta vez, a diferencia de 012/013.
- **Veces que se corrigió el spec en lugar del código**: 0.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí.
- **Validación real, con coste real**: los 7 escenarios de
  `quickstart.md` contra `beszel_hosts.json` real, el hub de Beszel
  real (vía `docker run`) y DeepSeek real. Coste nuevo: ~0,010 €.
- **Dato para el método**: séptimo origen cerrado (contenedores,
  discos, HA, backups, relays, inventario, hosts externos) de los 9 de
  la Central de Alarmas — quedan 2: el hub de Beszel, agentes.

## 2026-08-12 — Feature 013, ciclo completo (specify → implement), sexto origen, primera vez que `diagnostico` importa un paquete hermano

**Igual que 011/012**: Miquel pidió explícitamente "Claude ejecuta
todo" vía `AskUserQuestion` antes de arrancar — rompe a propósito el
reparto por defecto de `METODO.md`. Ciclo completo ejecutado por
Claude: `specify` → `clarify` → `plan` → `tasks` → `analyze` →
`implement` → validación en vivo.

- **Qué se pidió**: sexto origen de la Central de Alarmas — el propio
  inventario de cobertura (`inventario.db`, feature 001). De los 6
  tipos de brecha que clasifica (`sin_declaracion`,
  `declaracion_caducada`, `sin_vigilancia`, `no_llega_a_dashboard`,
  `riesgo_concentrado_telegram`, `condicion_incumplida`), 5 entran en
  alcance; `condicion_incumplida` queda fuera por diseño — solo ocurre
  hoy en `entidad_ha` y es el propio inventario re-detectando, con
  otras palabras, lo que el origen `ha` (010) ya diagnostica.
- **Decisión de arquitectura real, no anticipada en el material de
  partida**: `diagnostico/evidencia.py` importa `inventory.store`/
  `inventory.diff` directamente (paquete hermano de este mismo repo)
  en vez de leer un fichero/DB externo — primera vez que este motor
  importa un paquete de aplicación en vez de una fuente de datos
  externa. La comparación contra "qué cambió" se resuelve gratis
  reutilizando `primera_ejecucion_id` (ya persistido por
  `populate_brechas()`) y `inventory.diff.compare_runs()`, sin
  construir ningún mecanismo nuevo.
- **Investigando la línea base real antes de planificar se encontraron
  dos hallazgos que el material de partida (`BRIEFING.md`) no
  anticipaba** — corregidos en el propio `plan`/`research`, no
  descubiertos tarde:
  1. Las cuatro brechas reales conocidas (ejecuciones #19/#28/#31/#52)
     no son su propia `primera_ejecucion_id` — las cuatro comparten
     `primera_ejecucion_id = 3`; `#19` etc. son la **última** aparición
     antes de resolverse, no la primera. El mecanismo de comparación
     (research.md §4) sigue siendo correcto, pero la nota de validación
     original ("apuntar a la propia primera_ejecucion_id") era
     literalmente al revés y se corrigió antes de escribir código.
  2. El ancla real de esas cuatro brechas (ejecución #2) tiene **0
     brechas registradas** (probablemente anterior a que
     `populate_brechas()` se conectara al flujo normal) — un diff sin
     límite listaría hasta 319 brechas como "nuevas". Corregido con
     `INVENTARIO_COMPARACION_MAX_ENTRADAS = 30` (`{"total", "muestra"}`
     por lista), mismo patrón defensivo que `HA_HISTORIAL_MAX_ENTRADAS`
     (010) y `BACKUP_ANOMALIA_MAX_LINEAS` (011), aplicado esta vez
     *antes* de la primera llamada real, no después de gastar dinero
     descubriéndolo.
- **`/speckit-analyze` encontró 1 hallazgo (U1, MEDIUM), corregido antes
  de implementar**: `data-model.md`/`tasks.md` describían
  `_brecha_de_componente()` como si "filtrara a los 5 tipos en alcance
  salvo para la comprobación de FR-010" — contradictorio consigo mismo.
  Si se hubiera implementado tal cual, la función habría filtrado
  `condicion_incumplida` antes de que `_validar_tipo_brecha_inventario()`
  (T004) tuviera nada que rechazar, vaciando FR-010 en silencio.
  Corregido en `data-model.md`, `tasks.md` y `research.md` antes de
  escribir ninguna línea de código. **Cero hallazgos de tipo C1**
  (hueco de SC-002 sin selftest) por primera vez en el proyecto — el
  test `test_parsear_respuesta_inventario_con_varias_hipotesis` se
  escribió directamente en `tasks.md`/T010 desde el diseño, en vez de
  esperar a que `/speckit-analyze` lo volviera a encontrar una quinta
  vez.
- **Tareas implementadas sin intervención: 23 de 23** — sin errores de
  test-writing esta vez (a diferencia de 012), aunque sí hizo falta un
  pase de limpieza propio durante la propia implementación (no
  detectado por ninguna skill): un `inv_store.connect()` redundante
  (abría la conexión de inventario dos veces por congelado) y un
  filtro muerto en `inventario_brecha` (ya inalcanzable tras la
  validación de FR-010) — corregidos antes de escribir los tests, no
  después.
- **La garantía central del feature (SC-005), verificada contra dos de
  las cuatro brechas reales conocidas**: "Agente Hermes/Bautista" (#19)
  y "Host de Uptime Kuma" (#28). El primer caso reprodujo exactamente
  el mismo patrón de truncamiento ya documentado en 012 §11 — 2 de 2
  llamadas reales a presupuesto por defecto (2000 tokens) fallaron
  (`finish_reason: "length"` una vez, `finish_reason: "stop"` con
  `content` vacío la otra — un tercer patrón de fallo, distinto tanto
  del truncamiento como de la recuperación vía `reasoning_content` de
  010) y una llamada manual con el límite subido a 6000 sí completó una
  `causa_probable` correcta, coincidiendo con la causa real conocida.
  El segundo caso, en cambio, tuvo éxito limpio a presupuesto por
  defecto con un `no_diagnosticable` bien razonado (4 hipótesis) —
  confirma que el truncamiento no es sistemático para todo episodio de
  inventario en diferido, depende del tamaño real de la evidencia.
  Documentado en `research.md` §12, sin tocar la constante compartida
  (mismo criterio ya fijado en 010/012 — decisión de coste de Miquel,
  no de este feature).
- **Veces que se corrigió el spec en lugar del código**: 0.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí.
- **Validación real, con coste real**: los 8 escenarios de
  `quickstart.md` contra `inventario.db` real y DeepSeek real —
  incluidas 2 llamadas de investigación adicionales fuera del CLI para
  diagnosticar el truncamiento (mismo método que 012). Coste nuevo:
  ~0,008 €.
- **Dato para el método**: sexto origen cerrado (contenedores, discos,
  HA, backups, relays, inventario) de los 9 de la Central de Alarmas —
  quedan 3: hosts externos, el hub de Beszel, agentes.

## 2026-08-12 — Feature 012, ciclo completo (specify → implement), primera línea base real desde el arranque

**Igual que 011**: Miquel invocó él mismo `specify`/`plan`/`tasks`/
`analyze` como comandos slash explícitos; el ciclo completo lo ejecutó
Claude, incluido el `implement` final, a petición directa ("aplica las
dos correcciones y directamente haz el implement").

- **Qué se pidió**: quinto origen de la Central de Alarmas — relays
  `socat` (9 relays HA + 2 de Beszel documentados en el `CLAUDE.md`
  general, 10 vigilados de verdad en `socat_relays.json`). Decisión
  explícita por `AskUserQuestion` antes de especificar: vivo con
  detalle real por relay, diferido solo con evidencia agregada
  (`ok/total`) — nunca cuál relay concreto, porque esa información no
  se archivó nunca en `dashboard-socat.log` y no existe forma de
  reconstruirla. Segunda decisión: enviar las IPs LAN reales a DeepSeek
  tal cual, con justificación explícita en `plan.md` (mismo criterio ya
  aplicado a otros orígenes, no una excepción nueva).
- **`/speckit-analyze` encontró 2 hallazgos, uno HIGH, corregidos antes
  de implementar**: F1 — FR-006 ("nunca nombres un relay concreto")
  solo estaba pedido en el prompt, sin validación en código, el mismo
  patrón de riesgo que ya causó el hallazgo I2 de 007 (dos hipótesis
  `confirmada` a la vez pese a que el prompt pedía una sola). Corregido
  con `listar_nombres_relay()` + `_menciona_relay_concreto()` +
  rechazo en `diagnosticar_episodio()` — nueva tarea T011. C1 — el
  hueco de SC-002 sin selftest de varias hipótesis para el origen
  nuevo, la cuarta vez seguida (009, 010, 011, 012) que `/speckit-analyze`
  encuentra el mismo hueco recurrente.
- **Tareas implementadas sin intervención: 22 de 22** — pero dos
  errores míos, no de las tareas, bloquearon el primer `--selftest`:
  un test nuevo sin `from unittest.mock import patch` en las
  importaciones, y una aserción que buscaba el texto literal "NUNCA
  nombres" cuando la cláusula real dice "NO nombres" — los dos en
  tests que yo mismo escribí en esta sesión, no en el código de
  producción. Corregidos antes de la validación en vivo.
- **La garantía central del feature (SC-005), verificada contra el
  episodio real del 2026-05-24 (~10h de caída, 1 de 5 relays caído sin
  interrupción)**: por primera vez en el proyecto, una línea base real
  estuvo disponible desde el arranque del feature — 009/010/011
  tuvieron que arrancar con la salvedad de "sin línea base real
  todavía". El resultado fue honesto (SC-005 no exige más que eso) pero
  revela una limitación real: de 4 llamadas reales a DeepSeek contra
  ese episodio con `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` en su valor por
  defecto (2000), 3 se truncaron (`finish_reason: "length"`) antes de
  completar un JSON válido — el razonamiento del modelo para esta
  evidencia agregada resultó sistemáticamente largo. La misma llamada
  con el límite subido a 6000 sí completó una `causa_probable` bien
  formada, con una única hipótesis `confirmada` y sin nombrar ningún
  relay. No se tocó la constante compartida (mismo criterio ya fijado
  en 010, research.md §10) — documentado como limitación conocida en
  `research.md` §11, no como corrección, porque subirla afecta al coste
  de los cinco orígenes por igual y es una decisión de Miquel.
- **Veces que se corrigió el spec en lugar del código**: 0.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí.
- **Validación real, con coste real**: los 7 escenarios de
  `quickstart.md` contra `socat_relays.json` y `dashboard-socat.log`
  reales y DeepSeek real — 8 llamadas en total (4 sobre el episodio del
  apagón, 1 sobre relay inexistente, 2 sobre relays sanos, 1 rechazada
  por el cortacircuitos de gasto sin llegar a llamar). Coste nuevo:
  ~0,013 €.
- **Dato para el método**: quinto origen cerrado (contenedores, discos,
  HA, backups, relays) de los 9 de la Central de Alarmas — quedan 4
  (hosts externos, hub de Beszel, agentes, inventario). Primera vez que
  el hallazgo de validación en vivo no es un bug de código sino una
  limitación de coste/calidad ya conocida y ya decidida en una sesión
  anterior — la disciplina de "no tocar sin decisión explícita" se
  sostuvo bajo presión real (un episodio con datos, sin poder mostrar
  una `causa_probable` limpia con la configuración por defecto).

## 2026-08-12 — Feature 011, ciclo completo (specify → implement), Miquel pide expresamente que ejecute cada paso

**Distinta otra vez**: en 010 Miquel ejecutó `clarify`/`plan`/`tasks`/
`analyze` él mismo y solo delegó `implement`. En 011 pidió
explícitamente "ejecuta tú" en cada paso del ciclo, incluidos
`specify`, `plan`, `tasks`, `analyze`, `implement`, y el commit/push
final — la ruptura de `METODO.md` fue completa esta vez, a petición
directa, no por defecto.

- **Qué se pidió**: cuarto origen de la Central de Alarmas —
  backups. Petición concreta de Miquel sobre el nombre
  (`011-diagnostico-backups`, para tenerlo como referente) y una
  pregunta real que cambió el material de partida: si los backups
  automáticos de Home Assistant necesitaban tratamiento aparte.
  Investigado antes de escribir nada: no — su frescura ya la
  diagnostica 010 (`ha_backup_reciente`), y que sobrevivan al rsync ya
  lo cubre el mecanismo genérico de este mismo feature (comprobado que
  su carpeta no está excluida del rsync principal).
- **Sin `/speckit-clarify` esta vez**: el checklist de calidad del spec
  pasó 16/16 sin ningún marcador `[NEEDS CLARIFICATION]` — la
  investigación previa a especificar (material de partida) ya había
  resuelto la única ambigüedad real (granularidad del episodio: ¿log
  completo de una noche, o cada uno de los ~12 checks de
  `verify_backups.py` por separado?) con un valor por defecto
  documentado en Assumptions, no como pregunta abierta.
- **`/speckit-analyze` encontró 3 hallazgos, 0 críticos, corregidos
  antes de implementar** (a diferencia de 010, donde las correcciones
  de `/speckit-analyze` se aplicaron sobre la marcha durante
  `implement`): SC-002 sin selftest explícito de varias hipótesis para
  origen backup (mismo hueco ya cerrado una vez en 009/010 — se había
  reproducido); una línea de dump fallido se contaba dos veces (en
  `dumps` y en `anomalias`); el caso "sin log en la ventana" de
  `congelar_backup_historico()` no se probaba explícitamente.
- **Tareas implementadas sin intervención: 20 de 20** — ninguna falló,
  pero la propia validación en vivo encontró un problema real no
  anticipado por ningún artefacto: sin ningún log en la ventana
  pedida, el episodio se etiquetaba con la hora *actual* en vez de la
  *pedida* — confuso en diferido (pedir 2020 mostraba la hora de hoy).
  Corregido y documentado en `research.md` §9 antes de cerrar el
  feature.
- **La garantía central del feature, verificada dos veces, sin
  sorpresas**: a diferencia de 010 (donde el reventón de prompt de
  `sal_nivel` fue un hallazgo real *durante* la implementación), aquí
  se comprobó primero en `research.md`/`plan.md` —antes de escribir
  código— contra el log real más grande retenido (951.031 caracteres,
  9.878 líneas), y se volvió a confirmar en Polish: la evidencia
  extraída se quedó en 1.684 caracteres las dos veces. Aplicar la
  lección de 010 por diseño, no después, evitó repetir el mismo
  susto.
- **Veces que se corrigió el spec en lugar del código**: 0. El código
  se corrigió (el hallazgo de `momento_solicitado`) y `research.md` se
  actualizó para seguir describiéndolo — mismo criterio que 010.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí,
  tras la actualización de `research.md` §9.
- **Validación real, con coste real**: 6 escenarios de `quickstart.md`
  contra logs reales y DeepSeek real. Coste nuevo: 0,00725 € —
  confirmado por consulta directa que el acumulado del día
  (0,24332864 €) es exactamente HA + backup, un único límite
  compartido.
- **Dato para el método**: cuarto origen cerrado (contenedores, discos,
  HA, backups) de los 9 de la Central de Alarmas — quedan 5 (relays,
  hosts externos, hub de Beszel, agentes, inventario). Segunda sesión
  seguida (tras 010) donde la investigación previa a especificar
  encuentra una diferencia estructural real entre orígenes —aquí, "sin
  tabla ni API, solo texto libre con 7 días de retención"— que cambia
  el propio diseño del plan, no solo el contenido de la evidencia.

## 2026-08-12 — Feature 010, ciclo completo (specify → implement), ruptura parcial de `METODO.md`

**Distinta de las rupturas de 008/009**: esta vez Miquel sí ejecutó él
mismo `/speckit-clarify`, `/speckit-plan`, `/speckit-tasks` y
`/speckit-analyze` (los cuatro llegaron como comandos escritos por él,
no decididos por Claude). La ruptura fue más estrecha y explícita: al
llegar a `/speckit-implement`, Claude paró y preguntó antes de escribir
ningún código (`METODO.md` dice "todo el código" es de Miquel) — Miquel
respondió "Implementa tú esta vez", y más tarde pidió también el commit
y el push. Registrar esto con precisión importa para el propio
experimento: no es "Claude hizo todo el ciclo" como 008/009, es "Miquel
llevó el diseño, Claude llevó la implementación a petición explícita,
con una pausa de confirmación en el punto exacto donde cambiaba el
reparto".

- **Qué se pidió**: generalizar el motor de diagnóstico (007, ya
  generalizado a discos en 009) a un tercer origen: Home Assistant —
  checks de entidad, el recorder corrupto, y la disponibilidad de la
  API. Tercero de los 7 orígenes restantes de la Central de Alarmas;
  quedan 6.
- **Ambigüedades detectadas por `clarify`**: 1 — el check `ha_api`
  (tipo `api_ping`, sin entidad asociada) no encajaba en ninguna de las
  dos categorías de evidencia que el material de partida daba por
  buenas. Encontrado comparando el spec contra `ha_monitor.py` real, no
  por inspección del propio spec — el Principio XIII (Cobertura
  Sistemática) fue literalmente el motivo de la pregunta.
- **`/speckit-analyze` encontró 5 hallazgos, 0 críticos**: dos huecos de
  cobertura MEDIUM (SC-004 sin validación real del recorder *sano*,
  SC-002 sin selftest explícito de varias hipótesis para origen `ha`),
  una inconsistencia de dependencias MEDIUM (T024 no listaba T007 como
  prerrequisito pese a invocar el flag que T007 conecta), y dos LOW
  (una nota de verificación de research.md sin tarea asignada, un
  resumen incompleto en `plan.md`). Los tres MEDIUM se cerraron durante
  `implement`, no antes: los dos huecos de cobertura escribiendo los
  tests/validaciones correctamente desde el principio, y la
  inconsistencia de T024 corrigiendo la nota de dependencia al marcar
  la tarea.
- **Tareas implementadas sin intervención: 24 de 24** — ninguna falló.
  Pero la mayor parte del tiempo de la sesión no lo absorbió `tasks.md`,
  sino la validación en vivo: **4 problemas reales del motor**, ninguno
  anticipado por ninguna tarea, encontrados solo porque la validación
  usó DeepSeek/HA/Docker reales en vez de pararse en los selftests
  simulados (que ya tenían mocks "bien formados" por construcción, así
  que ninguno de los 4 podía aparecer ahí):
  1. `parsear_respuesta()` descartaba respuestas completas y válidas
     que el modelo de razonamiento escribía en `reasoning_content` en
     vez de `content` — afecta al motor compartido por 007/009 también,
     no solo a HA.
  2. Una entidad de alta frecuencia (`sal_nivel`, sensor de voltaje)
     reventó un prompt a 280.454 tokens sin producir ningún
     diagnóstico — la premisa de diseño ("las entidades de HA solo
     cambian de estado de vez en cuando") era cierta para baterías
     Zigbee y falsa para sensores de medición continua.
  3. `docker_logs_tail("homeassistant")` devolvía siempre `""` — ese
     contenedor escribe en `stderr`, no en `stdout`, y el `_run_ro()`
     heredado de 007 solo capturaba `stdout`.
  4. Un check `ha_api` sano se diagnosticaba como `causa_probable`
     citando un error real pero no relacionado de otra integración —
     el prompt no le decía al modelo si *ese check concreto* estaba
     fallando, así que rellenaba el hueco con el ruido más cercano.
  Cada uno se confirmó antes de tocar código (reproducido, no asumido),
  y los tres primeros se corrigieron sin pedir confirmación de nuevo
  (bugs claros, de bajo riesgo, dentro del alcance de lo que FR-003 ya
  exigía); el cuarto se paró a preguntar porque cambiaba la forma del
  snapshot (`data-model.md`) y el propio diseño de qué cuenta como
  evidencia, no solo corregía un error de ejecución.
- **Veces que se corrigió el spec en lugar del código**: 0. Al revés:
  se corrigió el código y **el spec se actualizó para seguir
  describiéndolo** — los 4 hallazgos quedaron escritos en
  `research.md` §10-§13 y `data-model.md`, con fecha, causa raíz y
  validación real, no como una discrepancia silenciosa entre lo que
  dice el documento y lo que hace el código.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí,
  después de las 4 actualizaciones post-hoc de arriba — sin ellas,
  `research.md` habría quedado desfasado del código real en el mismo
  commit que lo cerraba.
- **Validación real, con coste real**: API de HA real, contenedor
  `homeassistant` real (corrupción de recorder simulada con
  `docker exec ... touch`/`rm`, limpiada de inmediato), DeepSeek real.
  Los 7 escenarios de `quickstart.md` validados con datos reales, no
  solo simulados. Coste real acumulado: 0,236 € — muy por debajo del
  límite compartido de 5 €/día, confirmado por consulta directa a
  `gasto_diario` (FR-007/SC-003).
- **Dato para el método**: cuarta sesión seguida (tras 007, 008, 009)
  donde la validación contra infraestructura real encuentra algo que
  ningún selftest simulado podía encontrar — esta vez el número más
  alto hasta ahora (4 hallazgos reales en una sola sesión de
  `implement`). Refuerza el mismo argumento que ya dejaron 007/008/009:
  "selftest en verde" y "feature funciona contra el sistema real" son
  preguntas distintas, y la brecha entre ambas parece crecer, no
  reducirse, a medida que el motor se generaliza a orígenes con formas
  de evidencia más variadas (HA es el primero sin una tabla SQL propia
  de la que leer).

## 2026-08-11 — Feature 009, ciclo completo (specify → implement), tercera vez fuera de proceso

**Ruptura deliberada de `METODO.md`, tercera vez en la misma sesión
larga.** Mismo patrón que 008: Miquel decidió el qué ("Pues hagamos
1" — generalizar el diagnóstico a un segundo origen), Claude ejecutó
todo el ciclo. Mismo aviso de siempre: estos números miden qué
encuentra el método sin Miquel al mando, no el método en sí.

- **Qué se pidió**: generalizar el motor de diagnóstico (007) más allá
  de contenedores. Antes de escribir nada, investigación real: de los 9
  orígenes restantes de la Central de Alarmas, solo discos tiene datos
  históricos de verdad en `homelab.db` (`disk_metrics`, 13.992 filas) —
  los otros 7 no tienen ninguna tabla propia. Decidido con Miquel:
  empezar por discos, uno a la vez, no los 9 de golpe (mismo criterio
  que ya usaron los features 004/005 para no tratar entidades distintas
  como un bloque).
- **Segundo hallazgo de la investigación previa**: a diferencia de
  `beszel` (49 reinicios reales para 007), no existe ningún incidente
  real de disco que usar como línea base — los tres discos del homelab
  llevan tiempo sanos. Aceptado como limitación conocida en el propio
  `plan.md` (Principio IX), no ocultada.
- **Ambigüedades detectadas por `clarify`**: 1 — qué pasa si el disco
  diagnosticado es el mismo donde vive `diagnostico.db` y no queda
  espacio para escribir el resultado (un riesgo que no existía para
  contenedores, cuya evidencia y registro viven en sitios
  independientes). Miquel aceptó el riesgo tal cual, sin mecanismo de
  respaldo nuevo.
- **`/speckit-analyze` encontró 3 hallazgos reales**: una inconsistencia
  de formato (`T002` marcada `[P]` pese a depender de `T001`), un hueco
  de cobertura (SC-002 — varias hipótesis para un episodio de disco —
  sin ninguna tarea que lo comprobara), y una infraespecificación real
  (la convención horaria de `MOMENTO_ISO` en `--disco-historico` no
  estaba escrita en ningún sitio — exactamente la categoría de fallo
  que ya costó una sesión de depuración entera en 008 sobre este mismo
  paquete). Los tres se corrigieron antes de implementar.
- **Tareas implementadas sin intervención real: 19 de 19** — ninguna
  falló, pero la implementación sí encontró trabajo no anticipado en
  ningún artefacto: renombrar `episodios.contenedor` a `componente`
  exigió tocar 5 sitios de `tests/selftest/*.py` que construían
  `Episodio(contenedor=...)` con el nombre antiguo — no estaban en
  `tasks.md` porque son consecuencia mecánica de T001/T002, no trabajo
  nuevo de diseño.
- **Migración de esquema sobre datos de producción, con cautela
  explícita**: `episodios.contenedor` → `componente` + `origen` nuevo,
  aplicada primero contra una **copia** de `diagnostico.db` real (9
  episodios, 17 diagnósticos, 26 hipótesis — verificados intactos byte
  a byte en los campos que no debían cambiar) antes de tocar el
  fichero de producción. Tareas T014/T015 separadas a propósito por
  esto mismo.
- **Validación real con DeepSeek, no solo selftest simulado**: los tres
  discos reales del homelab (FastData, Storage, Sistema), sanos,
  diagnosticados de verdad — los tres concluyeron `no_diagnosticable`
  con 3-4 hipótesis contrastadas cada uno (el modelo razonó sobre
  tendencia de crecimiento del uso, backups sin rotar, fallo de
  hardware — sin inventar ninguna causa). Reproducibilidad (SC-001)
  confirmada con dos diagnósticos reales del mismo episodio histórico.
  Gasto compartido (FR-007) confirmado por aritmética exacta contra
  `gasto_diario` real: coste de contenedor + coste de disco = acumulado
  del día, sin discrepancia.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí —
  ninguna decisión de `research.md` tuvo que revisarse tras la
  validación real, a diferencia de 008 (que sí encontró un bug de
  diseño real en implementación). La investigación previa a especificar
  (qué orígenes tienen datos reales, qué convención horaria usar) pagó
  aquí: menos sorpresas en `implement` que en las dos sesiones
  anteriores.
- **Dato para el método**: tercera sesión seguida donde `/speckit-analyze`
  encuentra algo real (008: 1 hallazgo sobre 007 + 1 sobre 008 propio;
  009: 3 hallazgos). La categoría que más se repite — convención
  horaria sin documentar — ya apareció en 008 como bug de
  implementación y en 009 como hallazgo de análisis antes de llegar a
  implementar; la disciplina de escribirlo explícitamente en
  `research.md`/`contracts/` esta vez evitó repetir el mismo bug.

## 2026-08-11 — Feature 008, ciclo completo (specify → implement), otra vez fuera de proceso

**Ruptura deliberada de `METODO.md`, segunda vez en la misma sesión
larga.** A petición explícita de Miquel ("Sigo tú", "Ejecuta tú el
specify", "Implement ya"), Claude ejecutó el ciclo completo —
`specify` → `clarify` → `plan` → `tasks` → `analyze` → `implement` —
de principio a fin. Mismo aviso que la sesión anterior: los números de
abajo no miden el método con Miquel al mando, miden qué encuentra el
método cuando se sigue igual de disciplinado sin él.

- **Qué se pidió**: exponer en el dashboard los diagnósticos que ya
  produce el motor de 007, solo lectura, colgado de una pestaña ya
  existente — visto en la sesión anterior como feature 008 (el hueco
  que dejó cerrarse la deuda técnica sin necesitar spec).
- **El spec cambió de sitio dos veces antes de llegar a `/speckit-plan`
  y otra vez durante `/speckit-plan`**. Primera: el material de partida
  decía "pestaña Correcciones"; al escribirlo, Miquel decidió que fuera
  solo visor y colgado de Correcciones. Segunda (real, encontrada al
  preparar `/speckit-plan`, no al escribir el spec): "Correcciones" no
  es la lista de alarmas activas — es el historial de alarmas ya
  **resueltas**; la lista activa es la pestaña "Alarmas", separada.
  Tercera: puesto a elegir entre las dos con la distinción ya clara,
  Miquel cambió el destino a "Alarmas" — más accionable, coincide con
  el caso de uso que 007 ya había validado de verdad (diagnóstico en
  vivo de un contenedor crítico). El spec, `research.md`, `data-model.md`,
  `contracts/` y `quickstart.md` se reescribieron enteros la segunda
  vez — la única reescritura completa de un artefacto en todo el
  proyecto hasta ahora.
- **Ambigüedades detectadas por `clarify`**: 1 — cuándo un diagnóstico
  de una caída anterior no debe mostrarse como si fuera de la actual.
  Miquel confirmó el valor por defecto y añadió un requisito no
  anticipado: las fechas del episodio y del diagnóstico deben estar
  siempre visibles, nunca solo la conclusión sola.
- **`/speckit-analyze` encontró 1 hallazgo real** (I1, HIGH): el
  contrato decía que la clave `diagnostico` no aparecía en absoluto
  para alarmas ajenas/agrupadas; `data-model.md` y `tasks.md` ya
  asumían que sí aparecía, como `null`. Resuelto unificando en la
  segunda convención (más simple de implementar).
- **Tareas implementadas sin intervención real: 13 de 16.** Las otras
  3 no fallaron por error de tarea — revelaron problemas de diseño que
  ninguna revisión de código podía encontrar:
  1. El desempate entre dos episodios a la misma distancia no seguía
     "el más reciente" que el propio `research.md` había decidido —
     encontrado releyendo el código ya escrito, antes de desplegar.
  2. Un `SyntaxWarning` real por un escape sin duplicar en el JS
     embebido, más una lógica de formateo de euros confusa —
     encontrado en los logs del contenedor al reconstruirlo.
  3. **El más importante**: el algoritmo de emparejamiento comparaba
     `down_since` contra un único punto (`ventana_inicio`). Probado
     contra un episodio real (`congelar --vivo` de un contenedor
     parado a propósito para la prueba), falló exactamente el caso de
     uso central del feature — diagnosticar en vivo poco después de la
     caída — porque `ventana_inicio` de un episodio `--vivo` es el
     principio de toda una hora de contexto de métricas, no el inicio
     real de la caída. Ninguna de las 16 tareas de `tasks.md`, ni la
     revisión de `/speckit-analyze`, podía haber encontrado esto sin
     ejecutar el código contra un caso real — se corrigió comparando
     contra el **rango** `[ventana_inicio, ventana_fin]` en vez de un
     punto.
- **Validación real, no solo selftest simulado**: contenedor
  reconstruido y desplegado en producción; funciones probadas dentro
  del contenedor real contra `diagnostico.db` real; **captura de
  pantalla con un navegador real** (Playwright/Chromium, instalado
  para la ocasión) confirmando visualmente el bloque de diagnóstico,
  las dos fechas y el gasto diario. El entorno de pruebas (un
  contenedor parado a propósito, `docker_monitor_state.json` alterado
  temporalmente para simular una alarma) se restauró exactamente al
  estado previo — diff vacío confirmado contra la copia de seguridad.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí,
  incluida la corrección del algoritmo de emparejamiento, documentada
  en `research.md` §3 con la fecha y el caso real que la motivó, no
  como una discrepancia silenciosa entre el spec y el código.
- **Dato para el método**: de los tres problemas reales encontrados en
  esta sesión (el pivote Correcciones→Alarmas, el hallazgo I1, y el
  bug del rango de fechas), **ninguno lo encontró la revisión de
  código ni `/speckit-analyze` — los tres aparecieron al ejecutar
  contra datos y contenedores reales**. Coincide con lo que ya apuntó
  la sesión de 007 (T030): en este proyecto, la validación real sigue
  encontrando categorías de fallo que ninguna revisión estática cubre.

## 2026-08-07/08 — Feature 001, ciclo completo (specify → implement)

Primer feature del proyecto. Una sola sesión cubrió el ciclo entero:
`constitution` (ya existía) → `specify` → `clarify` → `plan` → `tasks` →
`analyze` → `implement`.

- **Especificar vs implementar**: la mayor parte del tiempo se fue en
  `specify` — varias rondas de revisión con Miquel ampliando alcance
  (granularidad de entidad en HA, hosts externos, Hermes/Telegram como
  riesgo concentrado, disparo a demanda) antes de cerrar el spec.
  `implement` fue más rápido de lo esperado porque el propio `plan.md`
  ya había investigado contra el código real del homelab (convenciones,
  rutas, estructura de datos), así que hubo poco que decidir sobre la
  marcha.
- **Ambigüedades detectadas por `clarify`**: 3, ninguna descartada por
  cupo — identidad de un componente entre ejecuciones, retención del
  histórico, umbral de caducidad de una declaración (90 días).
- **Tareas implementadas sin intervención**: 39 de 40. La única que se
  paró a propósito fue T036 (parche del dashboard en producción, fuera
  del repo) — parada explícita para pedir confirmación antes de tocar un
  fichero en producción, no un fallo de implementación.
- **Veces que se corrigió el spec en lugar del código**: 2.
  1. Durante `/speckit-plan`: el ejemplo "container ID de Docker" en la
     Clarification 1 era técnicamente impreciso (el ID interno cambia en
     cada recreación; lo estable es el nombre) — corregido en `spec.md`
     antes de que hubiera código apoyado en el dato erróneo.
  2. Durante `/speckit-implement`: el paso 6 de `quickstart.md` probaba
     el mecanismo de respaldo del riesgo de Telegram con `--no-telegram`,
     que es un *skip* deliberado, no un fallo — se corrigió para forzar
     credenciales vacías de verdad, y se verificó contra el código real
     que el latido sale `fail` en ese caso.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay?**: sí, con una salvedad
  anotada aparte — Beszel/hosts externos/Recordatorios de Nextcloud
  quedaron marcados en `spec.md` (Assumptions) como candidatos a
  **feature 002** (mostrar en el dashboard las alarmas que ya calculan
  `docker_monitor.py`/`ha_monitor.py`, hoy invisibles) en vez de meterlos
  en este feature — decisión explícita con Miquel, no un hueco sin
  documentar.
- **Dato no previsto en ningún artefacto**: la primera ejecución real
  encontró 830 componentes y 385 brechas (línea base del Principio IX
  exigía ≥11). El propio volumen reveló un límite no cubierto por
  ninguna tarea: un mensaje de Telegram con 385 líneas probablemente
  supera el límite de 4096 caracteres de la API — anotado como pendiente,
  no arreglado en esta sesión.

## 2026-08-09 — Features 002-005, sin bitácora propia (hueco de proceso)

Entre el feature 001 y el 006 se cerraron cuatro features más
(`002-alarmas-al-dashboard`, `003-latidos-beszel-calendario`,
`004-triage-entidad-ha`, `005-movil-y-backup-ha`) sin anotar una línea
aquí en su momento — se hizo el ciclo completo de Spec Kit en cada uno
(hay `spec.md`/`plan.md`/`tasks.md` reales para los cuatro) pero las
métricas de proceso (ambigüedades, tareas sin intervención, spec vs
código) no se registraron. Se deja constancia del hueco en vez de
reconstruir con memoria las cifras de sesiones ya cerradas — inventar
un número aproximado sería peor que admitir que no se midió.

## 2026-08-09 — Feature 006, ciclo completo (specify → implement) + resolución de hallazgos post-implement

Central de Alarmas: pestaña nueva que unifica 10 orígenes ya
vigilados en una sola lista con explicación y remediación fijas por
tipo, sin IA. Ciclo completo en una sesión:
`specify` → `clarify` → `plan` → `tasks` → `analyze` → `implement` →
una segunda vuelta de `analyze` resuelta explícitamente a petición de
Miquel.

- **Especificar vs implementar**: al revés que el feature 001 — aquí
  `implement` llevó más rondas que `specify`. El propio `plan.md`
  investigó bien contra el código real (`app.py`), pero la superficie
  de T002 (10 orígenes con formas de datos todas distintas) hizo que
  apareciera un problema real de diseño ya en la fase de implementación:
  el catálogo de tipos de HA asumía que `app.py` podía leer el campo
  `type` de cada check (`api_ping`/`entity_available`/...), y ese campo
  nunca se serializa a `ha_monitor_state.json` — solo vive en el
  `ha_monitor.py` privado. Se resolvió con una heurística sobre
  `motivo`+`label`+id del check, sin volver a `/speckit-plan`: una
  decisión de implementación legítima, no un cambio de alcance.
- **Ambigüedades detectadas**: 5 en total — 2 durante `/speckit-specify`
  (granularidad de la remediación por submotivo; aviso especial para
  contenedores críticos) + 3 durante `/speckit-clarify`, ninguna de
  estas últimas marcada como `[NEEDS CLARIFICATION]` en el spec
  original pese a ser reales (agrupación de alarmas en cascada,
  criterio de orden por gravedad, antigüedad opcional cuando el origen
  no la calcula). Los 5 se resolvieron con la opción recomendada.
- **Tareas implementadas sin intervención**: 18 de 18 en la primera
  pasada de `/speckit-implement`, más 3 tareas nuevas (T019-T021)
  añadidas y completadas en una segunda pasada al resolver los
  hallazgos de `/speckit-analyze` — 21 de 21 en total, cero fallos.
  Sí hubo una corrección propia durante la validación (no un fallo de
  tarea): un `SyntaxWarning` en el escape de una regex JS dentro del
  string Python de la plantilla, detectado al ejecutar la
  autocomprobación de T012, corregido antes de continuar.
- **Veces que se corrigió el spec en lugar del código**: al menos 11,
  todas en `/speckit-analyze` — 3 de severidad HIGH que Miquel pidió
  arreglar de inmediato (conteo "9 orígenes" cuando el propio
  `data-model.md` ya enumeraba 10; conteo "17 tipos" con una tabla de
  19 filas; `host_externo_sin_evidencia` clasificado de forma
  contradictoria en `spec.md` frente a `data-model.md`) y 8 más de
  severidad MEDIUM/LOW que Miquel pidió arreglar después, ya con el
  feature implementado y funcionando (terminología "motivo raíz" sin
  equiparar a `tipo`; regla de antigüedad de un grupo sin documentar;
  criterio de `cron_con_error` sin anclar a ningún enumerado; un
  ejemplo técnicamente inexacto repetido 4 veces; y 3 huecos de
  cobertura entre requisito e implementación sin tarea de verificación
  — ver más abajo). Dato interesante para el método: los 8 MEDIUM/LOW
  se resolvieron **sin tocar una sola línea de código de `app.py`** —
  solo documentación más 3 tareas nuevas de verificación manual — lo
  que sugiere que esa categoría de hallazgo es barata de posponer más
  allá de `/speckit-implement` sin acumular deuda real.
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí,
  y verificado contra el dashboard real en cada paso (no solo por
  inspección de código) — 5 de las correcciones de `/speckit-analyze`
  se re-comprobaron en vivo (provocando alarmas reales o simuladas)
  después de corregir la documentación, no solo se dieron por buenas.
- **Hallazgo fuera de todo artefacto de Spec Kit**: antes de comitear,
  una revisión manual encontró que 6 referencias a la IP LAN real
  (`192.168.4.87`) se habían colado en `quickstart.md`/`tasks.md`/
  `data-model.md` — exactamente lo que la regla "Repositorio público"
  de `BRIEFING.md` prohíbe, y que el propio `spec.md` de este feature
  ya citaba como restricción (Assumptions). Ninguna skill de Spec Kit
  tiene un paso que compruebe esto — quedó a criterio de la revisión
  antes de `git push`. Se corrigieron las 6 (sustituidas por
  `homelab.amsterdam9.home`, ya usado así en specs 001/002) antes del
  commit. Nota aparte: `specs/005-movil-y-backup-ha/quickstart.md` ya
  tenía esta misma fuga desde antes, sin corregir — deuda preexistente,
  no de esta sesión, anotada aquí para no perderla de vista.

## 2026-08-11 — Sesión fuera de proceso: Claude ejecuta, no solo revisa; feature 008 se cierra antes de nacer

**Ruptura deliberada de `METODO.md`.** A petición explícita de Miquel
("lo ejecutas tú esta vez", luego "hazlo tú mismo"), esta sesión la
ejecutó Claude de principio a fin — algo que `METODO.md` reserva a
Miquel precisamente para que aprenda el método y para que las métricas
de proceso sean reales. Se anota aquí en vez de en silencio: los
números de esta sesión (abajo) no son comparables a los de una sesión
normal del proyecto, y no deberían usarse para medir el método en sí.

- **Qué se pidió**: preparar el feature 008 (deuda técnica pendiente:
  4 piezas ya detectadas — ver la sesión de feature 006/007 más abajo y
  `BRIEFING.md`). Antes de escribir `/speckit-specify`, Miquel decidió
  recuperar la cuarta pieza (5 hallazgos de `/speckit-analyze` de 007
  cuyo contenido nunca se guardó) volviendo a correr `/speckit-analyze`
  sobre `007-diagnostico-episodios`, en vez de reconstruirlos de
  memoria.
- **Lo que pasó en vez de un ciclo de Spec Kit para 008**: la segunda
  pasada de `/speckit-analyze` sobre 007 encontró 6 hallazgos nuevos
  (U1-U3, I1-I2, C1 — distintos en número y contenido de los 5
  originales, dados por irrecuperables). Al pedir Miquel "prepáralos
  tú", se resolvieron los 6 directamente: un fix de código real
  (`deepseek.py` — el parser aceptaba en silencio más de una hipótesis
  `confirmada` a la vez, pese a que el propio prompt exige exactamente
  una), un test nuevo, y reescritura de `spec.md`/`research.md`/
  `data-model.md`/`quickstart.md` de 007 para que el criterio de
  reproducibilidad (SC-001/FR-002) documentado coincida con lo que de
  verdad se puede sostener contra un LLM en la nube, y para fijar por
  fin los `restart_history_id` concretos de la línea base de `beszel`
  (nunca se habían registrado en ningún artefacto). Esas correcciones
  cerraron, de paso, las otras tres piezas de deuda que iban a formar
  el alcance de 008. Al llegar al punto de escribir la descripción de
  partida para `/speckit-specify`, no quedaba nada que especificar.
- **Hallazgo fuera de todo artefacto de Spec Kit**: al sanear la fuga
  de IP conocida (`specs/005-movil-y-backup-ha/quickstart.md`), un
  barrido del mismo patrón por todo el repo encontró una segunda fuga
  no catalogada — los relays de Frigate en la sección "Feature 004" de
  `BRIEFING.md` citaban la IP real en vez de `homelab.amsterdam9.home`.
  Mismo patrón que el hallazgo de la sesión de feature 006
  (2026-08-09): ninguna skill de Spec Kit comprueba esto, sigue a
  criterio de la revisión manual.
- **¿El spec de 007 sigue describiendo lo que hay al cerrar esta
  sesión?**: sí — es precisamente lo que esta sesión restauró. Antes de
  ella, `spec.md`/`research.md` de 007 describían un criterio de
  reproducibilidad más estricto del que el código y la validación real
  (T030) podían sostener; ahora coinciden.
- **Dato para el método, no para el proyecto**: esta sesión demuestra
  que "recuperar hallazgos perdidos re-ejecutando `/speckit-analyze`"
  funciona — no reprodujo los mismos 5 hallazgos literales (imposible,
  nunca se guardaron), pero encontró una cobertura equivalente o mejor
  del mismo terreno real. Vale como precedente para la próxima vez que
  se encuentre un hueco de proceso similar.

## 2026-08-10 — Feature 007, ciclo completo (specify → implement) + validación real con DeepSeek

Primer feature de Frente 2: diagnóstico de episodios de contenedor con
DeepSeek, sin ninguna acción correctiva. Ciclo completo en una sesión:
`specify` (una repetición por un error de herramienta) → `clarify` (3
preguntas) → `plan` → `tasks` (33 tareas) → `analyze` → resolución de 3
hallazgos a petición explícita de Miquel → `implement` → validación real
contra la API de DeepSeek (no solo selftests simulados) una vez Miquel
creó la credencial.

- **Especificar vs implementar**: al contrario que el feature 001 y en
  la línea del 006 — `implement` encontró dos problemas de diseño reales
  que ni `plan.md` ni `data-model.md` habían anticipado, y que
  `/speckit-analyze` tampoco pudo detectar porque no ejecuta código
  contra datos reales. (1) `container_metrics`/`disk_metrics` tienen 30
  días de retención (documentado en el `CLAUDE.md` general del homelab,
  pero no traído al diseño de este feature); los 49 reinicios de
  `beszel` (marzo-mayo 2026) ya no tenían ningún dato de detalle al
  llegar a `implement` — se corrigió con un respaldo a
  `container_metrics_hourly` (agregado permanente). (2)
  `disk_metrics_near` devolvía "las 3 muestras más próximas" sin límite
  de distancia — para un episodio de abril, eso eran datos de disco de
  agosto, que el LLM podría haber leído como evidencia real del momento
  del episodio; se corrigió con un filtro de tolerancia. Los dos se
  encontraron al ejecutar T030 (validación contra la línea base de
  `beszel`) contra `homelab.db` real, no por inspección de código.
- **Ambigüedades detectadas por `clarify`**: 3 (alcance solo
  contenedores; disparo bajo demanda; identidad del episodio = snapshot
  congelado al elegir diagnosticar). Una cuarta clarificación se añadió
  a mano, fuera del propio comando `/speckit-clarify`: Miquel pidió
  inicialmente remediación automática al 100% sin distinguir críticos,
  se le explicó el conflicto con el Principio V (NO NEGOCIABLE) y con
  `docker_monitor.py`/`SOUL.md` ya vigentes, y se acordó en su lugar
  reforzar FR-013/FR-013a (diagnóstico obligatorio de críticos, cero
  acción sobre ellos) — el momento de mayor riesgo de la sesión, resuelto
  parando a pedir confirmación en vez de implementar la petición inicial.
- **Tareas implementadas sin intervención**: 31 de 33 en la primera
  pasada de `/speckit-implement` — T030 y T032 quedaron bloqueadas
  porque `.secrets/deepseek.env` no existía todavía (verificado, no
  asumido). Miquel creó la credencial en la misma sesión y las 2
  restantes se completaron después → 33 de 33 al cierre. Ninguna tarea
  falló de verdad; sí hubo una corrección de prompt en `deepseek.py`
  durante la validación real (ver hallazgo más abajo), fuera de lo que
  ninguna tarea de `tasks.md` pedía.
- **Veces que se corrigió el spec/plan en lugar del código**: 3, todas
  en `/speckit-analyze`, a petición explícita de Miquel ("resolver B1 E1
  E2"): un margen de gasto "prudente" sin cifra concreta en `research.md`
  (sustituido por la constante `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS`, que
  además pasó a ser el `max_tokens` real de la petición); SC-001
  (reproducibilidad) y SC-002/FR-011 (línea base de `beszel`) solo tenían
  verificación manual — se añadieron 2 tareas nuevas (T023, T031) con
  selftests automatizados antes de implementar nada. Quedaron sin tocar,
  por decisión explícita de Miquel, 5 hallazgos más de severidad
  MEDIUM/LOW (C1-C3, F1).
- **Veces que se reescribió el spec entero**: 0.
- **¿El spec sigue describiendo lo que hay al cerrar el hito?**: sí, con
  un cambio hecho en caliente tras la validación real: el modelo por
  defecto pasó de `deepseek-chat` (el asumido al escribir `research.md`)
  a `deepseek-v4-flash`, a petición de Miquel una vez confirmado que el
  feature funcionaba — documentado con fecha en `research.md` y
  `contracts/cli.md`, no dejado como una discrepancia silenciosa.
- **Hallazgo fuera de todo artefacto de Spec Kit**: la validación real
  contra DeepSeek (imposible de reproducir con los selftests, que usan
  respuestas ya bien formadas) encontró que el modelo, específicamente
  al diagnosticar un contenedor crítico sano sin ningún episodio real
  que explicar, marcaba una hipótesis `"confirmada"` en la misma
  respuesta que concluía `no_diagnosticable` — viola el invariante
  FR-007 tal como el propio prompt lo pedía. El parser lo rechazó
  correctamente 3 veces seguidas (ninguna causa falsa se persistió), a
  costa de 3 llamadas reales desperdiciadas (~0,0015 € en total). Causa
  raíz: el prompt no distinguía "esta comprobación se completó" de "esta
  hipótesis ES la causa" para la palabra "confirmada" — corregido con una
  aclaración explícita; la siguiente llamada fue consistente. No se ha
  vuelto a probar en volumen si la ambigüedad reaparece en otros
  contenedores — queda anotado en `tasks.md` (T030) como algo a vigilar
  en uso real, no como cerrado del todo. Aparte, también en la
  validación real (no en ningún selftest): el mismo episodio
  diagnosticado dos veces dio la misma conclusión pero un número
  distinto de hipótesis (0 y 3) — exactamente el Edge Case de varianza
  entre llamadas que el spec ya preveía como posible; queda como hallazgo
  registrado, no resuelto en esta sesión.
