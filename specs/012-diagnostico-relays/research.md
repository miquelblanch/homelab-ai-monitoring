# Research — Generalizar el Diagnóstico a los Relays

**Feature**: [spec.md](./spec.md)

## §1 — Sin migración de esquema: `origen` ya es TEXT libre

**Decisión**: `episodios.origen` gana un quinto valor real,
`'relay'`, sin ningún `ALTER TABLE` — misma situación que 010 §1/011 §1.

## §2 — Identificador de un episodio de relay: asimétrico por diseño

**Decisión**: en vivo, `componente` es el nombre del relay tal cual
aparece en `dump_socat_status.py::SOCAT_RELAYS` (`"Beszel AdGuard"`,
`"HA Shelly"`, ...) — mismo criterio que `check_id` de HA (010 §2). En
diferido, `componente` es el momento pedido en ISO 8601 — **sin ningún
nombre de relay**, porque no hay ninguno que identificar (spec.md
Assumptions, decisión tomada con Miquel el 2026-08-12 durante la
investigación previa a especificar).

**Rationale**: esta asimetría no es una limitación de implementación,
es un reflejo honesto de qué evidencia existe de verdad —
`socat_relays.json` tiene detalle por relay solo para el instante
actual (se sobreescribe cada 5 min); `dashboard-socat.log` solo
conservó el recuento agregado. Forzar un argumento de nombre en
`--relay-historico` sería pedir un dato que el propio comando no puede
usar para nada.

## §3 — Evidencia en vivo: `socat_relays.json`, sin puente a ningún script

**Decisión**: `_relay_actual(nombre)` lee
`SOCAT_RELAYS_JSON` (`/Volumes/FastData/homelab/docker/homelab-orchestrator/data/socat_relays.json`,
configurable vía la variable de entorno del mismo nombre) y busca la
entrada cuyo `name` coincide exactamente con `nombre` — `None` si no
existe (10 relays reales hoy: Traefik LAN/loopback/OrbStack, HA
Shelly/Broadlink, Beszel AdGuard/Kuma, Kuma UI, Frigate cocina/salón).
Un nombre que no está en el fichero no es un error — mismo criterio ya
establecido para `check_id`/`label` inexistentes en 009/010: el
episodio se congela igual, con evidencia vacía, y el diagnóstico
concluye `no_diagnosticable` honestamente.

**Rationale**: `socat_relays.json` ya es exactamente la fuente de
"estado esperado declarado" (Principio III) para este origen — leerlo
directamente con `json.loads()` es más simple y más fiel que intentar
puentear `dump_socat_status.py` (que ni siquiera expone una función
reutilizable, es un script de una sola pasada sin `heartbeat.write()`
ni estado en memoria que leer).

## §4 — Principio X: IPs privadas de la LAN, justificadas explícitamente (decisión con Miquel, 2026-08-12)

**Hallazgo real durante la investigación previa a planificar**: el
campo `desc` de cada relay contiene direcciones IP reales de la LAN
(`"192.168.4.87:45877 → 192.168.4.174:45876"`). Ningún origen anterior
(contenedor, disco, HA, backup) había enviado direcciones de red a
DeepSeek — esto es una categoría de dato nueva para el motor, y se
paró a preguntar antes de diseñar el snapshot, no se asumió.

**Decisión**: `desc` se envía tal cual, sin redactar. Justificación:

1. Son direcciones **privadas RFC1918** (`192.168.4.0/24`) — sin
   sentido fuera de la LAN de Miquel, no enrutables desde internet, no
   identifican a una persona.
2. Son precisamente el dato que permite diagnosticar el tipo de fallo
   más probable de un relay: ¿sigue apuntando al host correcto? ¿el
   puerto de destino coincide con lo que el propio dispositivo espera
   hoy? Redactarlas (research.md, alternativa rechazada) dejaría al
   modelo sin la única pista concreta disponible, exactamente el mismo
   argumento que ya justificó enviar métricas/logs de contenedor en
   007.
3. Mismo criterio de justificación caso por caso que exige el
   Principio X — documentado aquí explícitamente, con la decisión
   tomada antes de escribir ningún código, no como nota a posteriori.

**Alternativas consideradas y rechazadas** (decisión de Miquel,
2026-08-12): redactar las IPs con marcadores genéricos — pierde la
señal diagnóstica real sin ninguna ganancia de privacidad
proporcional (son IPs privadas, no secretas). Quitar el campo `desc`
por completo — deja al modelo sin contexto de qué conecta con qué,
que es justo lo útil.

## §5 — Evidencia en diferido: ventana sobre `dashboard-socat.log`, fuera del árbol habitual

