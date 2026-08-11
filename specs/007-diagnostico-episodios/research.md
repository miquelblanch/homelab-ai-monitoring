# Research — Diagnóstico de Episodios

**Feature**: [spec.md](./spec.md)

## §1 — Sin LangGraph en este feature

**Decisión**: implementar el flujo como una tubería lineal en Python puro
(reunir evidencia → congelar snapshot → una llamada a DeepSeek → registrar),
sin ningún framework de orquestación de agentes.

**Rationale**: LangGraph aporta valor cuando hace falta estado compartido
entre nodos, ramas condicionales, bucles, o interrupciones para aprobación
humana a mitad de ejecución. Nada de eso existe todavía en el alcance de
este feature:

- FR-002/FR-003 obligan a reunir **toda** la evidencia antes de formular
  ninguna hipótesis — no hay un bucle de "pedir más datos según lo que
  responda el modelo" (eso sería agéntico; aquí la evidencia es fija de
  antemano, por diseño, precisamente para que el snapshot sea reproducible).
- FR-012/FR-013a excluyen cualquier acción — no hay ninguna rama de "actuar
  si la hipótesis se confirma" que orquestar todavía.
- El "contraste" de cada hipótesis (FR-005) se resuelve en la misma llamada
  que las propone (§2), no como pasos independientes con estado propio.