**Hallazgo real**: a diferencia de todas las fuentes anteriores
(siempre bajo `/Volumes/FastData/homelab/`), el log del checker de
relays vive en `~/Library/Logs/dashboard-socat.log` — el
`StandardOutPath` del LaunchAgent `amsterdam9.dashboard.socat`. **Sin
ninguna rotación**: comprobado en vivo, conserva histórico real desde
el 2026-04-29 (29.834 líneas, ~1,8 MB) — mucho más profundidad que los
7 días de `backup_diario_nvme.sh` (011) o los 30 días de
`container_metrics`/`disk_metrics`.

**Decisión**: `DASHBOARD_SOCAT_LOG` (configurable vía variable de
entorno, por defecto `~/Library/Logs/dashboard-socat.log`, expandida
con `Path.expanduser()`). `_agregado_relays_ventana(momento,
ventana_minutos)` parsea cada línea con el patrón
`\[(?P<ts>[^\]]+)\].*?(?P<ok>\d+)/(?P<total>\d+) ok` y se queda con las
que caen dentro de `[momento - ventana, momento + ventana]`.

**Ventana: `VENTANA_RELAY_MINUTOS = 180`, no los 30 min ya usados para
métricas.** Investigado en vivo antes de fijar el valor: de los 17
episodios reales identificados agrupando fallos consecutivos, 16 duran
52 minutos o menos; uno solo llega a ~595 minutos (10 horas, el
2026-05-24). Una ventana de ±180 min cubre esos 16 completos de
extremo a extremo, y muestra una porción amplia y clara del episodio
largo aunque no lo cubra entero — suficiente para que el modelo vea la
tendencia (caída sostenida, no un parpadeo) sin necesidad de acertar
el momento exacto de inicio/fin.

**Límite defensivo, no por necesidad medida**: `RELAY_AGREGADO_MAX_LINEAS
= 100` — a intervalos de 5 min, ±180 min ya acota a ~72 líneas como
máximo por diseño de la propia ventana (a diferencia de 010/011, donde
el límite sí hacía falta por un caso real que reventaba sin él); este
límite es solo una red de seguridad si el formato del log cambiara o
apareciera una cadencia de escritura distinta a los 5 min esperados.

**Alternativas consideradas**: calcular y enviar los límites exactos
del episodio (inicio/fin del periodo de fallo) en vez de una ventana
fija. Rechazada por ahora — exigiría lógica de agrupación de fallos
consecutivos en `evidencia.py` (la misma que se usó para la
investigación de `research.md`/`BRIEFING.md`, pero como código de
producción, no como script de análisis puntual); una ventana fija
alrededor del momento pedido ya es evidencia real suficiente y es el
mismo patrón que el resto del motor usa en todos los orígenes.

## §6 — `_homelab_bridge.py` no cambia

**Decisión**: igual que 011 §6 — no hay ningún módulo Python externo
que puentear, `_relay_actual`/`_agregado_relays_ventana` leen ficheros
directamente con `json`/`re` de la librería estándar.

## §7 — Prompt de DeepSeek: generalizado una quinta vez

**Decisión**: `_PROMPT_INSTRUCCIONES` añade "...o un relay `socat`
caído (feature 012: specs/012-diagnostico-relays/) — en vivo, con
detalle de qué relay; en diferido, solo el recuento agregado de
cuántos relays vigilados fallaban, nunca cuál en concreto" a la lista
ya existente. **Cláusula nueva, específica de este origen**: cuando
`snapshot.relay_agregado` no es `null` (episodio en diferido), el
prompt le prohíbe explícitamente al modelo nombrar un relay concreto
como causa — coherente con FR-006, y necesaria porque, a diferencia de
los demás orígenes, aquí la tentación real es que el modelo "adivine"
cuál relay era el caído a partir del contexto (por ejemplo, si la
`conclusion_texto` de un episodio anterior lo mencionaba).

**`es_critico` para relay — siempre `False`**: igual que discos, HA y
backups.

## §8 — CLI: dos flags nuevos, asimetría reflejada en el propio contrato

**Decisión**:

```
python3 -m diagnostico.cli congelar --relay-vivo NOMBRE
python3 -m diagnostico.cli congelar --relay-historico MOMENTO_ISO
```

`NOMBRE` puede contener espacios (`"Beszel AdGuard"`, `"HA Shelly"`) —
el usuario lo entrecomilla igual que ya hace con cualquier argumento de
shell con espacios; `argparse` no necesita ningún tratamiento especial
más allá de recibirlo como string. `--relay-historico` **no** lleva
prefijo `NOMBRE@`, a diferencia de `--disco-historico`/`--ha-historico`
— mismo criterio que `--backup-historico` (011 §2): no hay ningún
nombre que el argumento pueda aportar en diferido.

**`MOMENTO_ISO`**: misma convención de hora local sin marca de zona ya
usada en 009/010/011.

## §9 — Sin datos en la ventana: se congela el momento pedido, no el momento de congelar (lección de 011, aplicada por diseño)

**Decisión**: `congelar_relay_historico()` recibe y usa siempre el
`momento` pedido como `componente`/centro de ventana, nunca
`datetime.now()` — incluso cuando `relay_agregado` queda `[]` por no
haber ninguna línea en el rango. Mismo problema real que 011 encontró
en su propia validación en vivo (research.md §9 de 011: pedir un
momento de 2020 mostraba en `mostrar` la hora actual, no 2020,
engañoso de leer después) — aplicado aquí desde el primer diseño, no
como corrección posterior descubierta por accidente.

**Rationale**: es la misma categoría de error para cualquier origen
cuyo modo histórico pueda no encontrar evidencia — vale la pena
tratarlo como un patrón conocido del propio motor, no reinventar la
misma sorpresa en cada generalización nueva.

## §10 — FR-006 validado en código, no solo pedido al modelo (hallazgo F1 de `/speckit-analyze`, 2026-08-12)

**Hallazgo real**: la primera versión de este plan/tasks solo pedía en
el prompt (§7) que el modelo nunca nombrara un relay concreto en un
episodio en diferido. El invariante hermano de esta misma familia
("exactamente una hipótesis `confirmada`" para `causa_probable`) sí se
valida en código desde 007 (`parsear_respuesta()`) — pedirle algo a un
LLM en el prompt y no comprobarlo después es exactamente el patrón que
ya falló una vez en este proyecto (007, hallazgo I2 de
`/speckit-analyze`: el modelo marcaba dos hipótesis `confirmada` a la
vez pese a que el prompt pedía una sola).

**Decisión**: `evidencia.listar_nombres_relay()` expone los `name`
reales de `socat_relays.json` ahora mismo.
`deepseek._menciona_relay_concreto(parsed, nombres)` busca cada nombre
(en minúsculas) como subcadena de `conclusion_texto` y de la
`descripcion`/`comprobacion` de cada hipótesis.
`diagnosticar_episodio()` aplica esta comprobación solo cuando
`episodio.origen == "relay"` y `snapshot["relay_agregado"]` no es
`None` (es decir, solo para episodios en diferido, donde la
información realmente no existe) — si la respuesta nombra un relay
real, se rechaza con el mismo tratamiento que una respuesta
inconsistente: coste real registrado, `no_diagnosticable` persistido
con el motivo explícito.

**Por qué ahora y no como corrección posterior**: a diferencia del
hallazgo de 007 (encontrado validando en vivo, después de gastar
dinero real en respuestas mal formadas), aquí `/speckit-analyze` lo
encontró **antes** de escribir ningún código — más barato de arreglar
en el diseño que después de implementar.

## §11 — Tasa de truncamiento alta en el episodio real de Escenario 4 (hallazgo real, validación en vivo, 2026-08-12)

**Hallazgo real**: diagnosticando en vivo el episodio 35
(`--relay-historico 2026-05-24T08:00:00`, la caída real de ~10h,
72 muestras de `relay_agregado` en la ventana ±180min, todas en
`ok=4, total=5`), 3 de 4 llamadas reales a DeepSeek con
`DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` en su valor por defecto (2000)
terminaron con `finish_reason: "length"`: el modelo de razonamiento
escribe su análisis en `reasoning_content` antes de llegar a volcar el
JSON final, y para este episodio ese razonamiento resultó
sistemáticamente largo (2296–8034 caracteres observados), agotando el
presupuesto de tokens antes de completar una respuesta válida. Repetir
la misma llamada con `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS=6000` sí produjo
una respuesta completa y correcta (`causa_probable`, una única
hipótesis `confirmada`, sin nombrar ningún relay concreto — la
cláusula del hallazgo F1/§7 se respetó también a nivel de prompt, sin
necesitar el rechazo en código de T011).

**No se tocó `DIAGNOSTICO_DEEPSEEK_MAX_TOKENS`**: mismo criterio que
§10 de `specs/010-diagnostico-ha/research.md` — es un valor ya fijado
deliberadamente (007, hallazgo B1 de `/speckit-analyze`) y un
truncamiento genuino por `finish_reason: "length"` se trata como
límite de coste aceptado, no como bug. Lo que aquí es distinto de 010
es la **tasa**: para episodios de relay en diferido con evidencia
agregada extensa, el truncamiento no fue la excepción sino la norma en
esta muestra (3/4). SC-005 exige "causa probable o 'no se puede
diagnosticar' honesto" — un `no_diagnosticable` por
`finish_reason: "length"` cumple la letra del criterio (nunca nombra
un relay, es honesto sobre no poder concluir), pero es una forma más
pobre de cumplirlo que una `causa_probable` bien formada. Queda
documentado como limitación conocida, no como corrección: subir el
límite global de tokens es una decisión de coste que afecta a los
cinco orígenes por igual y corresponde a Miquel, no a este feature en
solitario.