La premisa original de `CLAUDE.md` de este repositorio ("agente de
diagnóstico (LangGraph)") describe la visión completa del proyecto de
principio a fin, incluida la fase de remediación con lista cerrada de
acciones reversibles — que es exactamente donde LangGraph empieza a aportar
algo que Python plano no da gratis (grafo con nodos de "proponer acción" /
"esperar aprobación humana" / "ejecutar" / "verificar resultado", con
persistencia de estado entre ellos). `BRIEFING.md` ya registra esa
secuencia explícitamente al redefinir el alcance de Frente 2: diagnóstico
primero, sin ningún agente ni remediación automática todavía. Introducir
LangGraph ahora sería adoptar la complejidad de un framework de grafos para
una tubería de tres pasos sin ninguna rama — el propio proyecto ya evita
dependencias que no ganan nada (`inventory/` entero es librería estándar).

**Alternativas consideradas**: usar LangGraph desde ahora "para no
reescribir después". Rechazada — cuando exista de verdad un grafo con
ramas y aprobación humana (el feature de remediación), ese feature parte
de datos ya reales (episodios diagnosticados de verdad, no un mock), así
que no hay coste de reescritura que evitar por adelantado; adoptar el
framework antes de necesitarlo solo añade una dependencia y una curva de
aprendizaje sin beneficio medible hoy.

## §2 — Una sola llamada a DeepSeek: propone e contrasta a la vez

**Decisión**: un único prompt por intento de diagnóstico, con el snapshot
de evidencia completo incluido en el contexto, pidiendo una respuesta JSON
estructurada donde cada hipótesis lleva ya su descripción, cómo se
contrasta contra la evidencia dada, y su desenlace (`confirmada` /
`descartada` / `sin_evidencia_suficiente`). Temperatura fijada a `0` para
maximizar la reproducibilidad (FR-002, Edge Case de variación entre
llamadas).

**Rationale**: como toda la evidencia ya está reunida y congelada antes de
llamar al modelo (FR-002/FR-003), no hace falta que el modelo pida más
datos a mitad de razonamiento — puede proponer y contrastar en el mismo
paso, contra el mismo contexto. Una sola llamada por intento también
simplifica el cortacircuitos de gasto (FR-009/010): el coste de un
diagnóstico es el de una única respuesta, no una suma variable de N
llamadas (una por hipótesis) cuyo total no se conoce hasta terminar.

**Alternativas consideradas**: una llamada para proponer hipótesis y una
llamada adicional por hipótesis para contrastarla contra la evidencia.
Rechazada por ahora — multiplica el coste y la variables por reproducir
(cada llamada adicional es una fuente más de no-determinismo), sin que el
spec pida nada que obligue a separarlas; se puede revisar si en la
práctica el modelo demuestra que contrastar en el mismo turno que propone
da peor resultado que hacerlo aparte.

**Determinismo real**: `temperature=0` reduce pero no garantiza
matemáticamente el mismo texto, ni el mismo número de hipótesis, en dos
llamadas. FR-002 exige reproducibilidad de `conclusion_tipo` (causa
probable / no diagnosticable) — el criterio de comparación para SC-001
es exclusivamente ese campo, no el número, el texto ni el orden de las
hipótesis intermedias. **Decidido así explícitamente el 2026-08-11**
(`/speckit-analyze`, hallazgos U1/I1) tras evidencia real de T030: un
mismo episodio, diagnosticado dos veces, dio el mismo `conclusion_tipo`
pero 0 y 3 hipótesis respectivamente. Antes de esa fecha, este mismo
párrafo pedía además que coincidiera "el desenlace de cada hipótesis" —
un criterio más estricto que nunca se validó de verdad contra DeepSeek
real y que la propia naturaleza de un LLM en la nube no puede sostener
sin perder valor (forzar determinismo total de hipótesis intermedias
exigiría fijar el propio texto que el modelo genera, no solo la
temperatura). Se corrige aquí para que el documento diga lo que de
verdad se exige y se mide.

**La ambigüedad de "confirmada" (documentada aquí desde 2026-08-11,
antes solo en `tasks.md` T030)**: la validación real contra DeepSeek
encontró que el modelo, al diagnosticar un contenedor crítico sano sin
ningún episodio real que explicar, marcaba una hipótesis `"confirmada"`
en la misma respuesta que concluía `no_diagnosticable` — violando el
invariante FR-007. Causa raíz: el prompt no distinguía "esta
comprobación se completó" de "esta hipótesis ES la causa" para la
palabra "confirmada". Corregido en `_PROMPT_INSTRUCCIONES`
(`deepseek.py`) con una aclaración explícita de que `"confirmada"`
significa específicamente que esa hipótesis es la causa, nunca que una
comprobación individual haya terminado. Cualquier cambio futuro al
prompt debe conservar esa distinción explícita — es la causa raíz real
del único fallo de FR-007 observado hasta ahora, no una nota de
implementación desechable.

## §3 — Formato de la llamada a DeepSeek: HTTP puro, mismo patrón que `deliver.py`

**Decisión**: `urllib.request` + `ssl`, igual que `inventory/deliver.py`
hace con la API de Telegram — sin el SDK oficial de DeepSeek ni ninguna
librería HTTP de terceros. Endpoint compatible con el formato "chat
completions"; modelo configurable vía variable de entorno
(`DIAGNOSTICO_DEEPSEEK_MODEL`, por defecto `deepseek-v4-flash` — elegido
por Miquel el 2026-08-10 tras validar el feature en `deepseek-chat`),
clave vía
`_homelab_bridge.get_secret("DEEPSEEK_API_KEY")`.

**Rationale**: coherencia con la convención ya establecida del repo (cero
dependencias nuevas, ver `inventory/deliver.py`/`sources.py`) — una
petición HTTP con JSON de entrada y salida no justifica una dependencia
nueva. El nombre exacto del modelo de producción de Bautista
(`deepseek-v4-pro`, `CLAUDE.md` general del homelab) puede no coincidir
con el identificador de modelo expuesto por la API pública de DeepSeek en
el momento de implementar — se resuelve como parámetro configurable, no
hardcodeado, precisamente porque puede cambiar sin que cambie este spec.

**Alternativas consideradas**: SDK oficial `openai`/`deepseek` de Python.
Rechazada por ahora — añadiría la primera dependencia externa real del
repo por una llamada HTTP que `urllib` ya resuelve, rompiendo la
convención de "cero dependencias" sin necesidad.

## §4 — Persistencia: base SQLite propia, mismo patrón que `inventario.db`

**Decisión**: `diagnostico.db`, en
`/Volumes/FastData/homelab/docker/homelab-orchestrator/data/` (misma
carpeta que `inventario.db` y `homelab.db`), configurable vía
`DIAGNOSTICO_DB_PATH` (mismo patrón que `INVENTORY_DB_PATH`). Cuatro
tablas: `episodios`, `hipotesis`, `diagnosticos`, `gasto_diario`
(data-model.md).

**Rationale**: esa carpeta ya está cubierta por el backup nocturno de
FastData sin ninguna configuración adicional — mismo razonamiento que
`store.py` de `inventory` documenta para `inventario.db`. Una base propia
(en vez de añadir tablas a `homelab.db`) evita que este feature, todavía
experimental, escriba en la base de datos de la que depende
`docker_monitor.py` en producción.

**Lectura de `homelab.db`**: conexión normal de `sqlite3.connect()`, sin
`mode=ro` en la URI — se probó `mode=ro` contra el fichero real (montado
sobre `/Volumes/FastData`, red) y falló con `unable to open database file`,
mientras que una conexión normal funciona sin problema. La disciplina de
"nunca escribir" se aplica por convención de código (solo `SELECT`, nunca
`INSERT`/`UPDATE`/`DELETE` contra esa conexión), igual que ya hace el resto
del homelab al leer bases ajenas, no por un flag de solo-lectura a nivel de
SO/SQLite que en este entorno no es fiable.

## §5 — Evidencia de contenedor: `homelab.db` + `docker inspect`/`docker logs` con lista blanca

**Decisión**: reutilizar exactamente el patrón `_READONLY_ALLOWLIST`/
`_run_ro()` de `inventory/sources.py`, ampliado con `("docker", "logs")`
además de los ya existentes `("docker", "ps")`/`("docker", "inspect")`.

- **Diferido** (`restart_history`): fila de `homelab.db.restart_history`
  para el episodio (`container_name`, `timestamp`, `result`, `reason`,
  `triggered_by`) + ventana de `container_metrics` alrededor de ese
  `timestamp` (±30 min, configurable) + fila(s) de `disk_metrics` más
  próximas en el tiempo, por si el episodio coincide con presión de disco.
- **En vivo**: mismo tipo de ventana de `container_metrics` (las últimas
  muestras disponibles, ya que `docker_monitor.py` escribe cada 5 min con
  independencia de si hay o no un episodio activo) + `docker inspect
  <container>` (estado/salud actual, no capturado aún por la muestra de 5
  min) + `docker logs --tail 200 <container>` (motivo textual que
  `restart_history.reason` no tiene en el caso en vivo, porque el episodio
  todavía no ha cerrado).

**Rationale**: `container_metrics`/`disk_metrics` ya existen y ya cubren
tanto el caso vivo como el histórico con la misma tabla — no hace falta
ninguna fuente nueva de métricas. `docker logs` es la única fuente
realmente nueva que este feature necesita frente a lo que `inventory` ya
usa, y encaja en el mismo mecanismo de lista blanca ya validado (T040 de
feature 001) en vez de inventar uno paralelo.

**Alternativas consideradas**: parsear logs de LaunchAgents
(`~/Library/Logs/`) también como evidencia. Fuera de alcance por ahora —
el spec limita la evidencia a "métricas de contenedores/disco, logs,
estado de otros componentes relevantes" (FR-003) sin exigir esa fuente en
concreto; se añade si la validación contra los episodios de `beszel`
(FR-011) demuestra que hace falta.

## §6 — Coste diario: tabla `gasto_diario` con tabla de precios como constante

**Decisión**: cada respuesta de DeepSeek reporta `usage.prompt_tokens` /
`usage.completion_tokens` (y `prompt_cache_hit_tokens`/
`prompt_cache_miss_tokens` si la API los distingue). Un diccionario
`PRECIOS_EUR_POR_MILLON_TOKENS` a nivel de módulo (entrada/salida/caché)
convierte esos conteos reales en euros; se suma al acumulado de
`gasto_diario` para el día natural en curso (huso horario local del Mac
Mini). Límite configurable vía `DIAGNOSTICO_LIMITE_EUR_DIA` (por defecto
`5.0`, el número de partida de Miquel — Assumptions del spec).

**Rationale**: cumple FR-009 al pie de la letra — "a partir de los tokens
que la propia respuesta reporta", nunca consultando la facturación de la
API. Un diccionario de precios como constante (no una llamada a un
endpoint de precios) porque DeepSeek no expone tal endpoint y los precios
cambian con poca frecuencia — se anota en el propio código que debe
revisarse si DeepSeek cambia su tarifa, mismo espíritu que otros
"revisar periódicamente" ya presentes en el proyecto (Principio III).

**Cortacircuitos (FR-010)**: antes de cada llamada, `gasto.py` comprueba si
`gasto_acumulado_hoy + coste_estimado_de_la_llamada > limite_configurado`.
El coste del prompt de entrada se conoce exactamente antes de llamar (es
texto ya construido, se cuenta directamente). El coste de la salida se
estima con el mismo número que se envía como `max_tokens` en la propia
petición a DeepSeek — no una cifra "prudente" aparte inventada para la
estimación, sino el mismo límite duro que la API usará de verdad para
truncar la respuesta si hiciera falta. Constante
`DIAGNOSTICO_DEEPSEEK_MAX_TOKENS` (por defecto `2000` — suficiente para
varias hipótesis con su comprobación en el JSON de §2; una tanda de 5-6
hipótesis con descripción + comprobación en prosa breve no debería
necesitar más), configurable por variable de entorno igual que el resto de
límites de este feature (ver contracts/cli.md). La estimación previa a la
llamada es entonces `tokens_entrada_reales + DIAGNOSTICO_DEEPSEEK_MAX_TOKENS`
contra `PRECIOS_EUR_POR_MILLON_TOKENS` — un límite superior real (porque
`max_tokens` es matemáticamente lo máximo que DeepSeek puede devolver), no
una suposición sin respaldo. Tras la respuesta real (casi siempre por
debajo de `max_tokens`, salvo que la respuesta se trunque) se registra el
coste efectivo exacto, nunca la estimación — la estimación solo decide si
se llama o no, jamás lo que queda persistido en `diagnosticos.coste_eur`.

## §7 — `_homelab_bridge.py` propio, duplicado deliberadamente

**Decisión**: `diagnostico/_homelab_bridge.py` es una copia mínima (no una
importación) de las funciones de `inventory/_homelab_bridge.py` que este
feature necesita: `get_secret`, `record_heartbeat`, `docker_critical`,
`docker_never_restart`. No añade `ha_monitor_*` (este feature no toca HA).

**Rationale**: `inventory` y `diagnostico` son dos paquetes hermanos
independientes bajo `src/`, sin que ninguno dependa del otro — mismo
principio que ya aplica entre features de Spec Kit (cada uno es
autocontenido). Extraer un tercer paquete compartido (`src/_common/`) para
~40 líneas usadas por dos consumidores es la abstracción prematura que las
reglas operativas de este proyecto ya piden evitar; si aparece un tercer
consumidor con la misma necesidad, ese es el momento de extraerlo de
verdad, no antes.

**Uso de `docker_critical()`/`docker_never_restart()`**: FR-013a exige que
el sistema nunca proponga ni ejecute una acción sobre un contenedor
crítico. Como este feature no ejecuta ninguna acción en absoluto (FR-012),
el uso real de esas dos funciones es más simple: marcar el `episodio` como
`es_critico` en el momento de congelarlo (para que el prompt a DeepSeek
incluya explícitamente esa condición y el modelo nunca redacte una
hipótesis en clave de "acción a tomar"), leyendo la lista tal cual la
mantiene `docker_monitor.py` — nunca una copia propia que pudiera
desincronizarse.

## §8 — CLI: tres verbos, sin disparo automático

**Decisión**: `congelar`, `diagnosticar`, `mostrar`, más `--selftest` —
ver `contracts/cli.md`. Ningún LaunchAgent, ningún cron, ningún modo
"vigilar y disparar solo" (FR-015).

**Rationale**: separar "congelar" de "diagnosticar" hace explícito en la
propia interfaz el momento exacto en que se fija el snapshot (FR-002) —
Miquel puede congelar un episodio en vivo y decidir más tarde si gastar
presupuesto de DeepSeek en diagnosticarlo, o diagnosticar el mismo
`episodio_id` dos veces para comprobar la reproducibilidad (SC-001) sin
tener que reconstruir la evidencia desde cero cada vez.
