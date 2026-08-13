# Briefing — Monitorización completa del homelab

> Material de partida para `speckit-constitution` y `speckit-specify`.
> **Esto no es la especificación.** Es lo que se sabe antes de escribirla.

---

## El objetivo, dicho sin rodeos

Este proyecto no nació para explicar por qué un contenedor se reinició 49 veces,
ni para arreglar cuatro casos concretos uno por uno. Nació de investigar estos casos, 
pero se hizo evidente algo más grande: **la monitorización del homelab
tiene agujeros, y no hay forma de saber cuántos son ni dónde están todos.**

El objetivo no es una lista de arreglos. Es un **sistema de monitorización
avanzado que encuentre sistemáticamente TODOS los problemas reales del homelab**
—no solo los que ya se conocen— y que, para cada uno:

- si la causa ya está diagnosticada y la corrección es segura y reversible,
  **lo resuelva solo**;
- si no, **avise a Miquel con contexto suficiente para que lo resuelva él**.

Los cuatro casos de abajo no son "la lista de tareas". Son la prueba de que el
problema es sistémico, no anecdótico — y de que parchear caso por caso nunca va
a ser suficiente.

---

## Lo que ya sabemos que falla

Cuatro casos, encontrados en momentos distintos, con el mismo patrón: algo se
rompe y el sistema no avisa.

| Caso | Qué pasó | Estado de la investigación |
| --- | --- | --- |
| **1 · Reinicios de beszel** | Un contenedor se reinició 49 veces en siete semanas. Cero alertas. | Investigado a fondo (ver más abajo). Causa raíz no encontrada — y con la evidencia disponible, no se puede encontrar (ver "Criterio de muerte"). |
| **2 · Barrido del 01-08-2026** | Revisión manual de 86 puntos del dashboard y Home Assistant: 11 problemas reales, 0 visibles en el dashboard. | Investigado a fondo. Causas conocidas y escritas en `BARRIDO-2026-08-01.md`. |
| **3 · Beszel no vigila bien lo que vigila** | El propio Beszel —la herramienta que vigila CPU/memoria/disco de otras máquinas— muestra 2 de sus 3 sistemas en rojo (`AdGuardHome`, `UptimeKuma`). Solo `Mac Mini Server` en verde. | Investigado a fondo. El síntoma original no se reprodujo (ver "Feature 003 — material de partida"); el hueco real que sí quedaba —si el hub deja de reportar para los tres a la vez, nada lo distingue de "los tres están bien"— lo cierra `specs/003-latidos-beszel-calendario/` (latido de `beszel-hosts`, verificado en producción el 13-08-2026). |
| **4 · Recordatorios de Nextcloud** | Los recordatorios de Tareas/Calendario de Nextcloud, que deberían avisar por Telegram, no llegan. | Investigado a fondo. `BARRIDO-2026-08-07.md` encontró y arregló un fallo silencioso real en `recordatorios_hoy()`; el hueco que quedaba —`bautista-calendar.sh` sin latido propio— lo cierra `specs/003-latidos-beszel-calendario/`, verificado en producción el 13-08-2026. |

Los cuatro casos están investigados a fondo — el resto de este documento y
`specs/003-latidos-beszel-calendario/` explican qué se encontró en cada uno.

**Importante:** esto no es una lista cerrada. Son los cuatro casos que se han
encontrado *por casualidad*, mirando distintas cosas en distintos momentos.
Nadie ha hecho todavía el ejercicio de recorrer sistemáticamente los 40
contenedores y todas las integraciones del homelab preguntando, de cada uno,
"¿esto tiene un estado esperado declarado, se vigila, y si falla se sabría?".
Eso —no investigar los casos 3 y 4 uno por uno— es lo que de verdad hace falta
antes de escribir ningún spec.

---

## Las cinco preguntas

**Qué.** Un sistema de monitorización avanzado con dos partes:

1. **Cobertura sistemática, no anecdótica.** Todo lo que forma parte del
   homelab —los 40 contenedores, las integraciones, los recordatorios, lo que
   se venga a añadir después— tiene un estado esperado declarado (Principio
   III), se vigila de verdad, y si algo falla, llega al dashboard del homelab
   (`http://homelab.amsterdam9.home/`) una vez y sin ausencias (Principio XII).
   No es una lista de servicios elegidos a mano: es un método que se aplica a
   todo por igual.
2. **Dos caminos de respuesta**, según cada problema que se detecte: si la
   causa ya está diagnosticada con certeza y la corrección es segura y
   reversible, un agente (grafo de LangGraph) la aplica solo, dentro de una
   lista cerrada de acciones reversibles. Si no, avisa a Miquel con contexto
   suficiente para que lo resuelva él.

**Por qué.** Cuatro casos encontrados por casualidad (arriba), del mismo
patrón: algo se rompe, y nadie se entera hasta que alguien mira a mano. Si
cuatro aparecieron sin buscarlos activamente, la pregunta real no es "¿cómo
arreglo estos cuatro?" — es "¿cuántos más hay, y cómo dejo de depender de la
suerte para encontrarlos?".

**Para quién.** Para Miquel, que gestiona su propia infraestructura. Es un solo
usuario: no hace falta pensar en varios usuarios ni en garantías de
disponibilidad. En segundo lugar, para quien lea el caso de estudio público:
este proyecto continúa el repositorio público del homelab.

**Cómo.** Dos frentes, que no dependen el uno del otro:

- **Un inventario sistemático**, no una investigación caso por caso: recorrer
  todo lo que compone el homelab y, de cada pieza, responder "¿tiene estado
  esperado declarado? ¿se vigila? ¿si falla, se sabría?". 
- **Un grafo de LangGraph** que, cuando se detecta un problema: formula
  posibles causas y las comprueba una a una contra el sistema, lo corrige si la
  causa ya está diagnosticada y la acción está en la lista cerrada de
  reversibles, y si no puede —porque se queda sin ideas o porque la acción es
  peligrosa— se lo dice a Miquel.

**Cuándo.** Sin fecha límite. Es un proyecto largo. El ritmo lo marcan los
artefactos de Spec Kit (constitution, spec, plan, tasks), no un calendario.

---

## Caso 1, en detalle: los reinicios de beszel

Los hechos:

- El mismo contenedor (`beszel`) se ha reiniciado automáticamente 49 veces, sin
  causa conocida.
- Esos 49 reinicios son el **59% de todas las intervenciones automáticas** del
  sistema (49 de 83 en total).
- **Nunca llegó una alerta.** La regla era "avisar solo cuando cambia el
  estado", así que cada reinicio se registraba como un simple mensaje de
  recuperación, y nadie se enteraba.
- La investigación manual descartó dos explicaciones posibles y no encontró una
  tercera.


---

## Qué existe ya, y que el agente NO debe sustituir

`docker_monitor.py` corre cada cinco minutos y funciona bien. Clasifica todos los
contenedores en tres grupos: **CRITICAL** (si falla, avisa, pero no lo toca),
**NEVER_RESTART** (lo ignora) y el resto (lo reinicia y, a los 10 segundos,
comprueba que siga funcionando). Además tiene un límite de seguridad: si falla 3
veces en 6 horas, deja de intentarlo.

**El agente se añade a esto, no lo reemplaza.** El monitor seguirá siendo quien
reinicie los contenedores — eso no cambia. Lo que el agente aporta es lo que hoy
no existe: ampliar qué se vigila y cómo se avisa, y corregir —dentro de una
lista cerrada de acciones reversibles— lo que ya esté diagnosticado con
certeza. Nada de esto sustituye al monitor, y nada actúa sobre contenedores
críticos.

Por qué importa esto: si el agente reemplazara al monitor y el agente fallara,
se perdería la remediación automática que lleva meses funcionando bien. Un
componente nuevo y experimental no puede poner en riesgo algo que ya funciona.

---

## Principios candidatos para la constitución

Redactados en la primera versión de este briefing, antes de correr
`speckit-constitution`. Ya están incorporados en `.specify/memory/constitution.md`
(que hoy tiene 12 principios, no 6) y quedan aquí solo como registro histórico,
no como fuente viva.

**1 · Ninguna acción sobre un contenedor crítico sin aprobación humana explícita.
NO NEGOCIABLE.**

**2 · El agente diagnostica; el monitor sigue actuando.**

**3 · Toda hipótesis se registra, con su comprobación y su resultado.**

**4 · Nada cuenta como mejora hasta que se compara con la línea base.**

**5 · Local por defecto.**

**6 · Todo diagnóstico tiene que poder reproducirse en diferido.**

---

## En alcance ahora

> **Nota (2026-08-13): esta sección y la siguiente son de la fase de
> planificación original, anteriores al feature 002 — más antiguas que
> todo lo demás en este documento.** No se reescriben para que parezcan
> siempre acertadas (mismo criterio que ya aplican `BRIEFING.md` para
> el desajuste de numeración de 006 y `specs/008-.../spec.md` para
> "Correcciones" vs. "Alarmas"): se documenta aquí el desajuste real,
> encontrado al revisar el estado del proyecto a fondo. En concreto,
> "Fuera de alcance por ahora" decía que diagnosticar Home Assistant y
> los relays era "otro terreno" — dejó de ser cierto en cuanto los
> features 010 y 012 los generalizaron, y nadie actualizó esta sección
> entonces. El estado real y vigente de qué está en alcance es el de
> `constitution.md` ("Alcance y Límites"), no el de esta sección.

- **Inventario sistemático de cobertura**: recorrer todo el homelab —no solo
  los cuatro casos conocidos— y para cada pieza comprobar si tiene estado
  esperado declarado, si se vigila, y si un fallo llegaría al dashboard. Esto
  viene antes que escribir código de agente para casos nuevos.
- **Cobertura y precisión del dashboard** (`http://homelab.amsterdam9.home/`):
  que toda alarma real activa aparezca, una sola vez, sin que falte ninguna
  (Principio XII de la constitución).
- **Corregir, de forma reversible, lo que ya esté diagnosticado con certeza**
  —empezando por la lista del barrido del 01-08 (deduplicación, ficheros
  corruptos, rotación de logs, logs en `/tmp`, healthchecks que faltan)— dentro
  de una lista cerrada de acciones reversibles, cada una con su forma
  documentada de deshacerla (Principios V y VI).
- **Avisar a Miquel, con contexto**, para todo lo que se detecte y no tenga
  corrección segura y reversible ya diagnosticada. No todo problema encontrado
  tiene que resolverlo el agente — muchos los resuelve Miquel, pero solo si se
  entera.

## Fuera de alcance por ahora

- **Perseguir la causa raíz de los 49 reinicios de beszel.** Ya se comprobó que
  la evidencia no basta (ver más arriba). Insistir ahí sin más instrumentación
  sería repetir el error que ya se cometió una vez.
- **Cualquier acción sobre contenedores críticos** (la lista del monitor), esté
  diagnosticado o no el problema. Ahí siempre se detiene y espera que Miquel lo
  apruebe.
- Diagnosticar Home Assistant y los relays. Es otro terreno, con otras fuentes
  de información.
- Cualquier incidencia que el monitor actual ya resuelve solo, sin ayuda.

---

## Decisiones ya tomadas

**Repositorio público.** Contiene rutas, nombres de contenedores y salidas de
diagnóstico reales, pero saneadas según la política habitual: **se nombra el
software que se usa, no cómo está montada la red real** — nada de datos que
afecten a la seguridad física (por ejemplo, entidades ligadas a una cerradura
real) ni credenciales. Decidir esto ahora no cuesta nada; decidirlo después de
tres meses de commits significaría reescribir todo el historial de git.

**Acceso a los datos consultando SQLite directamente**, porque es una base de
datos propia, no de un tercero.

**La entrega es por Telegram**, como el resto de las automatizaciones del
homelab. No hace falta construir una interfaz nueva.

**El dashboard ya existe, no se construye uno nuevo.** La cobertura de alarmas
se resuelve arreglando qué llega y cómo se deduplica en
`http://homelab.amsterdam9.home/`, que ya está ahí.

---

## Feature 002 — material de partida (2026-08-08)

Tras cerrar feature 001, la primera ejecución real del inventario dejó 322
brechas (790 componentes). 318 son el mismo hallazgo repetido —entidades HA
sin estado declarado— ya aparcado como su propio problema, de volumen, no de
diseño. Las 4 restantes son las únicas "de verdad": exactamente los Casos 3
y 4 de este briefing, más el punto que `specs/001-.../spec.md` (Assumptions,
líneas 373-386) ya había anotado como candidato natural a feature 002:
`docker_monitor_state.json` y `ha_monitor_state.json` calculan una alarma
que el dashboard no muestra.

Antes de especificar, se investigaron las 4 contra el código y los datos
reales del homelab (no contra lo que decía la documentación) para separar
dos tipos de brecha que a simple vista parecen iguales:

| Brecha | ¿Ya existe la señal, solo falta mostrarla? | Evidencia |
|---|---|---|
| Contenedores (`docker_monitor_state.json`) | **Sí** — 50 entradas `{ok, down_since}`, cada 5 min | `app.py` no lo lee en ningún sitio; el panel de contenedores hace `docker ps` en vivo y no puede mostrar "estuvo caído y se recuperó" ni el cortacircuitos de reinicios — el mismo patrón que dejó pasar sin alerta los 49 reinicios de beszel |
| Home Assistant (`ha_monitor_state.json`) | **Ya resuelto en gran parte** (2026-08-08) | `get_ha_monitor()` ya lo lee; cubre las ~15 entidades que vigila `ha_monitor.py` una a una. Las ~357 restantes del registro son el bulto ya aparcado, no este caso |
| Host de Uptime Kuma / Host de AdGuard | **Sí, pero en otro sistema** | Consultado `data.db` de Beszel directamente: ambos `up`. El dato vive en el volumen `beszel_hub_data`, que el dashboard no monta ni lee |
| Beszel (hub) | **No** | Ninguna señal calculada todavía — nada vigila si el propio hub está vivo y reportando bien |
| Recordatorios de Nextcloud | **No** | El bug silencioso ya se arregló (`BARRIDO-2026-08-07.md`), pero sigue sin heartbeat propio |

**Por qué importa la distinción:** el propio `spec.md` de feature 001
justificó el candidato a feature 002 como "mecánicamente independiente":
*"no necesita identidad estable, ni caducidad, ni SQLite — solo leer dos
ficheros que ya existen y sumarlos al panel"*. Eso es cierto para
contenedores, y ya en parte para HA. Para Kuma/AdGuard es casi igual de
barato — un script más que escribe un JSON, mismo patrón que el resto del
homelab, sin montar el volumen del hub de Beszel directamente en el
dashboard. Pero Beszel (hub) y Recordatorios de Nextcloud son harina de
otro costal: no hay nada que "mostrar" todavía, hace falta decidir qué
significa "sano" para un monitor que se vigila a sí mismo, o instrumentar
un heartbeat nuevo. Eso es trabajo real de `clarify`/`plan`, no una lectura
de fichero.

**Alcance propuesto para feature 002:**

- **Dentro**: cerrar `docker_monitor_state.json` → panel de contenedores, y
  Kuma/AdGuard → panel nuevo o extendido. Cierra 3 de las 4 brechas reales
  sin abrir ninguna decisión de diseño nueva.
- **Fuera, para un feature posterior**: Beszel (hub) y Recordatorios de
  Nextcloud — cada uno necesita su propio `clarify` sobre qué constituye un
  fallo, y mezclarlos aquí diluiría lo que hace barato a este feature.

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El dashboard del homelab (`http://homelab.amsterdam9.home/`) ya recibe,
> cada 5 minutos, una alarma calculada por contenedor (`docker_monitor.py`:
> si está caído y desde cuándo) y, para los hosts físicos distintos del Mac
> Mini que vigila Beszel (Uptime Kuma, AdGuard Home), un estado calculado
> por Beszel — pero ninguna de las dos llega hoy al panel. Quiero que toda
> alarma real activa de estos dos orígenes aparezca en el dashboard, una
> sola vez y sin ausencias, sin construir ningún portal ni interfaz nueva —
> el dashboard ya existe. No incluye vigilar el propio Beszel ni los
> recordatorios de Nextcloud: esos no tienen todavía una señal calculada
> que mostrar.

---

## Feature 003 — material de partida (2026-08-08)

Tras cerrar feature 002, quedan 2 de las 4 brechas reales originales:
Beszel (hub) y los recordatorios de Nextcloud — Casos 3 y 4 de este
briefing, dejados fuera de 002 a propósito porque ninguno tenía una señal
calculada que simplemente exponer. Investigados otra vez contra el código
y los datos reales antes de especificar, los dos han cambiado de estado
desde que se escribieron esos casos:

**Caso 4 (recordatorios de Nextcloud) — más cerca de lo que parecía.**
El barrido del 2026-08-07 ya arregló el fallo silencioso de
`recordatorios_hoy()` (un `""` que significaba dos cosas distintas) y
añadió healthcheck real a los 3 contenedores de Nextcloud — la vía por la
que "Nextcloud corriendo pero roto" podía pasar desapercibido ya está
cerrada, y desde feature 002 ese resultado también llega al dashboard.
Lo único que falta de verdad: **`bautista-calendar.sh` no llama a
`heartbeat.write()` en ningún punto** — ni al éxito, ni al silencio
intencionado (sin eventos hoy), ni al error ya distinguido. Mismo patrón
exacto que se acaba de construir para `beszel-hosts`: un latido al final
de cada ejecución (haya o no eventos), sumado a "Estado de los monitores".

**Caso 3 (Beszel no vigila bien lo que vigila) — el síntoma original ya
no se reproduce.** Consultada la tabla `systems` real: los 3 sistemas
(`Mac Mini Server`, `AdGuardHome`, `UptimeKuma`) están `up`, con `updated`
de hace un par de minutos — no los 2 en rojo que describía el caso original
(06-08-2026, antes de los relays de Beszel del 07-08 y del lector de
feature 002). Lo que sigue sin existir es la pregunta de fondo: **si el
propio hub deja de reportar** (deja de escribir `updated` nuevos para
todos, no solo para uno) **nada lo distingue de "los tres sistemas están
bien"**. `scripts/beszel_hosts_monitor.py` ya lee la tabla `systems`
completa (`research.md` §3 de 002) — ampliarlo para comprobar la
antigüedad de `updated` de los 3, no solo el `status` de 2, es reutilizar
infraestructura ya construida, no partir de cero.

Los dos casos comparten forma: instrumentar un latido que hoy no existe,
sobre infraestructura de lectura que ya existe (`heartbeat.py` para el
primero, `beszel_hosts_monitor.py` para el segundo). Miquel ha pedido
bundlarlos en un solo feature 003 en vez de separarlos — la objeción que
tenía (madurez distinta) queda parcialmente resuelta: los dos resultan
ser extensiones baratas de mecanismos ya desplegados, no dos alcances de
tamaño distinto.

> **Cierre confirmado (2026-08-13).** `specs/003-latidos-beszel-calendario/`
> se implementó el 09-08-2026 — lo de arriba queda como el material de
> partida, no como el estado actual. Verificado en producción hoy, no
> solo en el código: `bautista-calendar.sh` **sí** llama a
> `heartbeat.write()` en cada ejecución (la frase de más arriba, "no llama
> a `heartbeat.write()` en ningún punto", ya no es cierta), y tanto
> `bautista-calendar` como `beszel-hosts` están dados de alta en
> `MONITOR_JOBS` del dashboard, con latidos frescos reales (266 s y 9,3 h
> de antigüedad respectivamente, ambos bajo su umbral). Los casos 3 y 4
> quedan cerrados. Único matiz revisado y descartado como bug: el latido
> de `bautista-calendar.sh` marca `status='ok'` incluso cuando el detalle
> es "error real detectado" — pero ese fallo real ya se notifica al
> instante por Telegram (`recordatorios_hoy()` tiene su propio
> distingo desde el barrido del 07-08), y el mismo patrón de
> `status='ok'` siempre lo usan los otros cinco monitores con latido
> (`docker-monitor`, `ha-monitor`, `dns-pi-monitor`, `verify-backups`,
> `beszel-hosts`): el campo indica que el ciclo del monitor se completó,
> no que lo vigilado esté sano — eso va por su propio canal de alerta.
> Cambiarlo solo aquí rompería esa consistencia; queda anotado, no hecho.

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> Dos piezas de la propia infraestructura de monitorización del homelab
> no tienen todavía una señal que confirme que siguen funcionando de
> verdad, más allá de que el proceso esté vivo. La primera:
> `bautista-calendar.sh` (recordatorios de Nextcloud, cron de las 10:00)
> no dice nunca si se ha ejecutado — ni cuando manda recordatorios, ni
> cuando calla porque hoy no hay eventos, ni cuando ya detecta y reporta
> un fallo real de los calendarios. La segunda: Beszel, la propia
> herramienta que vigila los hosts físicos de Uptime Kuma y AdGuard Home
> (y el Mac Mini), no tiene ninguna comprobación de si sigue reportando
> datos frescos sobre los tres — si el hub se queda colgado o deja de
> sincronizar, hoy no hay forma de saberlo salvo notarlo por casualidad
> (es el mismo tipo de fallo que ya se investigó y no se confirmó el
> 06-08-2026). Quiero que las dos tengan un latido propio, visible en el
> panel "Estado de los monitores" del dashboard que ya existe, con el
> mismo criterio de frescura que usa el resto de monitores del homelab.
> No incluye rediseñar cómo funcionan los recordatorios de Nextcloud ni
> la configuración de Beszel — solo instrumentar la vigilancia que les
> falta.

---

## Feature 004 — material de partida (2026-08-09)

Tras cerrar 002 y 003 solo quedaban brechas `entidad_ha` (328, luego 309
tras la limpieza de este mismo día — ver más abajo). A diferencia de 002
y 003, aquí no había una señal ya calculada esperando a exponerse: había
que investigar qué son de verdad esas ~300 entidades antes de decidir
nada, porque tratarlas como un bloque homogéneo habría escondido tanto
ruido real como señales de seguridad genuinas.

**Investigación previa a especificar — con el homelab en vivo, no solo
con el registro de HA:**

1. **Frigate encendido a propósito por Miquel** para el análisis (normalmente
   `NEVER_RESTART`, cámaras dadas por desconectadas). Los logs mostraban
   timeout de RTSP constante en las dos cámaras — pero comprobado desde
   el host, las dos respondían de verdad en el puerto 554. La causa real:
   Frigate corre en su propia red bridge de Docker, sin ruta a la LAN —
   mismo problema exacto que Beszel/HA, nunca corregido aquí porque se
   daba a Frigate por permanentemente apagado. **Ya resuelto y desplegado
   en producción** (no parte de este feature, ya hecho):
   - Relays permanentes `amsterdam9.frigate.relay-cocina`/`-salon`
     (`homelab.amsterdam9.home:5540/5541`), vigilados en
     `dump_socat_status.py`.
   - `config.yaml` de Frigate apuntando a los relays en vez de a las IPs
     directas.
   - Confirmado con datos reales: las dos cámaras a 14 fps.
2. **Auditoría de `entity_category`** contra las 328 brechas: 133 son
   `config`/`diagnostic` (ajustes o telemetría interna de HA), pero 5 son
   señales de seguridad reales que la categoría diagnostic no debería
   esconder (batería crítica de la cerradura, enchufes "sobrecargado") y
   12 son los switches de Frigate (mejor tratados con la lógica
   condicional del punto 1, no con una regla genérica).
3. **Auditoría de las 39 `automation.*`**: 17 tenían nombre de
   contenedor/servicio (`beszel`, `frigate`, `nextcloud`, `uptime_kuma`…)
   y resultaron ser una capa de alertas por Telegram/push redundante con
   lo que este mismo proyecto ya vigila — creadas todas el mismo día
   (`unique_id` correlativos), disparaban en `sensor.<servicio>_estado
   → down`. **Ya eliminadas** (vía API de HA, con backup de
   `automations.yaml`). De las 22 restantes, otras 5 resultaron
   redundantes con checks que ya existen en `ha_monitor.py`/
   `bautista-calendar.sh` (conectividad de la cerradura, batería,
   nivel de sal, recordatorios) — **también eliminadas**, decisión
   explícita de Miquel tras leerlas una a una. Quedan 17 automatizaciones
   domésticas genuinas sin duplicado en ningún otro sitio.

**Estado tras la limpieza (2026-08-09): 309 brechas, todas `entidad_ha`.**

**Alcance cerrado para este feature:**

| Pieza | Cuántas | Tratamiento |
|---|---|---|
| `entity_category` config/diagnostic (menos las 17 excepciones de abajo) | 115 | Declarar "no aplica" — no son señales de salud, son ajustes o telemetría interna |
| Entidades de Frigate (cámaras, movimiento, snapshots, switches) | 33 | Vigiladas **solo si Frigate está corriendo** (estado en vivo del contenedor, ya disponible); error = entidad `unavailable`/`unknown` mientras Frigate corre; si Frigate está parado (su estado normal), intencionado — mismo trato que ya tiene el contenedor `frigate` |
| `automation.*` domésticas restantes | 17 | Declarar esperado = activada (`on`) — una automatización que se desactiva sola y nadie se entera es el mismo tipo de fallo silencioso que motivó este proyecto |

**Explícitamente fuera de alcance, pendiente aparte:**
- Las 5 excepciones de seguridad (batería crítica/cargando de la
  cerradura, 3 enchufes "sobrecargado") — necesitan declaración propia,
  no la regla genérica ni el silencio actual.
- Las ~134 entidades restantes (localización de iPhones/MacBook,
  sensores de temperatura/energía por habitación, luces Zigbee
  individuales, scripts, helpers, estado de backups en HA…) — cola larga
  sin triar todavía, deliberadamente fuera de este feature para no
  repetir el error de tratar 300 entidades distintas como un bloque.

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El inventario de cobertura marca ~165 entidades de Home Assistant como
> brecha (sin estado esperado declarado) que en realidad no necesitan una
> declaración individual: unas porque son ajustes o telemetría interna de
> la propia integración (`entity_category` config/diagnostic — botones
> "identify", niveles de log, versión de la app, opciones de color...),
> y otras porque pertenecen a Frigate, cuyo estado esperado depende de si
> el contenedor está corriendo o no — hoy Frigate está pensado para estar
> permanentemente apagado, así que sus ~33 entidades no deberían contar
> como brecha mientras esté parado, pero si algún día se enciende y algo
> falla de verdad, sí debería avisar. Además, 17 automatizaciones
> domésticas (toldos, cerradura, luces, proyector, sirenas...) no tienen
> ninguna vigilancia de si siguen activadas — si una se desactiva sola,
> nadie se entera hasta que falla el efecto que se esperaba de ella.
> Quiero que las tres cosas se traten como corresponde: las de ajuste/
> diagnóstico dejan de contar como brecha; las de Frigate solo cuentan
> como brecha cuando Frigate está encendido y algo va mal de verdad; las
> automatizaciones domésticas pasan a tener un estado esperado (activada)
> que si se incumple sí es una brecha real. No incluye las 5 entidades de
> seguridad (batería de la cerradura, enchufes sobrecargados) ni el resto
> de la cola larga sin triar — esas quedan para un feature posterior.

---

## Feature 005 — material de partida (2026-08-09)

Tras cerrar 004 quedaban 150 brechas `entidad_ha` (309→190→150 en el
propio despliegue de 004, con datos reales, no solo la estimación
original). Investigadas por `platform` del registro de HA (mismo
criterio que ya separó el ruido real de las señales de seguridad en
004), salen 17 plataformas distintas. Dos son limpias, baratas y sin
ambigüedad — el resto (`melcloud`, `esphome`, `tplink`, `script`,
`proximity` y una cola de diez plataformas con 1-3 entidades cada una)
necesita que Miquel aporte criterio (qué es "normal" para un
climatizador o un ESP32) y queda fuera de este feature a propósito.

**Investigación previa a especificar:**

1. **`mobile_app` (53 entidades)** — localización, batería, red y
   estado de kiosco de los iPhones de Miquel y Cécile y del MacBook Air.
   Mismo argumento que la regla de `entity_category` de 004: metadato
   personal variable, no una señal de salud de nada. A diferencia de
   `entity_category`, esta información **ya viaja en el `meta` de cada
   componente desde feature 001** (`sources.py::ha_entity_components()`
   ya guarda `platform`) — cero lectura nueva, una condición más en
   `is_intentional()`.
2. **`backup` (5 entidades)** — el propio sistema de copias de
   seguridad automáticas de Home Assistant (distinto de
   `backup_diario_nvme.sh`, que copia todo el homelab). Comprobado en
   vivo el 2026-08-09: la última copia correcta fue a las 03:04 UTC de
   hoy, la próxima está programada para mañana a las 02:51 UTC — cadencia
   diaria, mismo patrón que el resto de backups del homelab. El sensor
   `sensor.backup_ultima_copia_de_seguridad_automatica_realizada_
   correctamente` es un timestamp — exactamente el mismo tipo de dato
   que ya vigila `verify_backups.py` para el backup principal, con el
   mismo margen razonable (~30 h). No existe hoy ningún check de este
   tipo en `ha_monitor.py` (los actuales miran `state`/`entity_available`,
   no la antigüedad de un timestamp) — hace falta un tipo de check nuevo,
   mismo patrón de extensión que `requires_container` en feature 004.

**Alcance propuesto para este feature:**

| Pieza | Cuántas | Tratamiento |
|---|---|---|
| Entidades `platform: mobile_app` | 53 | Declarar "no aplica" — no son señales de salud |
| Backup automático de HA | 5 (o solo la de mayor señal: última copia correcta) | Declarar esperado: la última copia correcta tiene menos de ~30 h |

**Explícitamente fuera de alcance, pendiente de que Miquel aporte
criterio:**
- `melcloud` (12, climatizadores) y `esphome` (5, sal/toldos) — sensores
  físicos reales, pero "normal" depende de cada dispositivo.
- `tplink` (15, resto de sensores de los enchufes Tapo), `script` (10),
  `proximity` (7) y la cola de diez plataformas con 1-3 entidades cada
  una (~17) — baja urgencia o necesitan su propio criterio, no se tocan
  aquí para no repetir el error de tratar entidades distintas como un
  bloque.

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El inventario de cobertura marca 150 entidades de Home Assistant como
> brecha. De esas, 53 pertenecen a la app móvil de Home Assistant en el
> iPhone de Miquel, el de Cécile y el MacBook Air — localización, nivel
> de batería, red wifi, modo kiosco... — y no son señales de salud de
> nada, son metadatos personales que cambian todo el rato. Quiero que
> dejen de contar como brecha, igual que ya se hizo con las entidades de
> ajuste/diagnóstico. Además, Home Assistant tiene su propio sistema de
> copias de seguridad automáticas (distinto del backup diario del
> homelab), y hoy nadie vigila si esas copias se siguen haciendo — si
> dejaran de funcionar, no me enteraría hasta necesitar una copia y no
> encontrarla. Quiero que haya un aviso si la última copia correcta de
> Home Assistant tiene más de un día y medio. No incluye los
> climatizadores, los ESP32, el resto de sensores de los enchufes
> inteligentes, los scripts, ni el resto de entidades sin triar — esas
> quedan para un feature posterior, cuando decida qué es "normal" para
> cada una.

---

## Feature 006 — material de partida (2026-08-09)

> Nota de numeración: el triage de `entidad_ha` del commit `8e42e7d`
> también se llamó "feature 006" en su mensaje de commit, pero nunca
> tuvo directorio de spec propio — el numerado secuencial de Spec Kit
> asignó `006-central-alarmas` a este feature al ejecutar
> `/speckit-specify`. Esta sección se renombró de "Feature 007" a
> "Feature 006" para que la numeración de la prosa coincida con la del
> directorio real (`specs/006-central-alarmas/`), detectado como
> inconsistencia F4 en `/speckit-analyze` (2026-08-09).

**Redefinición de alcance, decidida hoy con Miquel.** El plan implícito tras
cerrar 001-006 era seguir con el Frente 2 del proyecto (`BRIEFING.md`, "Qué",
punto 2): el grafo de LangGraph que diagnostica y remedia. Miquel ha decidido
acotar el siguiente paso: **de momento, nada de remediación automática ni de
agente**. Este feature es solo el primer tramo de ese frente — detección y
explicación, sin ninguna acción ejecutada por el sistema. La lista cerrada de
acciones reversibles y el propio grafo (principios IV-VIII de la constitución)
quedan para un feature posterior, cuando exista algo que remediar de verdad
sobre lo que este feature deje construido.

**Investigación previa a especificar.** El Frente 1 (cobertura sistemática,
001-006) dejó cada pieza del homelab vigilada y llegando al dashboard
(Principio XII) — pero repartida en 6 pestañas distintas, cada una con su
propio formato de "esto está mal". Hoy no hay un sitio único que responda
"¿qué está roto ahora mismo, en todo el homelab?". Nueve orígenes ya calculan
una señal de alarma real, sin que este feature tenga que vigilar nada nuevo:

| Origen | Qué calcula ya | Pestaña actual |
|---|---|---|
| `docker_monitor_state.json` (vía `get_containers()`) | Contenedor caído o parado sin ser intencionado | Docker |
| `ha_monitor_state.json` (vía `get_ha_monitor()`) | 113 checks de Home Assistant, cada uno `ok`/no | Domótica |
| `inventario.json` (vía `get_inventory()`) | Brechas de cobertura (hoy 0, pero el mecanismo ya existe) | Inventario |
| `.backup-heartbeat` (vía `get_backup_heartbeat()`) | Backup diario atrasado (>25h) | Sistema (resumen) |
| Latidos de monitores (vía `get_monitor_heartbeats()`) | Un monitor dejó de ejecutarse, no solo de detectar | Automatización |
| `socat_relays.json` (vía `get_socat_relays()`) | Relay `socat` caído | Networking |
| `beszel_hosts.json` — hosts (vía `get_external_hosts()`) | Host externo (Kuma, AdGuard) caído o "sin evidencia" | Networking |
| `beszel_hosts.json` — hub (vía `get_beszel_hub_status()`) | El propio hub de Beszel dejó de reportar sobre todos sus sistemas | Networking |
| LaunchAgents (vía `get_launchagents()`) | Agente crasheado (`exit_code` ≠ 0, sin PID activo) | Automatización |
| Discos (vía `get_disks()`) | Uso ≥75%/≥90% | Sistema |

La pestaña "Alarmas" no añade vigilancia nueva: **unifica** lo que el Frente 1
ya dejó bien calculado. El trabajo real de este feature es otro: ninguno de
estos 9 orígenes trae hoy una explicación en prosa de qué significa el fallo
ni una remediación sugerida — eso es contenido nuevo, por *tipo* de alarma
(no por instancia; "contenedor caído" es un tipo, no 40), y es justo el tipo
de decisión que `clarify` tendrá que preguntar: ¿una remediación fija por
tipo basta, o algunos tipos necesitan variar el texto según el detalle
(por ejemplo, HA distingue ya `no_disponible` de `umbral`, ver el triage de
entidad_ha)? ¿qué se muestra para una alarma de un tipo todavía sin texto
escrito — se oculta, o se muestra en bruto con un aviso de "sin remediación
documentada todavía"?

**Alcance propuesto:**

| Pieza | Dentro / Fuera |
|---|---|
| Nueva pestaña "Alarmas" en el dashboard ya existente | Dentro |
| Agregar los 9 orígenes en una lista única, ordenada por severidad/antigüedad | Dentro |
| Por alarma: origen, componente, mensaje corto (ya existe en cada fuente) | Dentro |
| Por *tipo* de alarma: explicación en prosa de qué significa + remediación sugerida (texto plano, manual) | Dentro — el contenido nuevo real de este feature |
| Contador total visible (badge de la pestaña / resumen) | Dentro |
| Ejecutar cualquier remediación automáticamente | Fuera — Frente 2, pospuesto |
| Tocar la lógica de detección de los 9 orígenes | Fuera — ya está bien, no se toca lo que ya funciona |
| Deduplicación/agrupación más allá de lo que cada origen ya hace | Fuera, salvo que `clarify` revele que hace falta |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El homelab ya vigila casi todo (Frente 1 del proyecto, cerrado): 9 sistemas
> distintos calculan hoy si algo está mal — contenedores, Home Assistant,
> backups, relays, hosts externos, el propio hub de Beszel, agentes
> programados, discos y el inventario de cobertura. El problema es que esa
> información vive repartida en 6 pestañas del dashboard, cada una con su
> propio formato, y no hay ningún sitio que diga de un vistazo "esto es todo
> lo que está roto ahora mismo". Quiero una pestaña nueva, "Alarmas", que
> reúna en una sola lista cualquier alarma activa de cualquiera de esos 9
> orígenes, ordenada por gravedad. Cada alarma tiene que traer, además del
> dato en bruto que ya existe, una explicación en lenguaje sencillo de qué
> significa ese fallo y una sugerencia de cómo solucionarlo — en texto, para
> que yo decida y actúe, no algo que el sistema ejecute solo. No incluye
> ninguna corrección automática ni un agente que decida por su cuenta — eso
> es explícitamente para más adelante. Tampoco incluye vigilar nada que hoy
> no se vigile ya: esta pestaña muestra lo que los 9 sistemas existentes ya
> calculan, no añade una fuente de datos nueva.

---

## Feature 007 — material de partida (2026-08-09): primera pieza del Frente 2

Con el feature 006 cerrado (Central de Alarmas, 0 brechas, 10 orígenes
unificados), el Frente 1 del proyecto queda completo: todo lo que se
sabía vigilar de antemano ya se vigila, ya se explica y ya trae una
remediación sugerida. El Frente 2 — el agente que diagnostica causas
que **no** se sabían de antemano (principios IV, VIII, XI de la
constitución) — sigue en cero. Esta sección es el punto de partida
para el primer feature de ese frente.

**Por qué diagnóstico antes que remediación.** La constitución exige
diagnóstico previo a cualquier acción (Principio IV, NO NEGOCIABLE en
espíritu aunque el marcado formal esté en V/VI): no tiene sentido
diseñar la lista cerrada de acciones reversibles (Principios V, VI)
antes de tener ni un solo caso real donde el agente haya identificado
una causa con certeza suficiente para actuar sobre ella. Este feature
es exclusivamente diagnóstico — sin ejecutar nada, ni siquiera sugerir
texto de remediación nueva (eso ya lo cubre el feature 006 para las
causas que ya se conocían de antemano).

**El caso de prueba ya existe y ya tiene línea base.** Los 49
reinicios de `beszel` (Caso 1 de este briefing) son el banco de
pruebas natural: la investigación manual ya concluyó que 3 de los 5
episodios comprobados no tienen evidencia suficiente para diagnosticar
nada (`restart_history` no guarda más que la marca de tiempo). El
éxito de este feature en ese caso concreto **no es encontrar la
causa** — es llegar a la misma conclusión honesta ("no se puede
diagnosticar con esta evidencia") sin inventar una causa falsa por
presión de dar una respuesta, medido contra esa línea base (Principio
IX).

**Reproducibilidad diferida desde el diseño, no como añadido.**
Principio XI exige que toda conclusión se pueda reproducir ejecutando
el agente en diferido contra el mismo episodio histórico. Esto no es
negociable para *poder medir* el feature: sin ello, cada prueba exige
esperar a que algo se rompa de verdad. El agente debe poder recibir un
episodio de dos formas — en vivo (una alarma activa ahora mismo, del
feature 006) o en diferido (un episodio ya cerrado de
`restart_history`, con su ventana de `container_metrics`/`disk_metrics`
alrededor) — y producir la misma conclusión en ambos casos si los
datos de entrada son los mismos.

**Alcance propuesto:**

| Pieza | Dentro / Fuera |
|---|---|
| Recibir un episodio (vivo o histórico) y reunir evidencia real (`container_metrics`, `disk_metrics`, logs, estado de HA/relays según el origen) | Dentro |
| Formular varias hipótesis de causa probable con un LLM (DeepSeek) y contrastar cada una contra la evidencia reunida | Dentro |
| Cortacircuitos de gasto diario sobre las llamadas a DeepSeek — ver más abajo | Dentro |
| Registrar cada hipótesis con su comprobación y su desenlace (Principio VIII) — legible después, no solo en el momento | Dentro |
| Concluir "causa probable: X (evidencia: Y)" **o** "no se puede diagnosticar con la evidencia disponible" — nunca forzar una causa | Dentro |
| Validar contra el caso de beszel como banco de pruebas (sin perseguir su causa raíz como objetivo) | Dentro |
| Ejecutar cualquier acción correctiva, o sugerir una nueva (fuera de lo que el feature 006 ya sugiere de forma estática) | Fuera — Principios V/VI, feature posterior |
| Tocar contenedores críticos de cualquier forma, incluido analizarlos con intención de preparar una acción futura sobre ellos | Fuera |
| Una pestaña nueva en el dashboard | Fuera de este feature en concreto — primero hace falta que el mecanismo funcione y se pueda validar en diferido; la superficie visible (dónde se lee un diagnóstico) es una decisión de un feature posterior, una vez que haya diagnósticos reales que mostrar |
| RAG sobre el histórico de episodios ya resueltos, consultado antes de gastar tokens | Fuera — ver "Secuencia decidida" más abajo |

**Motor de hipótesis: decidido con Miquel el 2026-08-10.** De los tres
caminos que este documento dejaba abiertos (reglas fijas sin IA, LLM
local, LLM en la nube), la decisión es **DeepSeek** (LLM en la nube,
camino 3) — generar hipótesis abiertas sobre una causa que no se
conoce de antemano es exactamente el tipo de tarea donde un LLM
razona mejor que una tabla de reglas fijas (a diferencia del feature
006, catálogo cerrado de ~19 tipos, resuelto sin IA a propósito,
FR-015), y el modelo local ya tiene limitaciones documentadas en el
propio `CLAUDE.md` general del homelab para tareas de varios turnos.

Usar un LLM en la nube exige dos cosas explícitas por el Principio X
(Local por Defecto: "lo que salga de la máquina se justifica caso por
caso") y por el coste real de los tokens:

1. **Justificación de que salgan datos de diagnóstico**: la evidencia
   de un episodio (métricas, logs, estado de contenedores) viaja a la
   API de DeepSeek para que el modelo razone sobre ella — igual que ya
   hacen los crons complejos de Bautista (`dreaming`, `noticias-ia`,
   `gbrain-weekly-purge`) con DeepSeek, mismo proveedor y mismo
   principio de justificación ya aceptado para esos casos.
2. **Cortacircuitos de gasto diario** — mismo patrón que ya usa
   `docker_monitor.py` (3 reinicios en 6 h y para, con aviso), aplicado
   a €/día en vez de a reinicios: cada respuesta de la API de DeepSeek
   ya trae `usage.total_tokens` (prompt + completion por separado);
   sumar el coste real con el precio conocido del modelo y acumularlo
   en un registro diario. Al llegar al límite (a decidir en el plan;
   la cifra de partida que planteó Miquel es 5 €/día), el agente deja
   de invocar al LLM hasta el día siguiente y responde "no se puede
   diagnosticar sin gastar más del límite diario" en vez de forzar una
   llamada — nunca calcularlo contra la API de facturación de DeepSeek
   en tiempo real (más lento, más frágil, y no hace falta: el conteo
   local ya es exacto).

**Secuencia decidida — el RAG queda para un feature posterior.**
Miquel propuso además indexar el histórico de resoluciones ya
aprendidas (un RAG) para consultarlo antes de gastar tokens en una
llamada nueva — buena idea, pero prematura para este primer feature:
sin episodios diagnosticados todavía, no hay nada que indexar. La
secuencia acordada:

1. **Este feature**: DeepSeek + cortacircuitos de gasto diario, sin
   RAG. Validar contra beszel si el LLM aporta algo de verdad antes de
   construir nada más encima.
2. **Feature posterior**: con episodios reales ya resueltos y
   registrados (Principio VIII se encarga de que existan), un RAG
   sobre ese historial como capa de ahorro — reutilizando **GBrain**
   (ya desplegado en el homelab: embeddings + búsqueda híbrida, puerto
   3131) en vez de levantar un índice paralelo, mismo criterio de "no
   construir un mecanismo nuevo si ya hay uno sirviendo" que ha guiado
   todo el proyecto hasta ahora.

---

## Feature 008 — cerrada sin llegar a `/speckit-specify` (2026-08-11): deuda técnica pendiente

Este material se escribió para un feature `008-deuda-tecnica-pendiente`
con cuatro piezas de deuda técnica ya detectadas y documentadas, pero
nunca corregidas. Antes de escribir la descripción de partida para
`/speckit-specify`, se decidió con Miquel volver a correr
`/speckit-analyze` sobre `007-diagnostico-episodios` para recuperar la
cuarta pieza (5 hallazgos cuyo contenido nunca se había guardado). Esa
segunda pasada de análisis regeneró 6 hallazgos (U1-U3, I1-I2, C1) —
distintos en número y etiqueta de los 5 originales (C1-C3, F1, cuyo
contenido literal se dio por irrecuperable), pero cubriendo el mismo
terreno — y las correcciones resultantes cerraron, de paso, las otras
tres piezas de deuda que iban a ser el resto del alcance de este
feature. Al llegar al punto de escribir `/speckit-specify` no quedaba
ya nada que especificar: **este es un feature que se resolvió antes de
nacer**, no uno que se ejecutó fuera de proceso.

| Deuda original | Cómo se cerró |
|---|---|
| Fuga de IP LAN real en `specs/005-movil-y-backup-ha/quickstart.md` | Corregida — sustituida por `$HA_URL` (variable ya existente para `ha_monitor.py`), en vez de hardcodear la IP |
| Ambigüedad de "confirmada" en el prompt de DeepSeek (007) | Resuelta con hallazgo **I2**: el parser solo rechazaba el caso vacío, no dos o más `confirmada` a la vez pese a que el propio prompt exige exactamente una — corregido en `deepseek.py`, con test nuevo, y la ambigüedad documentada como decisión de diseño en `research.md` §2 (**U3**) |
| Varianza entre dos diagnósticos del mismo episodio (0 vs 3 hipótesis) | Resuelta con hallazgos **U1/I1**: `spec.md`/`research.md` exigían reproducibilidad del "desenlace de cada hipótesis", más estricto que lo que la validación real (T030) pudo sostener contra un LLM en la nube — redefinido para exigir y medir solo `conclusion_tipo`, con la varianza de hipótesis documentada como comportamiento aceptado |
| 5 hallazgos de `/speckit-analyze` de 007 (C1-C3, F1), contenido irrecuperable | Sustituidos por los 6 de la nueva pasada (**U1-U3, I1-I2, C1**), todos resueltos — ver `specs/007-diagnostico-episodios/tasks.md`, Fase 7 (T034-T037) |

**Hallazgo adicional, fuera de la lista original.** Al sanear la fuga de
IP de `specs/005`, una búsqueda del mismo patrón (`192.168.`) en todo el
repo encontró una segunda fuga no catalogada: los relays de Frigate en
la sección "Feature 004" de este mismo `BRIEFING.md` citaban
`192.168.4.87:5540/5541` en vez de `homelab.amsterdam9.home` — corregida
también.

**Nota de método.** Esta sesión completa (re-análisis de 007 +
correcciones + esta nota) la ejecutó Claude de principio a fin, a
petición explícita de Miquel ("lo ejecutas tú esta vez" /
"hazlo tú mismo") — rompe a propósito la regla de `METODO.md` de que
Miquel ejecuta los comandos de Spec Kit. Ver `BITACORA.md` para el
registro completo.

---

## Feature 008 — material de partida (2026-08-11): superficie del diagnóstico en el dashboard

Con 007 cerrado y endurecido (sesión de arriba), el mecanismo de
diagnóstico funciona pero solo se puede leer por CLI (`mostrar
EPISODIO_ID`) — exactamente lo que `spec.md` de 007 dejó fuera a
propósito en sus Assumptions: *"la superficie visible de un
diagnóstico... queda fuera de este feature — se decide en uno
posterior, una vez que haya diagnósticos reales que mostrar"*. Ya los
hay: hoy `diagnostico.db` tiene 8 episodios, 16 diagnósticos y 26
hipótesis reales (todos de la validación de `beszel` + un caso de
`homeassistant` crítico) — pocos, pero reales, no un mock.

**Lo que ya existe y no hay que construir.** `diagnostico.db` vive en
`docker/homelab-orchestrator/data/`, la misma carpeta que
`inventario.db`/`homelab.db`, que ya está montada en el contenedor del
dashboard en `/data` (`docker-compose.yml` de `homelab-dashboard`) —
sin volumen nuevo que añadir. `app.py` ya sabe leer SQLite de solo
lectura (`mode=ro`, ver el patrón de `speedtest.db`) para otra base de
ese mismo directorio; sería el segundo caso, no el primero.

**Dato real a tener en cuenta al diseñar.** Los 16 diagnósticos
existentes son **todos** `no_diagnosticable` — ningún `causa_probable`
real todavía. Cualquier vista debe poder mostrar bien las dos
conclusiones aunque solo una tenga datos reales hoy; no diseñar
mirando solo la muestra disponible.

**Decidido con Miquel (2026-08-11), las dos preguntas que este material
dejaba abiertas:**

1. **Solo visor de lectura, sin disparador.** Nada de botón en el
   dashboard que llame a `diagnosticar` — eso sigue siendo solo por
   línea de comandos. El dashboard sigue siendo, como hasta ahora, de
   solo lectura sobre ficheros/bases que otro proceso ya escribió;
   este feature no le añade la primera acción que ejecuta código de
   otro paquete ni gasta dinero en una API externa por un clic.
2. **Cuelga de la pestaña "Correcciones" ya existente** (feature 006),
   no una pestaña nueva — cuando una alarma de esa pestaña tenga un
   episodio diagnosticado asociado, se muestra su diagnóstico como
   detalle. Acopla dos features hasta ahora independientes
   (`alarm_history.json` no sabe nada de `diagnostico.db`) — el cómo
   se resuelve ese acoplamiento (¿por contenedor+ventana de tiempo?
   ¿un campo nuevo en algún sitio?) es trabajo real de `/speckit-plan`,
   no algo que este material deba resolver.

**Alcance propuesto:**

| Pieza | Dentro / Fuera |
|---|---|
| Leer `diagnostico.db` (episodios, diagnósticos, hipótesis) desde `app.py` | Dentro |
| Mostrar, por episodio, su conclusión y el detalle de cada hipótesis (descripción, comprobación, desenlace) | Dentro |
| Mostrar el acumulado de gasto diario de DeepSeek (`gasto_diario`) | Dentro — visibilidad del cortacircuitos de FR-010, no solo su existencia |
| Colgarlo de la pestaña "Correcciones" ya existente (feature 006), no una pestaña nueva | Dentro |
| Disparar un diagnóstico nuevo desde el dashboard (botón "diagnosticar") | Fuera — solo visor de lectura, decidido con Miquel |
| Cambiar cómo `diagnostico.cli` congela o diagnostica episodios | Fuera — este feature es de lectura, no toca 007 |
| Generalizar a las otras 9 alarmas de la Central de Alarmas | Fuera — sigue acotado a contenedores, mismo alcance que 007 |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios de contenedor (feature 007) ya
> funciona y ya tiene diagnósticos reales guardados, pero solo se
> pueden leer por línea de comandos — no hay ningún sitio en el
> dashboard del homelab donde ver qué se ha diagnosticado. Quiero que
> la pestaña "Correcciones" que ya existe en el dashboard (feature 006,
> unifica las alarmas activas del homelab) muestre, para una alarma de
> contenedor que ya tenga un episodio diagnosticado asociado, su
> conclusión (una causa probable con evidencia, o que no se pudo
> diagnosticar) y el detalle de cada hipótesis que se consideró — qué
> se propuso, cómo se contrastó, y en qué quedó. También quiero ver
> cuánto llevo gastado hoy en el presupuesto de DeepSeek. Es solo un
> visor de solo lectura: no incluye poder lanzar un diagnóstico nuevo
> desde el navegador, eso sigue siendo solo por línea de comandos. No
> incluye diagnosticar nada que no sean contenedores, ni una pestaña
> nueva en el dashboard.

---

## Feature 009 — material de partida (2026-08-11): generalizar el diagnóstico a discos

Con 007 (motor de diagnóstico) y 008 (visor en Alarmas) cerrados, el
siguiente paso del Frente 2 es generalizar el diagnóstico más allá de
contenedores — el propio `spec.md` de 007 lo dejó explícitamente
acotado a un solo origen (Clarification 1) "para poder validar el
enfoque antes de generalizar".

**Investigación previa — por qué discos y no los otros 8.** Antes de
elegir, se comprobó qué orígenes de la Central de Alarmas (feature 006)
tienen datos históricos reales en `homelab.db`, no solo el estado
actual:

| Origen | ¿Tabla de series temporales en `homelab.db`? |
|---|---|
| Contenedores | Sí — `container_metrics` (30 días) + `container_metrics_hourly` (permanente). Ya usado por 007. |
| **Discos** | **Sí** — `disk_metrics` (13.992 filas reales, ~5 min de cadencia) + `disk_metrics_daily` (pensada como agregado permanente, pero **vacía hoy** — el job de agregación no la está rellenando, sin investigar por qué). |
| HA, backup, monitores, relays, hosts externos, hub de Beszel, agentes, inventario | **No.** Ninguna tabla propia — solo el fichero de estado actual (que se sobrescribe en cada ciclo) más el registro fino de `alarm_history.json` (feature 006: cuándo empezó y acabó cada alarma, sin ningún detalle intermedio). |

Generalizar a los otros 7 de golpe habría significado tratar orígenes
con evidencia real y orígenes con evidencia casi vacía como si fueran
equivalentes — el mismo error que los features 004/005 ya evitaron
explícitamente ("tratar entidades distintas como un bloque"). Discos es
el único segundo candidato con datos comparables a los de contenedores.
Decidido con Miquel: empezar por discos; los otros 7 quedan para
features posteriores, uno a uno, cuando cada uno tenga su propia
investigación de qué constituye evidencia real.

**Segundo hallazgo: no hay ningún incidente real de disco que usar como
línea base.** El caso de prueba de 007 fueron los 49 reinicios reales de
`beszel`. Para discos, `alarm_history.json` tiene **0** alarmas de
origen `discos` ya resueltas — los tres discos del homelab llevan tiempo
por debajo del umbral de aviso (75%) de forma continuada (comprobado en
vivo: 14,6% / 17,0% / 61,9% de uso). A diferencia de 007, este feature
**no tiene un FR-011 equivalente que exigir** ("debe coincidir con la
conclusión de una investigación manual ya hecha") — no existe esa
investigación manual porque no ha habido ningún incidente real de disco
todavía. La validación tendrá que apoyarse en `congelar --vivo` contra
el estado sano actual (como ya hizo 007 con `homeassistant` sano,
Escenario 4 de su quickstart) y, si aparece un aviso real de disco
mientras se desarrolla este feature, usarlo como caso real.

**Lo que esto exige cambiar de la arquitectura de 007 (para
`/speckit-plan`, no para el spec).** `Episodio.contenedor` es un campo
obligatorio hoy, usado por `evidencia.py` (`docker inspect`/`logs`,
`container_metrics`), por `es_critico()` (`docker_critical()`), y por
el propio contrato del CLI (`congelar --historico/--vivo CONTENEDOR`).
Generalizar a un segundo origen implica que el modelo deje de asumir
"todo episodio es de un contenedor" — un cambio de diseño real, no solo
código nuevo añadido al lado. Igual de importante: el prompt a DeepSeek
(`_PROMPT_INSTRUCCIONES` de `deepseek.py`) habla explícitamente de
"reinicio del contenedor" y "episodios de contenedores Docker" — tendrá
que dejar de asumir ese lenguaje sin perder la claridad que le costó
conseguir a 007 (la ambigüedad de "confirmada", ver `BITACORA.md`).

**Alcance propuesto:**

| Pieza | Dentro / Fuera |
|---|---|
| Generalizar `Episodio` (y el resto del modelo) para que un episodio pueda ser de un disco, no solo de un contenedor | Dentro |
| Evidencia de un episodio de disco: `disk_metrics` alrededor del momento, mismo criterio de tolerancia que ya usa `disk_metrics_near()` | Dentro |
| Ajustar el prompt de DeepSeek para que no asuma "contenedor" como único tipo de episodio | Dentro |
| Validar contra `congelar --vivo` de los 3 discos reales en su estado sano actual (no hay incidente histórico que usar) | Dentro |
| Generalizar a los otros 7 orígenes (HA, backup, monitores, relays, hosts externos, hub de Beszel, agentes, inventario) | Fuera — cada uno necesita su propia investigación de qué es "evidencia real" para él, igual que se acaba de hacer aquí para discos |
| Cualquier acción correctiva sobre el disco (liberar espacio, etc.) | Fuera — sigue siendo solo diagnóstico, mismo alcance que 007 |
| Mostrar el diagnóstico de un disco en el dashboard (equivalente a 008) | Fuera de este feature — primero el mecanismo, después la superficie, mismo orden que 007→008 |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (feature 007) hoy solo sabe
> diagnosticar contenedores caídos — se limitó a propósito a un solo
> origen para validar el enfoque antes de generalizar. Quiero que
> también pueda diagnosticar episodios de disco: cuando un disco cruza
> el umbral de aviso o crítico de uso, quiero poder pedirle al motor
> que reúna la evidencia real alrededor de ese momento (uso del disco
> en la ventana de tiempo relevante) y formule hipótesis de causa
> probable, con el mismo rigor y las mismas garantías que ya tiene para
> contenedores: varias hipótesis contrastadas, nunca inventar una causa
> sin evidencia, un límite de gasto diario compartido con el resto del
> motor. No incluye generalizar a ningún otro origen de la Central de
> Alarmas (Home Assistant, backups, relays, hosts externos, el hub de
> Beszel, agentes, inventario de cobertura) — eso queda para features
> posteriores, uno a uno. No incluye ninguna acción correctiva sobre el
> disco, ni mostrar este diagnóstico nuevo en el dashboard — sigue
> siendo solo por línea de comandos, mismo alcance que tuvo 007 antes
> de que 008 le diera superficie visible.

---

## Feature 010 — material de partida (2026-08-12): generalizar el diagnóstico a Home Assistant

Con 007 (motor), 008 (visor) y 009 (discos) cerrados, toca elegir el
tercer origen a generalizar de los 7 que quedaban fuera de 009 (HA,
backup, monitores, relays, hosts externos, hub de Beszel, agentes,
inventario). Se investiga HA primero.

**Por qué HA ahora y no antes.** La tabla de 009 decía que HA no tenía
"ninguna tabla propia" de series temporales, solo el fichero de estado
actual (se sobrescribe cada ciclo) más el registro grueso de
`alarm_history.json`. Eso ha cambiado esta misma sesión: al investigar
y corregir la corrupción repetida del recorder de HA (bind mount +
WAL de SQLite sobre OrbStack, 3 corrupciones reales entre abril y
agosto), el recorder se movió a un volumen Docker nativo
(`ha_recorder_db`) y se le añadió un check de monitorización nuevo
(`ha_recorder_corrupto` en `ha_monitor.py`). Consecuencia directa para
este feature: **el propio recorder de HA es una fuente de series
temporales reales, por entidad**, comprobado en vivo justo ahora — solo
en los ~14 min desde el último reinicio del contenedor ya había 1.583
filas en `states` (`event_data`, `event_types`, `states_meta`,
`statistics`, `statistics_short_term` completan el esquema). Es más
fina que `container_metrics` (cadencia de 5 min): un estado nuevo por
cada cambio real de cualquier entidad. **Con una condición**: solo es
fiable desde el 2026-08-11 (fecha del fix); antes de eso el recorder se
corrompía y se reiniciaba solo periódicamente, así que la profundidad
histórica hacia atrás es irregular por diseño, no un bug de este
feature.

**Segundo hallazgo, corregido tras una comprobación en vivo (2026-08-12):
`alarm_history.json` NO tiene ningún incidente real de recorder
corrupto que usar como línea base.** La primera versión de este
material daba por bueno un registro "Resuelta | Recorder de Home
Assistant (SQLite)" en `alarm_history.json` como si fuera un incidente
real equivalente a `beszel` en 007. No lo era: al revisar sus
timestamps (`aparecio_en`/`resuelta_en`, 13 segundos de diferencia)
quedó claro que era un artefacto de la prueba de integración de ayer —
inyecté un estado falso para comprobar que el dashboard clasificaba
bien la alarma, lo restauré segundos después, y esa transición se
grabó como si fuera una alarma real. **Se ha eliminado de
`alarm_history.json`** (dato de producción, no debía quedar un
incidente fabricado en el historial). Del origen `ha`, lo que queda
tras la limpieza:

| Estado | Componente | Naturaleza |
|---|---|---|
| Resuelta | Desbloqueo Cerradura | Cerradura Nuki — dispositivo físico |
| Resuelta | Bloqueo Cerradura | Cerradura Nuki — dispositivo físico |
| Activa | Batería crítica cerradura Amsterdam 9 | Cerradura Nuki — investigado esta sesión, concluido hardware/batería del dispositivo, fuera del control del homelab, cerrado explícitamente ("Dejemos el tema de la cerradura") |
| Activa | Batería cerradura Amsterdam 9 | Igual que la anterior |
| Activa | Cerradura Amsterdam 9 | Igual que la anterior |

Es decir: **los 5 incidentes reales de origen `ha` son todos la misma
cerradura**, con causa ya investigada a mano y no corregible desde el
homelab. A diferencia de 009 (que al menos tenía `disk_metrics` con
13.992 filas reales aunque sin ningún incidente que analizar), aquí
**tampoco hay un equivalente a `restart_history` para el check
`ha_recorder_corrupto`** — es un check nuevo (de ayer), las 3
corrupciones reales conocidas (20 abr, 9 y 11 ago) ocurrieron antes de
que existiera, y no dejaron ningún registro con timestamp reutilizable.
La validación de línea base de este feature queda, por tanto, más
limitada que la de 007 (que sí tuvo 49 reinicios reales de `beszel`):
solo `congelar --vivo` contra el estado sano actual de cada tipo de
check, más lo que aparezca de verdad mientras se desarrolla — mismo
tipo de limitación que 009 ya aceptó para discos, documentada en vez de
inventar un caso sintético que aparente ser real.

**Lo que esto exige cambiar de la arquitectura de 009 (para
`/speckit-plan`, no para el spec).** Menos que en 009: `Episodio` ya
tiene `origen` como campo genérico (`"contenedor"` / `"disco"` hoy);
añadir `"ha"` es un valor nuevo, no un rediseño del modelo. Lo que sí
hace falta construir de cero es la evidencia — no hay
`disk_metrics_near()` equivalente para HA todavía. La evidencia de un
episodio de HA tendría que salir de dos sitios distintos según el tipo
de comprobación que falló: (a) para checks sobre una entidad concreta
(batería, disponibilidad), consultar el `states` del recorder filtrado
por `entity_id` y ventana de tiempo, igual patrón que
`disk_metrics_window()` pero contra una base distinta a `homelab.db`;
(b) para el check `ha_recorder_corrupto` en sí, no hay serie temporal
que consultar — la evidencia es el propio fichero `.corrupt.*` y los
logs del contenedor, más parecido a `docker_logs_tail()` que a una
consulta de métricas.

**Alcance propuesto (a confirmar en `/speckit-clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Generalizar `Episodio.origen` para admitir `"ha"` | Dentro |
| Evidencia por entidad: consultar `states` del recorder de HA alrededor del momento del episodio | Dentro |
| Evidencia para `ha_recorder_corrupto`: ficheros `.corrupt.*` + logs del contenedor `homeassistant` | Dentro |
| Validar con `congelar --vivo` contra el estado sano actual de cada tipo de check (entidad y recorder), y contra cualquier episodio real de cualquiera de los dos tipos que aparezca mientras se desarrolla | Dentro — sin línea base histórica equivalente a `beszel`, ver hallazgo corregido arriba |
| Diagnosticar los episodios de la cerradura (batería/conectividad) | **Fuera.** Decidido con Miquel (2026-08-12): la causa ya se investigó a mano esta sesión y es hardware/batería de un dispositivo físico (Nuki), no infraestructura del homelab — no aporta nada nuevo validar el motor contra un caso ya resuelto sin él |
| Generalizar a los otros 6 orígenes restantes (backup, monitores, relays, hosts externos, hub de Beszel, agentes, inventario) | Fuera — uno a uno, misma razón que 009 |
| Cualquier acción correctiva sobre HA o la cerradura | Fuera — sigue siendo solo diagnóstico |
| Mostrar el diagnóstico de HA en el dashboard | Fuera de este feature — mecanismo primero, superficie después, mismo orden que 007→008 |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (feature 007, generalizado a
> discos en 009) hoy no sabe diagnosticar nada de Home Assistant.
> Quiero que también pueda diagnosticar episodios de HA: cuando un
> check de `ha_monitor.py` sobre una entidad falla (batería, entidad
> no disponible, estado inesperado) o cuando falla el check del
> recorder de HA corrupto, quiero poder pedirle al motor que reúna la
> evidencia real alrededor de ese momento — para checks de entidad, el
> historial de esa entidad en el recorder de Home Assistant; para el
> recorder corrupto, los ficheros de corrupción y los logs del
> contenedor — y formule hipótesis de causa probable, con el mismo
> rigor que ya tiene para contenedores y discos: varias hipótesis
> contrastadas, nunca inventar una causa sin evidencia, el mismo límite
> de gasto diario compartido con el resto del motor. No existe hoy
> ningún incidente histórico real de ninguno de los dos tipos de check
> que usar como línea base (a diferencia de los 49 reinicios de
> `beszel` en 007) — la validación se apoya en `congelar --vivo` contra
> el estado sano actual de cada tipo, y contra cualquier episodio real
> que aparezca mientras se desarrolla. No incluye diagnosticar los
> episodios de la cerradura de la puerta (batería/conectividad): su
> causa ya se investigó a mano esta sesión y es un problema del
> dispositivo físico, no del homelab, así que no hay nada nuevo que
> validar ahí. No incluye generalizar a ningún otro origen de la
> Central de Alarmas (backups, relays, hosts externos, el hub de
> Beszel, agentes, inventario de cobertura) — eso queda para features
> posteriores, uno a uno. No incluye ninguna acción correctiva sobre
> HA, ni mostrar este diagnóstico nuevo en el dashboard — sigue siendo
> solo por línea de comandos, mismo alcance que tuvo 007 antes de que
> 008 le diera superficie visible.

## Feature 011 — material de partida (2026-08-12): generalizar el diagnóstico a los backups

Con 007 (motor), 008 (visor), 009 (discos) y 010 (HA) cerrados, toca el
cuarto origen de los 9 de la Central de Alarmas: **backups**. El nombre
de la feature debe llevar "backups" explícito (`011-diagnostico-backups`,
mismo patrón que `009-diagnostico-discos`/`010-diagnostico-ha`) — pedido
directo de Miquel, para tenerlo como referente.

**Investigación previa a especificar — qué evidencia real existe.**
A diferencia de HA (API + historial por entidad) y de discos (tabla
SQL), aquí no hay ni tabla en `homelab.db` ni ningún JSON histórico:
comprobado en vivo, `homelab.db` solo tiene tablas de contenedores y
discos, y `heartbeat.read('verify-backups')` solo da el último
resultado (`"12/12 checks OK"`), nunca un historial. La única fuente de
evidencia real es texto libre:

- `backup_diario_nvme.sh` escribe un log completo por ejecución
  (`/Volumes/FastData/homelab/logs/backup_YYYY-MM-DD_HH-MM-SS.log`):
  estado de cada dump de BD (Vaultwarden, Jellyfin ×2, Beszel, n8n,
  Audiobookshelf, MariaDB, PostgreSQL Immich/GBrain), la salida
  completa de `rsync --itemize-changes`, y una línea `RESUMEN FINAL`
  con la duración y el código de rsync **ya interpretado por el propio
  script** (`0`/`24` = ok, `23` = parcial con riesgo de huérfanos —
  mismo bug que el `sudo` del 2026-07-27 ya documentado en el
  `CLAUDE.md` general, `10` = fallo).
- **Retención: solo 7 días** (`RETENTION_DAYS=7`), no 30 como
  `container_metrics`/`disk_metrics` — condiciona directamente cuánto
  se puede mirar hacia atrás en diferido. Hoy hay 8 logs reales en
  disco (5–12 de agosto), todos limpios.
- Sin línea base real disponible: los 8 logs retenidos son todos
  éxitos — mismo criterio ya aceptado por 009/010. El incidente real
  conocido (huérfanos root del 2026-07-27) ya cayó fuera de la ventana
  de 7 días — no hay log real de aquel episodio que recuperar.
- Corrección menor de paso: el `CLAUDE.md` general dice "13 checks" de
  `verify_backups.py`; comprobado en vivo son **12** (10 ficheros del
  catálogo + heartbeat + log de backup) — se anota aquí, no se toca el
  documento general en este feature.

**Pregunta ya resuelta durante la investigación — backups de Home
Assistant.** Miquel preguntó si había que añadir aquí los backups
automáticos de HA. Son dos cosas distintas, comprobadas ambas en vivo:

1. **Que HA siga generando copias nuevas** — ya lo vigila el check
   `ha_backup_reciente` de `ha_monitor.py` (`entity_age_below`,
   `max_age_s=129600`), y ya es diagnosticable hoy: es exactamente el
   check validado en vivo con 010 (episodio 22). Nada que añadir aquí.
2. **Que esas copias sobrevivan al backup nocturno** — comprobado que
   `docker/homeassistant/backups/` **no está excluido** del rsync
   principal (solo se excluye `zigbee2mqtt/data/log` de esa carpeta);
   los tres backups automáticos reales de HA (9, 10 y 11 de agosto,
   172–250 MB) se copian igual que cualquier otro fichero de FastData.
   Entra sin tratamiento especial en el alcance ya previsto de este
   feature — diagnosticar "¿tuvo éxito el rsync de anoche?" cubre a HA
   exactamente igual que a cualquier otro dato bajo `/Volumes/FastData/`.

Matiz real anotado, no propuesto como trabajo de este feature:
`verify_backups.py` verifica una lista curada de ~12 elementos, pero no
comprueba específicamente que el tar de HA (ni el de ningún otro dato
fuera del catálogo) haya llegado — solo el éxito global del rsync.
Ampliar ese catálogo sería vigilar más cosas nuevas, no diagnosticar;
fuera de alcance aquí.

**Diferencia real respecto a HA/discos, con consecuencia en el
diseño.** La evidencia no es una tabla ni una API — es texto libre por
ejecución. "Congelar" aquí significa parsear un log, no hacer un
`SELECT` ni una llamada REST. Y "diferido" solo tiene sentido dentro de
los 7 días retenidos — pasada esa ventana, no hay nada que congelar,
ni siquiera con `--historico`.

**Alcance propuesto (borrador, para que Miquel decida en `clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Diagnosticar en vivo el log de backup más reciente | Dentro |
| Diagnosticar en diferido cualquier log dentro de los 7 días retenidos | Dentro |
| Evidencia: parsear el log de texto (estado por dump de BD, código de rsync interpretado, duración) | Dentro |
| Backups de HA (frescura de sus propias copias, o que sobrevivan al rsync) | Ya cubierto — ver arriba, nada nuevo aquí |
| Tocar `backup_diario_nvme.sh` de cualquier forma, ejecutar un backup nuevo, cualquier acción sobre `/Volumes/Storage/backup/` | Fuera — solo diagnóstico |
| Ampliar el catálogo de `verify_backups.py` a más rutas | Fuera — es vigilancia nueva, no diagnóstico |
| Generalizar a los 5 orígenes restantes (relays, hosts externos, hub de Beszel, agentes, inventario) | Fuera — uno a uno, misma razón que 009/010 |
| Mostrar el diagnóstico de backups en el dashboard | Fuera de este feature — mecanismo primero, superficie después, mismo orden que 007→008 |
| **Por decidir en `clarify`**: ¿se diagnostican los ~12 checks de `verify_backups.py` como unidades individuales (como los checks de HA), o el log completo de una noche como una sola unidad? A diferencia de HA, aquí no hay "checks" con `id` propio — es un log narrativo de una sola ejecución. | Abierto |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (feature 007, generalizado a
> discos en 009 y a Home Assistant en 010) hoy no sabe diagnosticar
> nada de los **backups** del homelab. Quiero que también pueda
> diagnosticar episodios de backup: cuando el rsync nocturno
> (`backup_diario_nvme.sh`) falla o queda parcial, o cuando algún dump
> de base de datos del catálogo de `verify_backups.py` falla o queda
> atrasado, quiero poder pedirle al motor que reúna la evidencia real
> de esa ejecución — el log completo de esa noche, con el estado de
> cada dump y el código de rsync ya interpretado — y formule hipótesis
> de causa probable, con el mismo rigor que ya tiene para contenedores,
> discos y HA: varias hipótesis contrastadas, nunca inventar una causa
> sin evidencia, el mismo límite de gasto diario compartido con el
> resto del motor. A diferencia de HA y discos, aquí la evidencia es
> texto libre (un log por ejecución), no una tabla ni una API, y la
> retención es de solo 7 días — el diagnóstico en diferido solo puede
> mirar dentro de esa ventana. No existe hoy ningún incidente real
> dentro de esos 7 días que usar como línea base — los 8 logs
> retenidos están todos limpios; el incidente real conocido (huérfanos
> root del 27-07) ya cayó fuera de la ventana de retención — la
> validación se apoya en `congelar --vivo` contra el estado sano actual
> y contra cualquier fallo real que aparezca mientras se desarrolla. No
> incluye los backups automáticos de Home Assistant como caso aparte:
> su frescura ya la diagnostica el feature 010 (`ha_backup_reciente`),
> y que sobrevivan al rsync ya lo cubre este mismo mecanismo sin
> tratamiento especial. No incluye ejecutar ningún backup nuevo, tocar
> `backup_diario_nvme.sh`, ni ninguna acción sobre
> `/Volumes/Storage/backup/`. No incluye generalizar a ningún otro
> origen de la Central de Alarmas (relays, hosts externos, el hub de
> Beszel, agentes, inventario de cobertura) — eso queda para features
> posteriores, uno a uno. No incluye ninguna acción correctiva, ni
> mostrar este diagnóstico nuevo en el dashboard — sigue siendo solo
> por línea de comandos, mismo alcance que tuvo 007 antes de que 008 le
> diera superficie visible.

---

## Feature 012 — material de partida (2026-08-12): generalizar el diagnóstico a los relays

Con 007 (motor), 008 (visor), 009 (discos), 010 (HA) y 011 (backups)
cerrados, toca el quinto origen de los 9 de la Central de Alarmas:
**relays** (`012-diagnostico-relays`, nombre explícito pedido para
seguir la misma convención que 009/010/011).

**Investigación previa a especificar — un origen con forma nueva**: a
diferencia de discos/HA/backups, aquí **sí existe una línea base real**
(Principio IX) — pero con una limitación real distinta a cualquiera de
los tres orígenes anteriores, no la ya conocida "sin línea base".

- `dump_socat_status.py` (LaunchAgent `amsterdam9.dashboard.socat`,
  cada 5 min) comprueba 10 relays `socat` (Traefik LAN/loopback/
  OrbStack, HA Shelly/Broadlink, Beszel AdGuard/Kuma, Kuma UI, Frigate
  cocina/salón) y sobreescribe `socat_relays.json` — estado **actual**
  con detalle real por relay (`name`, `desc`, `ok`), mismo patrón que
  `ha_monitor_state.json` antes del fix de HA.
- Su `StandardOutPath` (`~/Library/Logs/dashboard-socat.log`) **no
  tiene ninguna rotación** — guarda histórico real desde el
  2026-04-29, 29.834 líneas. Comprobado en vivo: **17 episodios de
  fallo reales**, agrupando fallos consecutivos — desde parpadeos de
  un solo ciclo hasta una caída sostenida de **~10 horas el
  2026-05-24** (03:34–13:29). Primera vez en este proyecto con línea
  base real desde el arranque, sin la salvedad que necesitaron 009,
  010 y 011.
- **La limitación real**: el log solo guarda el recuento agregado
  ("4/5 ok") cada 5 minutos — el detalle de *qué relay concreto* falló
  en cada uno de esos 17 episodios se perdió, porque
  `socat_relays.json` (el único sitio con detalle por relay) se
  sobreescribe cada ciclo sin archivar nunca la versión anterior.
- **Decidido con Miquel (2026-08-12)**: en vivo, evidencia con detalle
  real por relay (`socat_relays.json`, estado actual). En diferido,
  evidencia agregada del log ("N de M caídos, durante X minutos") —
  el motor dice honestamente que no sabe cuál si se le pregunta, en
  vez de adivinar. Aprovecha los 17 episodios reales sin inventar una
  resolución que no existe.
- **Consecuencia en el CLI**: asimetría real entre los dos modos —
  `--relay-vivo NOMBRE` (como `--ha-vivo CHECK_ID`, un relay concreto)
  pero `--relay-historico MOMENTO_ISO` sin nombre de relay (como
  `--backup-historico`, porque en diferido no hay ningún relay
  concreto que nombrar).
- **Hallazgo aparte, fuera de alcance de este feature**: `~/Library/
  LaunchAgents/` tiene muchos más relays `socat` reales (HEOS, Marantz
  ×3, ESPHome sal/toldos, Android TV ×2, Tapo ×3...) que
  `dump_socat_status.py` **no vigila** — un hueco de cobertura real
  (Frente 1, Principio XIII), no de diagnóstico. Se anota aquí para no
  perderlo, pero ampliar la vigilancia no es diagnosticar lo que ya se
  vigila — queda fuera, igual que el catálogo de `verify_backups.py`
  quedó fuera en 011.

**Alcance propuesto (borrador, para que Miquel decida en `clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Diagnosticar en vivo un relay concreto, con su estado real actual | Dentro |
| Diagnosticar en diferido un momento pasado, con evidencia agregada (no por relay) | Dentro |
| Validar contra los 17 episodios reales ya identificados (sin línea base "aceptada como limitación", por primera vez en este proyecto) | Dentro |
| Recuperar el detalle por relay de episodios históricos ya ocurridos | Fuera — esa información no existe, no se puede inventar |
| Ampliar `dump_socat_status.py` a los relays de HA que hoy no vigila | Fuera — es vigilancia nueva (Frente 1), no diagnóstico |
| Cualquier acción correctiva sobre un relay o su LaunchAgent | Fuera — solo diagnóstico |
| Generalizar a los 4 orígenes restantes (hosts externos, hub de Beszel, agentes, inventario) | Fuera — uno a uno, misma razón que 009/010/011 |
| Mostrar el diagnóstico de relays en el dashboard | Fuera de este feature — mecanismo primero, superficie después |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (feature 007, generalizado a
> discos en 009, a Home Assistant en 010 y a backups en 011) hoy no
> sabe diagnosticar nada de los **relays** `socat` del homelab. Quiero
> que también pueda diagnosticar episodios de relay: en vivo, cuando
> un relay concreto (de los 10 que vigila `dump_socat_status.py`) está
> caído ahora mismo, reuniendo su estado real de `socat_relays.json`
> (nombre, descripción, si responde); en diferido, señalando un
> momento pasado dentro del histórico real (`dashboard-socat.log`, sin
> rotación, con datos desde el 29 de abril), reuniendo la evidencia
> agregada de esa ventana — cuántos de los relays vigilados estaban
> caídos y durante cuánto tiempo, sin poder decir cuál concretamente,
> porque ese detalle no se archivó nunca. Quiero que formule hipótesis
> de causa probable con el mismo rigor que ya tiene para los demás
> orígenes: varias hipótesis contrastadas, nunca inventar una causa ni
> inventar qué relay concreto falló cuando esa información no existe,
> el mismo límite de gasto diario compartido con el resto del motor. A
> diferencia de discos, HA y backups, aquí sí existe una línea base
> real desde el arranque del feature: 17 episodios de fallo reales
> desde el 29 de abril, agrupando fallos consecutivos del log agregado,
> incluida una caída sostenida de unas 10 horas el 24 de mayo. No
> incluye recuperar qué relay concreto falló en un episodio ya pasado
> — esa información no se archivó y no se puede reconstruir. No
> incluye ampliar la vigilancia a los relays de Home Assistant que
> `dump_socat_status.py` no comprueba hoy (HEOS, Marantz, ESPHome,
> Android TV, Tapo) — eso es cobertura nueva, no diagnóstico, y queda
> fuera de este feature. No incluye ninguna acción correctiva sobre
> ningún relay ni su LaunchAgent. No incluye generalizar a ningún otro
> origen de la Central de Alarmas (hosts externos, el hub de Beszel,
> agentes, inventario de cobertura) — eso queda para features
> posteriores, uno a uno. No incluye ninguna acción correctiva, ni
> mostrar este diagnóstico nuevo en el dashboard — sigue siendo solo
> por línea de comandos, mismo alcance que tuvo 007 antes de que 008 le
> diera superficie visible.

---

## Feature 013 — material de partida (2026-08-12): generalizar el diagnóstico al inventario de cobertura

Con 007 (motor), 008 (visor), 009 (discos), 010 (HA), 011 (backups) y 012
(relays) cerrados, toca el sexto origen de los 9 de la Central de Alarmas:
**inventario** (`013-diagnostico-inventario`, mismo patrón de nombre
explícito que 009/010/011/012).

**Investigación previa a especificar — la mejor evidencia histórica del
proyecto hasta ahora, pero con un problema de solapamiento que hay que
resolver antes de tocar el spec.**

`inventario.db` (el mecanismo del feature 001) tiene **81 ejecuciones
reales** desde el 2026-08-07, con **detalle completo por componente
preservado en cada una** — a diferencia de los relays en 012, donde el
detalle por relay se perdía entre ejecuciones y solo quedaba el agregado.
Además ya existe `diff.compare_runs()` (`src/inventory/diff.py`,
expuesto por `--since RUN_ID` en el CLI): compara dos ejecuciones
cualesquiera y da de alta/baja componentes y brechas concretas. Es
evidencia más rica que la que tuvieron 009, 010 y 011 al empezar, y no
hace falta construir nada nuevo para leerla — mismo criterio de
"reutilizar lo que ya existe" que guió el diseño de esos tres.

**El problema real, encontrado consultando `inventario.db` en vivo, no
solo leyendo el código.** Las brechas tienen 6 tipos
(`classify_gap()` en `src/inventory/evaluate.py`): `sin_declaracion`,
`declaracion_caducada`, `sin_vigilancia`, `no_llega_a_dashboard`,
`riesgo_concentrado_telegram` y `condicion_incumplida`. De estos, **`condicion_incumplida` ocurre única y exclusivamente en la
categoría `entidad_ha`** (289 casos históricos; 2 activos ahora mismo,
comprobado en vivo — de nuevo la cerradura Amsterdam 9, `binary_sensor.
..._battery_critical` y `lock.cerradura_amsterdam_9`, en `unavailable`
desde las 13:35 de hoy). Esto no es casualidad: `classify_gap()` solo
asigna `condicion_incumplida` cuando el componente **sí** tiene mecanismo
de vigilancia declarado pero su último resultado real falla — y hoy el
único mecanismo así modelado en el inventario es `ha_monitor.py`. Es
decir: cuando el inventario marca `condicion_incumplida`, está
re-detectando, con otras palabras, exactamente el mismo fallo que el
origen `ha` ya diagnostica desde el feature 010. Diagnosticarlo aquí
también sería repetir trabajo ya hecho — mismo criterio que ya usó 011
para dejar fuera los backups de HA ("ya cubierto, nada nuevo aquí") — y,
en este caso concreto, reabriría un tema que Miquel ya cerró explícitamente
en la sesión del 010 ("dejemos el tema de la cerradura").

Los otros 5 tipos son los que de verdad importan para este feature: no
son un fallo en vivo de un dispositivo, son que el propio sistema de
monitorización **perdió** la declaración, la vigilancia o la llegada al
dashboard de algo. Es una forma de episodio distinta a las de 009-012 —
no "algo externo falló", sino "la cobertura misma retrocedió" — y encaja
con el objetivo original del proyecto (`BRIEFING.md`, arriba del todo).

**Dónde está la línea base real de estos 5 tipos — y por qué está
"fría".** Comprobado en vivo, agrupando por categoría (todas menos
`entidad_ha`, que es solo `condicion_incumplida`/`sin_declaracion` de la
cola larga ya conocida): `hermes` y `telegram` tuvieron brechas reales
hasta la ejecución #19 (2026-08-08), `host_externo` hasta la #28,
`integracion` hasta la #31, `infra_monitorizacion` hasta la #52
(2026-08-09) — todas del tipo `no_llega_a_dashboard` o `sin_vigilancia`.
Ejemplo real, ejecución #19: *"'Agente Hermes/Bautista' (hermes) está
vigilado por amsterdam9.bautista.heartbeat, pero un fallo real no
llegaría al dashboard del homelab"* y lo mismo para el canal de Telegram.
Todas se cerraron cuando los features 001-006 fueron declarando estado
esperado y ampliando qué llega al dashboard — es decir, **sí existe
línea base real e histórica** para estos 5 tipos (a diferencia de 009 y
010 al empezar), pero está fría: ninguna ha vuelto a aparecer desde el
2026-08-09. La validación de este feature puede apoyarse en
`--inventario-historico` contra esas ejecuciones reales concretas
(#19, #28, #31, #52) — sabiendo de antemano, por los propios commits de
001-006, cuál fue la causa real y la resolución real de cada una, el
mismo tipo de contraste contra una línea base ya investigada que usó 007
con los 49 reinicios de `beszel` — más que `--vivo` contra el estado sano
de hoy (que no tiene ninguna brecha de estos 5 tipos que congelar en
vivo).

**`declaracion_caducada` no tiene ni un solo caso real todavía.**
Comprobado: los 859 componentes con `last_reviewed_at` no nulo lo tienen
todos fechado a 2026-08-08; el umbral de caducidad son 90 días
(`is_declaration_stale()`), así que el primero no puede aparecer antes
de aproximadamente el 2026-11-06. Mismo tipo de limitación ya aceptada en
009/010 (un subtipo sin caso real todavía) — se documenta, no se
inventa un caso sintético.

**Lo que esto exige cambiar de la arquitectura de 012 (para
`/speckit-plan`, no para el spec).** Menos que en 009, parecido a 010:
`Episodio.origen` admite un valor nuevo (`"inventario"`). La evidencia no
sale de `homelab.db` sino de `inventario.db`, con un patrón nuevo pero
ya resuelto por el propio inventario: reconstruir el hallazgo de una
ejecución concreta (`store.hallazgos_de_ejecucion`/`brechas_de_ejecucion`)
más el `diff.compare_runs()` contra la ejecución inmediatamente anterior
a la que introdujo la brecha (`primera_ejecucion_id - 1`, ya guardado por
componente) — eso es la evidencia real de "qué cambió" que el propio
`--since` del CLI ya expone por separado, sin construir nada nuevo, solo
ensamblarlo en `evidencia.py` igual que ya se hizo con `diff.py`/`store.py`
para las otras 5 fuentes.

**Alcance propuesto (borrador, para que Miquel decida en `clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Diagnosticar en vivo una brecha activa de tipo `sin_declaracion`, `declaracion_caducada`, `sin_vigilancia`, `no_llega_a_dashboard` o `riesgo_concentrado_telegram` | Dentro |
| Diagnosticar en diferido una ejecución pasada concreta donde existió una de esas brechas | Dentro |
| Evidencia: el hallazgo de la ejecución + el `diff` contra la ejecución anterior a que apareciera (qué componente/mecanismo cambió) | Dentro |
| Validar contra las brechas reales de `hermes`/`telegram` (#19), `host_externo` (#28), `integracion` (#31) e `infra_monitorizacion` (#52), con su causa y resolución ya conocidas por los commits de 001-006 | Dentro |
| Diagnosticar `condicion_incumplida` (solo ocurre en `entidad_ha`) | **Propuesto fuera** — duplica el origen `ha` (feature 010); mismo criterio que excluyó los backups de HA en 011. A confirmar en `clarify` |
| Cualquier acción correctiva sobre una brecha (declarar estado, añadir vigilancia, etc.) | Fuera — solo diagnóstico |
| Generalizar a los 3 orígenes restantes (hosts externos, hub de Beszel, agentes) | Fuera — uno a uno, misma razón que 009/010/011/012 |
| Mostrar el diagnóstico de inventario en el dashboard | Fuera de este feature — mecanismo primero, superficie después |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (feature 007, generalizado a
> discos en 009, a Home Assistant en 010, a backups en 011 y a relays en
> 012) hoy no sabe diagnosticar nada del propio **inventario de
> cobertura** del homelab — el sistema que audita, componente a
> componente, si tiene un estado esperado declarado, si se vigila y si
> un fallo llegaría al dashboard. Quiero que también pueda diagnosticar
> episodios de inventario: cuando aparece una brecha de cobertura real —
> un componente que se queda sin declaración, sin vigilancia, o cuyo
> fallo no llegaría al dashboard — quiero poder pedirle al motor que
> reúna la evidencia real de ese momento, tanto en vivo como en un punto
> pasado concreto ya registrado en el histórico del inventario, y
> formule hipótesis de causa probable con el mismo rigor que ya tiene
> para los demás orígenes: varias hipótesis contrastadas, nunca inventar
> una causa sin evidencia, el mismo límite de gasto diario compartido con
> el resto del motor. No incluye diagnosticar el tipo de brecha
> "condición incumplida" de una entidad de Home Assistant: ese tipo
> concreto es el propio inventario re-detectando un fallo que el origen
> de Home Assistant (feature 010) ya diagnostica, así que no aporta
> nada nuevo validarlo aquí también. No incluye ninguna acción
> correctiva sobre ninguna brecha (declarar un estado esperado nuevo,
> añadir vigilancia, etc.). No incluye generalizar a ningún otro origen
> de la Central de Alarmas (hosts externos, el hub de Beszel, agentes) —
> eso queda para features posteriores, uno a uno. No incluye mostrar
> este diagnóstico nuevo en el dashboard — sigue siendo solo por línea
> de comandos, mismo alcance que tuvo 007 antes de que 008 le diera
> superficie visible.

---

## Feature 014 — material de partida (2026-08-12): generalizar el diagnóstico a los hosts externos

Con 013 cerrado, toca el séptimo origen de los 9: **hosts externos**
(`014-diagnostico-hosts-externos`) — los dos hosts físicos que Beszel
vigila además del propio Mac Mini: Uptime Kuma y AdGuard Home (DNS
primario). Distinto del hub de Beszel en sí (origen #8, "¿el propio
hub sigue reportando?") y de los relays `socat` (012, ya cerrado) —
este origen es "¿el host físico que Beszel ya vigila está arriba?".

**Investigación previa a especificar — con el homelab en vivo, no solo
con el código.** Los dos hosts, sus nombres canónicos
(`"Host de Uptime Kuma"`/`"Host de AdGuard Home (DNS primario)"`) y su
mapeo a Beszel (`UptimeKuma`/`AdGuardHome`) ya están fijados en tres
sitios que hablan del mismo componente con el mismo nombre:
`scripts/beszel_hosts_monitor.py::HOSTS`, `app.py::EXTERNAL_HOSTS` y
`inventory/sources.py` (categoría `host_externo`). El mecanismo ya
calcula "arriba"/"caído"/"sin evidencia" — evidencia en vivo, no algo
que este feature tenga que construir.

**El hallazgo real que cambia el diseño de la parte en diferido**: se
asumía, por analogía con relays (012), que `~/Library/Logs/
beszel-hosts-reader.log` (el `StandardOutPath` del LaunchAgent, sin
rotación desde el 2026-08-08) sería la fuente de evidencia histórica.
Comprobado en vivo (1.139 líneas): **no lo es**. Cada línea dice solo
`"N hosts escritos"` o `"consulta a Beszel incompleta o fallida"` — el
propio `build_payload()` de `beszel_hosts_monitor.py` escribe "hosts
escritos" en cuanto los dos hosts **aparecen** en la consulta,
independientemente de si su `status` es `up` o `down`. El log no
distingue nunca "los dos arriba" de "uno caído" — cero señal
reconstruible por host, a diferencia del `ok/total` que sí tenía
`dashboard-socat.log` para relays.

**Dónde está la evidencia histórica real, en cambio**: la propia base
de datos del hub de Beszel (`beszel_hub_data`, mismo volumen que ya
lee `beszel_hosts_monitor.py` vía `docker run` de solo lectura, mismo
patrón documentado en el `CLAUDE.md` general — montar el volumen,
nunca `docker cp` del fichero suelto por el problema de WAL ya
conocido). Más allá de `systems` (que solo trae el estado *actual*),
la tabla `system_stats` sí tiene series temporales reales por sistema
— comprobado en vivo para `UptimeKuma`: 352 muestras en 5 resoluciones
de retención escalonada (`1m`: última hora, `10m`: últimas 12h,
`20m`: último día, `120m`: últimos 5 días, `480m`: desde el
2026-07-14, un mes completo) — mismo patrón de retención por niveles
que ya usa `container_metrics`/`container_metrics_hourly` en este
propio proyecto. La ausencia de muestras en una ventana es la señal de
"host no reportaba" — no hay ningún campo explícito "caído", igual que
`disk_metrics`/`container_metrics` tampoco tienen un booleano así y ya
se interpretan por ausencia/anomalía en 007/009. `alerts`/
`alerts_history` (las tablas que sí serían un booleano explícito de
"caído") están vacías — Beszel no tiene alertas configuradas para
estos sistemas, así que no son una fuente utilizable hoy.

**Ninguna IP ni dato de topología nueva en `stats`** (comprobado en
vivo): los campos son métricas de rendimiento (CPU, memoria, disco,
red, temperatura) y un nombre de interfaz (`wlan0`) con contadores de
bytes — ninguna dirección IP, a diferencia de `socat_relays.json` en
012. Sin justificación nueva de Principio X que documentar.

**Línea base real con causa raíz ya conocida — mejor que cualquier
feature anterior de este proyecto.** Comprobado en vivo: `system_stats`
tiene un hueco idéntico para los dos hosts, del 2026-07-30 a las
00:00-01:40 hasta el 2026-08-07 a las 22:20 — ocho días sin ninguna
muestra. No es una casualidad ni una incógnita: coincide exactamente
con la avería ya documentada en el `CLAUDE.md` general del homelab
("Beszel — routing roto tras reinicio", con su propio runbook en
`docs/`) — los contenedores de este Mac perdieron la ruta a la LAN el
30 de julio, y no se resolvió hasta los relays `socat` de Beszel del 7
de agosto. A diferencia de los 49 reinicios de `beszel` (007, causa
nunca encontrada) o de las brechas de inventario (013, causa "se
introdujo la categoría, se corrigió con el feature siguiente"), aquí sí
existe una causa raíz real e independientemente documentada contra la
que medir si el diagnóstico llega a una conclusión razonable.

**Alcance propuesto (borrador, para que Miquel decida en `clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Diagnosticar en vivo el estado actual de uno de los 2 hosts, leyendo `beszel_hosts.json` con la misma política de frescura que ya usa el dashboard (900s, dato + latido) | Dentro |
| Diagnosticar en diferido un momento pasado concreto, consultando `system_stats` del hub de Beszel para ese host en una ventana alrededor del momento — presencia/ausencia de muestras como señal, nunca un booleano inventado | Dentro |
| Diagnosticar el propio hub de Beszel (`get_beszel_hub_status()`, si deja de reportar sobre *todos* sus sistemas a la vez) | Fuera — es el origen #8, con su propia investigación pendiente |
| Cualquier acción correctiva sobre Beszel, sus hosts o sus relays | Fuera — solo diagnóstico |
| Generalizar a los 2 orígenes restantes (hub de Beszel, agentes) | Fuera — uno a uno, misma razón que 009-013 |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (007, generalizado a discos en
> 009, HA en 010, backups en 011, relays en 012 e inventario en 013)
> hoy no sabe diagnosticar nada de los hosts físicos externos que
> Beszel ya vigila — el host de Uptime Kuma y el de AdGuard Home (DNS
> primario), la infraestructura de observabilidad del propio homelab,
> distinta del Mac Mini. Quiero que también pueda diagnosticar
> episodios de host externo: en vivo, leyendo el estado ya calculado
> por el dashboard (arriba/caído/sin evidencia, con su misma política
> de frescura); en diferido, señalando un momento pasado y consultando
> directamente la base de datos del hub de Beszel para ver si ese host
> seguía reportando datos de rendimiento en esa ventana — sin inventar
> un estado "caído" que la propia evidencia no sostenga si solo hay
> ausencia de muestras, nunca un registro explícito de caída. Mismo
> rigor que los demás orígenes: varias hipótesis contrastadas, nunca
> inventar una causa, mismo límite de gasto diario compartido. No
> incluye diagnosticar el propio hub de Beszel (si deja de reportar
> sobre todos sus sistemas a la vez) — eso es otro origen, con otra
> investigación pendiente. No incluye ninguna acción correctiva sobre
> Beszel ni sobre los hosts. No incluye generalizar a los 2 orígenes
> restantes de la Central de Alarmas (el hub de Beszel, agentes). No
> incluye mostrar este diagnóstico en el dashboard — sigue siendo solo
> por línea de comandos.

---

## Feature 015 — material de partida (2026-08-12): generalizar el diagnóstico al hub de Beszel

Con 014 cerrado, toca el octavo origen de los 9: **el propio hub de
Beszel** (`015-diagnostico-hub-beszel`) — distinto de los hosts
externos (014, ya cerrado): no es "¿está arriba el host X que Beszel
vigila?", es "¿el hub de Beszel sigue vigilando *algo* de verdad, o se
quedó colgado?".

**El mecanismo ya existe y ya se investigó en el Frente 1**:
`app.py::get_beszel_hub_status()` (feature 003) lee `hub_systems` de
`beszel_hosts.json` — la antigüedad (`updated`) de **todos** los
sistemas que Beszel tiene registrados, no solo los 2 hosts canónicos
— y decide `sano=False` únicamente cuando **todos** superan
`BESZEL_HOSTS_MAX_AGE_S` (900s) a la vez. Un solo sistema viejo no
cuenta — eso ya lo cubre 014. Sin comprobación de latido aparte: si el
propio script (`beszel_hosts_monitor.py`) deja de ejecutarse, los
`updated` capturados quedan congelados y acaban superando el umbral
igual, así que el mecanismo ya detecta ambos fallos (Beszel realmente
colgado, o el propio lector sin ejecutarse) sin necesitar dos
comprobaciones distintas.

**El hallazgo real que cambia la validación de este feature, comprobado
antes de escribir nada**: se esperaba poder reutilizar la misma avería
real que validó 014 (routing de contenedores roto, 30 jul-7 ago). No
sirve para este origen. Comprobado en vivo contra `system_stats`: el
tercer sistema que vigila Beszel, `Mac Mini Server` —el propio Mac
donde vive el hub—, **no tiene ningún hueco en todo el mes de
retención** (90 muestras de `480m` seguidas, desde el 2026-07-13 sin
ninguna interrupción >10h). Tiene sentido: el agente de Beszel en el
propio Mac se comunica con el hub en local, sin pasar por el routing
de contenedores que se rompió — la avería solo afectó a los 2 hosts
remotos (Kuma, AdGuard), nunca a "todos los sistemas a la vez". Es
decir: **durante toda la avería real de 014, el hub de Beszel según
`get_beszel_hub_status()` estuvo `sano=True` en todo momento** — no es
un ejemplo válido para este origen.

**No existe, en la evidencia real disponible hoy, ningún episodio
conocido de "hub realmente caído"** (mismo tipo de limitación ya
aceptada en 009/010/011, no una excepción de este feature) — el
propio `BRIEFING.md` ya documentaba que el síntoma original del Caso 3
("Beszel no vigila bien lo que vigila", visto el 06-08) dejó de
reproducirse antes de que existiera ningún mecanismo que lo
investigara a fondo. La validación de este feature se apoyará en
`--vivo` contra el estado sano actual, igual que 009/010/011 al
arrancar.

**Alcance propuesto (borrador, para que Miquel decida en `clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Diagnosticar en vivo si el hub sigue vigilando algo (mismo cálculo que `get_beszel_hub_status()`, con la antigüedad real de cada sistema) | Dentro |
| Diagnosticar en diferido un momento pasado, consultando `system_stats` de **todos** los sistemas del hub en una ventana — sin ninguna muestra en ninguno a la vez, nunca un booleano "caído" inventado si solo hay ausencia parcial | Dentro |
| Sin identificador de componente — como los backups (011), solo hay un hub, `--hub-beszel-vivo`/`--hub-beszel-historico MOMENTO_ISO`, mismo patrón `--backup-vivo`/`--backup-historico` | Dentro |
| Diagnosticar un host externo concreto (Kuma, AdGuard) | Fuera — es el origen #7 (014), ya cerrado |
| Cualquier acción correctiva sobre Beszel | Fuera — solo diagnóstico |
| Generalizar al último origen restante (agentes) | Fuera — uno a uno, misma razón que 009-014 |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (007, generalizado a discos en
> 009, HA en 010, backups en 011, relays en 012, inventario en 013 y
> hosts externos en 014) hoy no sabe diagnosticar nada del propio hub
> de Beszel — la herramienta de observabilidad del homelab que vigila
> el Mac Mini y los 2 hosts externos. Quiero que también pueda
> diagnosticar si el hub sigue vigilando algo de verdad, distinto de
> si un host concreto está caído (eso ya lo cubre el origen anterior):
> en vivo, leyendo la antigüedad de todos los sistemas que el hub
> tiene registrados y si todos a la vez superan el umbral de frescura
> ya establecido; en diferido, señalando un momento pasado y
> consultando si todos los sistemas del hub dejaron de reportar datos
> de rendimiento a la vez en esa ventana — sin inventar un estado
> "caído" que la propia evidencia no sostenga si solo hay ausencia
> parcial. Mismo rigor que los demás orígenes: varias hipótesis
> contrastadas, nunca inventar una causa, mismo límite de gasto diario
> compartido. Como con los backups, no hace falta identificar ningún
> componente — solo hay un hub. No incluye diagnosticar un host
> externo concreto — eso es otro origen, ya cubierto. No incluye
> ninguna acción correctiva sobre Beszel. No incluye generalizar al
> último origen restante (agentes). No incluye mostrar este
> diagnóstico en el dashboard — sigue siendo solo por línea de
> comandos.

---

## Feature 016 — material de partida (2026-08-12): generalizar el diagnóstico a los agentes (LaunchAgents)

Con 015 cerrado, toca el noveno y último origen: **los agentes**
(`016-diagnostico-agentes`) — los ~20 LaunchAgents que ejecutan toda
la automatización del homelab (`amsterdam9.*`, `com.homeassistant.*`,
`ai.hermes.*`), vigilados hoy por `app.py::get_launchagents()`.

**Ambigüedad real encontrada en el propio histórico de este
`BRIEFING.md`, resuelta antes de especificar.** La tabla de orígenes
de "Feature 006" (línea 539-543) lista **dos** filas separadas bajo
"Automatización": `LaunchAgents` (`get_launchagents()`, "agente
crasheado") y `Latidos de monitores` (`get_monitor_heartbeats()`, "un
monitor dejó de ejecutarse"). Las dos siguieron apareciendo juntas en
la lista de "orígenes restantes" hasta el material de 011 — pero entre
011 y 012, `monitores` **desapareció de la lista sin que ningún
feature la cerrara**. Ningún commit la generalizó; simplemente dejó de
mencionarse. Se documenta aquí como lo que es —una inconsistencia real
del propio histórico del proyecto, no una decisión tomada— y se
resuelve así: **este feature cierra `LaunchAgents` en el sentido
literal del término "agentes"** (mismo uso consistente en el resto de
`BRIEFING.md` desde 012 en adelante); `Latidos de monitores`
(`get_monitor_heartbeats()`) queda **explícitamente fuera**, como
mecanismo relacionado pero distinto, disponible para un feature futuro
si Miquel decide cerrarlo — no se amplía el alcance de este feature
para "arreglar" la inconsistencia sin que él lo decida.

**El hallazgo real que hace de este origen un caso estructuralmente
distinto a los 8 anteriores**: no existe **ningún** dato histórico
reconstruible. Comprobado en vivo:

- `launchagents_raw.txt` (el fichero que lee `get_launchagents()`,
  escrito por `dump_launchagents.sh` cada 5 min vía el LaunchAgent
  `amsterdam9.dashboard.launchagents`) se **sobreescribe** en cada
  ciclo — solo el estado actual, sin ningún historial.
- Su log (`/tmp/dump_launchagents.log`, `StandardOutPath` del propio
  LaunchAgent) tiene 9.392 líneas — **todas vacías**: `launchctl list
  > fichero` no produce salida en `stdout` por sí solo, así que el log
  no contiene ni un solo dato real aprovechable.
- No existe ninguna tabla en `homelab.db` equivalente a
  `restart_history` para LaunchAgents — `docker_monitor.py` solo
  vigila contenedores Docker, nunca ha vigilado agentes.

**Consecuencia real para el diseño**: este es el primer origen del
proyecto que **no puede tener un modo diferido** — no por falta de un
episodio real conocido (009/010/011/015, que sí tenían un mecanismo de
consulta histórica aunque sin caso real), sino porque no existe
ninguna fuente que consultar. El Principio XI (Reproducibilidad
Diferida) no se puede cumplir literalmente para este origen — se
documentará así, explícitamente, en el `Constitution Check` del plan
en vez de forzar un mecanismo diferido ficticio o fingir que se
cumple. La reproducibilidad que sí se puede garantizar y se garantizará
(SC-001, igual que el resto) es la del propio motor: diagnosticar dos
veces el mismo episodio ya congelado en vivo da la misma conclusión.

**Alcance propuesto (borrador, para que Miquel decida en `clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Diagnosticar en vivo un LaunchAgent concreto (por `label`) — vigilando, crasheado, o "idle" según el mismo cálculo que ya usa el dashboard | Dentro |
| Diagnosticar en diferido un momento pasado | **Fuera — imposible con la evidencia real disponible**, no una decisión de alcance |
| `Latidos de monitores` (`get_monitor_heartbeats()`) | Fuera — mecanismo distinto, disponible para un feature futuro |
| Cualquier acción correctiva sobre un LaunchAgent (reiniciarlo, recargarlo) | Fuera — solo diagnóstico |
| Mostrar el diagnóstico en el dashboard | Fuera — sigue siendo solo por línea de comandos |

Con esto se cierran los 9 orígenes de la Central de Alarmas que este
proyecto se propuso generalizar (`BRIEFING.md`, línea 56 en adelante).

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (007, generalizado a discos en
> 009, HA en 010, backups en 011, relays en 012, inventario en 013,
> hosts externos en 014 y el hub de Beszel en 015) hoy no sabe
> diagnosticar nada de los LaunchAgents que ejecutan toda la
> automatización del homelab — los ~20 agentes `amsterdam9.*`,
> `com.homeassistant.*` y `ai.hermes.*`. Quiero que también pueda
> diagnosticar un agente concreto: reunir su estado real (si tiene un
> proceso activo, y su último código de salida) y formular hipótesis
> de causa probable cuando esté fallando, con el mismo rigor que los
> demás orígenes — varias hipótesis contrastadas, nunca inventar una
> causa, mismo límite de gasto diario compartido. A diferencia de
> todos los orígenes anteriores, este no tiene ningún modo diferido:
> no existe ningún historial real de LaunchAgents que consultar, ni en
> el propio fichero de estado (se sobreescribe cada 5 minutos) ni en
> su log (vacío) ni en ninguna base de datos del homelab — solo se
> puede diagnosticar el estado actual. No incluye el mecanismo
> relacionado de latidos de monitores (`get_monitor_heartbeats()`) —
> es una fuente de evidencia distinta, fuera de alcance de este
> feature. No incluye ninguna acción correctiva sobre ningún agente
> (reiniciarlo, recargarlo). No incluye mostrar este diagnóstico en el
> dashboard — sigue siendo solo por línea de comandos.

---

## Feature 017 — material de partida (2026-08-13): generalizar el diagnóstico a los latidos de monitores

Con los 9 orígenes de la Central de Alarmas cerrados en 016, queda un
décimo mecanismo relacionado pero distinto, dejado fuera explícitamente
en esa misma sesión: **`Latidos de monitores`** (`get_monitor_heartbeats()`
en `app.py`) — si un monitor (`docker_monitor.py`, `ha_monitor.py`, etc.)
sigue vivo no según si su LaunchAgent está cargado (eso ya lo cubre 016),
sino según si ha completado un ciclo hace poco. Cierra un caso distinto:
un LaunchAgent cargado pero cuyo proceso se cuelga en silencio sin
crashear.

**Cómo funciona, comprobado en vivo:**

- `heartbeat.py` (`/Volumes/FastData/homelab/scripts/heartbeat.py`) escribe
  un fichero `<job>.json` por tarea en `/Volumes/FastData/homelab/data/heartbeats/`
  cada vez que esa tarea completa un ciclo: `{job, timestamp, epoch, status,
  detail}`. Cada escritura **sobreescribe** el fichero anterior — mismo
  patrón sin historial que 016 (LaunchAgents), no un patrón nuevo.
- `app.py::get_monitor_heartbeats()` (líneas 714-732) lee esos ficheros
  para una lista fija de 8 jobs (`MONITOR_JOBS`, línea 54) y calcula
  `ok = edad_del_latido <= max_age_s` por job — el mismo cálculo que ya
  alimenta la Central de Alarmas (`add("monitores", "monitor_sin_latido",
  ...)`, línea 1108-1113): esta pieza **ya genera alarmas** en el
  dashboard hoy, lo que falta es que el motor de diagnóstico sepa
  explicar el porqué de una.
- Sin persistencia histórica: no hay tabla en `homelab.db` ni ninguna otra
  base de datos con el histórico de latidos — mismo caso estructural que
  016, este origen tampoco tendrá modo diferido.

**Hallazgo real no trivial, encontrado al comparar el código con los
datos en disco (2026-08-13), antes de especificar:** existen **dos
listas independientes** de "qué jobs tienen latido", y no coinciden:

| Job | En `MONITOR_JOBS` (`app.py`, alimenta el dashboard y las alarmas) | En `DEFAULT_MANIFEST` (`heartbeat.py`, alimenta `heartbeat.py --report` y el informe de Telegram) |
|---|---|---|
| `docker-monitor`, `ha-monitor`, `dns-pi-monitor`, `verify-backups`, `inventario-cobertura` | Sí | Sí |
| `telegram-monitor`, `beszel-hosts`, `bautista-calendar` | Sí | **No** |
| `metrics-retention`, `immich-album-sync` | **No** | Sí |

Los tres jobs ausentes de `DEFAULT_MANIFEST` sí escriben su latido
(comprobado: `telegram-monitor.json` y `beszel-hosts.json` existen y se
actualizan en disco), pero `heartbeat.py::report()` solo itera sobre
`load_manifest().items()` — así que esos tres son **invisibles** para
`heartbeat.py --report` y para la línea "💓 Latidos" del informe de las
09:00, aunque si se les pregunta al dashboard sí aparecen. Es el mismo
patrón de brecha que motivó el proyecto entero (Principio XIII): un dato
real que existe pero no llega a todos los sitios que deberían mostrarlo.
No se corrige aquí — es una inconsistencia del propio homelab, fuera del
código de este proyecto (`heartbeat.py` y `app.py` viven en el repo
privado) — se documenta y se **decide qué lista usa el origen nuevo**:
`app.py::MONITOR_JOBS`, porque es literalmente la función que 016 excluyó
por su nombre (`get_monitor_heartbeats()`) y la que ya alimenta la Central
de Alarmas real.

**Alcance propuesto (borrador, para que Miquel decida en `clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Diagnosticar en vivo el latido de un job concreto (de los 8 de `MONITOR_JOBS`) — a tiempo, rancio, o nunca ha latido | Dentro |
| Diagnosticar en diferido un momento pasado | Fuera — sin historial real que consultar, igual que 016 |
| Corregir la inconsistencia entre `MONITOR_JOBS` y `DEFAULT_MANIFEST` | Fuera — bug real del homelab, no de este proyecto |
| Cualquier acción correctiva (relanzar un monitor) | Fuera — solo diagnóstico |
| Mostrar el diagnóstico en el dashboard | Fuera — sigue siendo solo por línea de comandos |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El motor de diagnóstico de episodios (007, generalizado a discos en
> 009, HA en 010, backups en 011, relays en 012, inventario en 013,
> hosts externos en 014, el hub de Beszel en 015 y los LaunchAgents en
> 016) hoy no sabe diagnosticar el mecanismo de latidos de monitores
> (`get_monitor_heartbeats()`), dejado explícitamente fuera de 016 por
> ser una fuente de evidencia distinta. Quiero que también pueda
> diagnosticar el latido de un job concreto de los 8 vigilados hoy por
> el dashboard: reunir su estado real (si ha latido, hace cuánto, y su
> último detalle) y formular hipótesis de causa probable cuando esté
> rancio o ausente, con el mismo rigor que los demás orígenes — varias
> hipótesis contrastadas, nunca inventar una causa, mismo límite de
> gasto diario compartido. Igual que los LaunchAgents en 016, este
> origen no tiene ningún modo diferido: cada latido se sobreescribe en
> cada ciclo y no existe ninguna tabla histórica, así que solo se puede
> diagnosticar el estado actual. No incluye corregir la inconsistencia
> real encontrada entre la lista de jobs del dashboard y la de
> `heartbeat.py` — es un defecto del homelab, no de este proyecto. No
> incluye ninguna acción correctiva sobre ningún monitor (relanzarlo).
> No incluye mostrar este diagnóstico en el dashboard — sigue siendo
> solo por línea de comandos.

---

## Feature 018 — material de partida (2026-08-13): generalizar el visor de diagnósticos a los 9 orígenes restantes (y arreglar el de contenedor)

Con los 10 orígenes de `src/diagnostico/` cerrados (007-017), el visor
del dashboard (feature 008) solo muestra diagnósticos de `contenedor`
— el resto son solo consultables por CLI. Este feature generaliza esa
superficie, igual que 009-017 generalizaron el motor.

**Hallazgo crítico, comprobado en vivo antes de especificar: el visor
de `contenedor` está roto en producción ahora mismo.**
`get_diagnostico_para_alarma()` (`app.py`, feature 008) sigue
consultando `WHERE contenedor = ?`, pero el feature 009 (mismo día,
después) migró el esquema a `componente`+`origen`
(`_migrar_episodios_contenedor_a_componente`, `store.py`). Comprobado
contra la base real:

```
$ sqlite3 diagnostico.db "SELECT ... FROM episodios WHERE contenedor = 'beszel';"
Error: in prepare, no such column: contenedor
```

El fallo se traga en silencio (`_diagnostico_db_query` atrapa
cualquier excepción y devuelve `None`, a propósito — FR-008 de 008: un
origen roto no debe tumbar el resto de `/api/data`). Consecuencia: la
pestaña "Alarmas" lleva **desde el 2026-08-11 sin mostrar ningún
diagnóstico**, ni siquiera de contenedor — viola el Principio XII
(Precisión del Dashboard, NO NEGOCIABLE) ahora mismo, sin que nadie lo
haya notado porque el silencio es indistinguible de "no hay
diagnóstico todavía". Se arregla como prerrequisito de este feature,
no como un feature aparte — no tiene sentido generalizar una consulta
rota.

**El frontend ya es agnóstico al origen — sin cambios de JS.**
`diagnosticoHtml(a)` se llama para cualquier alarma con `a.diagnostico`
no nulo, sin distinguir de qué origen es (comprobado leyendo
`app.py`, la función y su único punto de llamada en `renderAlarmas`).
Todo el trabajo de este feature es backend (Python), en un único
fichero fuera de este repo, sin control de versiones:
`/Volumes/FastData/homelab/docker/homelab-dashboard/scripts/app.py`
— mismo patrón que 008 (dashboard-only), con el riesgo añadido de que
no hay `git diff` ni revert fácil: se hace copia de seguridad del
fichero antes de tocarlo, y se verifica el contenedor tras cada cambio
(`docker compose up -d --build` en
`docker/homelab-dashboard/`, no está en la lista de contenedores
críticos que exigen aprobación).

**Los 10 orígenes de alarma del dashboard no emparejan igual con
`diagnostico.db` — comprobado uno a uno leyendo `get_active_alarms()`
antes de diseñar nada:**

| Alarma (`add(...)`) | Origen de `diagnostico.db` | Identidad real para emparejar | Ventana temporal disponible |
|---|---|---|---|
| `contenedores` | `contenedor` | `c["name"]` | `down_since` → misma tolerancia de 30 min ya validada (008) |
| `ha` | `ha` | `cid` (el diccionario ya distingue `cid` de `label`; la alarma muestra `label`, pero `diagnostico.db` guarda `cid`) | `down_since` |
| `discos` | `disco` | `d["label"]` | Ninguna — la alarma no pasa `antiguedad_s` |
| `backup` | `backup` | Ninguna — `componente` es el momento ISO del propio diagnóstico, no un nombre estable (`data-model.md` de 011) | Ninguna — toca el episodio más reciente de ese origen, sin más filtro |
| `monitores` | `latido` | `m["job"]` (la alarma muestra `label`, p. ej. "Monitor de Docker"; `diagnostico.db` guarda el `job`, p. ej. "docker-monitor" — feature 017) | Ninguna con sentido real: `latido` no tiene modo diferido, solo existe "el último episodio vivo de este job" |
| `relays` | `relay` | `r["name"]` | Ninguna — **y solo empareja si ese relay se diagnosticó en vivo por nombre**: en diferido, `relay_agregado` nunca identifica cuál relay concreto (research.md de 012) — limitación real, no un fallo de este feature |
| `hosts_externos` | `host_externo` | Nombre canónico, no el de pantalla — mapeo `HOSTS_EXTERNOS` de `evidencia.py` ("Host de Uptime Kuma" → "UptimeKuma"), que hay que replicar en `app.py` igual que ya replica `EXTERNAL_HOSTS`/`MONITOR_JOBS` | Ninguna — la alarma no pasa `antiguedad_s` |
| `beszel_hub` | `hub_beszel` | Ninguna — mismo caso que `backup`, `componente` es el momento ISO (solo existe un hub) | Ninguna — episodio más reciente de ese origen |
| `agentes` (LaunchAgents) | `agente` | `a["label"]` completo (la alarma muestra `a["short"]`; hay que pasar el `label` real para emparejar, no lo que se ve en pantalla) | Ninguna — sin modo diferido |
| `agentes` (Crons de Hermes) | **ninguno** | — | **Fuera de alcance real, no una alarma sin emparejar**: ningún origen de `diagnostico.py` cubre los crons de Hermes — son un mecanismo distinto (`get_crons()`), nunca generalizado. Su `diagnostico` queda `None` siempre |
| `inventario` | `inventario` | `b.get("componente", "")` | Ninguna — la alarma no pasa `antiguedad_s` |

**Decisión de diseño**: una única función generalizada,
`get_diagnostico_para_origen(origen, identidad, down_since=None)`,
sustituye a `get_diagnostico_para_alarma()` (que solo servía a
contenedor). Con `down_since`, aplica la misma tolerancia de ventana ya
validada por 008 (research.md §2-§3 de esa feature). Sin él —el caso de
8 de los 10 orígenes—, toma el episodio más reciente para esa
`(origen, identidad)`, sin ventana: no hay ningún ancla temporal real
que comparar, y forzar una ventana arbitraria sería inventar precisión
que la evidencia no tiene (mismo criterio que 014/015 con "no
presentes la ausencia como una prueba de caída").

**Alcance propuesto (borrador, para que Miquel decida en `clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Arreglar el emparejamiento roto de `contenedor` (bug crítico, Principio XII) | Dentro — prerrequisito |
| Generalizar a `ha`, `discos`, `relays`, `host_externos`, `agentes` (LaunchAgents), `inventario`, `monitores` (latido) — 7 orígenes con identidad estable | Dentro |
| Generalizar a `backup`, `beszel_hub` — 2 orígenes singleton, sin identidad estable, solo "el más reciente" | Dentro |
| Cobertura de los crons de Hermes en la alarma `agentes` | Fuera — ningún origen de `diagnostico.py` los cubre; ampliar eso es un feature nuevo, no de este |
| Cambios en el frontend (JS/CSS) | Fuera — ya es agnóstico al origen, comprobado |
| Lanzar un diagnóstico nuevo desde el navegador | Fuera — sigue siendo solo por CLI (igual que 008) |
| Corregir la propia limitación estructural de `relay` (no poder saber cuál relay concreto en diferido) | Fuera — es del motor (012), no de este visor |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El visor de diagnósticos en el dashboard (feature 008) solo muestra
> el diagnóstico de contenedores caídos, y además está roto: sigue
> consultando una columna (`contenedor`) que el feature 009 renombró a
> `componente`+`origen` el mismo día, así que lleva desde el
> 2026-08-11 sin mostrar ningún diagnóstico en producción, ni siquiera
> el de contenedor — se traga el error en silencio. Quiero arreglar
> ese emparejamiento primero, y luego generalizarlo a los 9 orígenes
> restantes del motor de diagnóstico (disco, HA, backup, relay,
> inventario, host externo, hub de Beszel, agente, latido) para que
> cualquier alarma activa con un diagnóstico ya hecho lo muestre,
> igual que ya hace contenedor. Para los orígenes con modo diferido y
> un ancla temporal real en la alarma (contenedor, HA), el
> emparejamiento respeta la misma ventana de tolerancia que ya usa
> contenedor. Para el resto, que no tienen ese ancla o no tienen modo
> diferido, basta con el episodio más reciente de ese origen. No
> incluye dar cobertura de diagnóstico a los crons de Hermes, que hoy
> comparten la alarma "agentes" con los LaunchAgents pero no los cubre
> ningún origen del motor. No incluye ningún cambio de frontend — ya
> es agnóstico al origen. No incluye poder lanzar un diagnóstico nuevo
> desde el navegador.

---

## Feature 019 — material de partida (2026-08-13): remediación automática, primera pieza

Con el diagnóstico cerrado en los 10 orígenes (007-017) y su visor
generalizado (018), toca el Frente 2 que nunca se empezó: la
**remediación automática** (Principios IV-VIII, Modelo Operacional B).
Es la primera vez que este proyecto escribe sobre el homelab real, no
solo lo lee — mayor riesgo real que cualquier feature anterior.

**Lo que pidió Miquel, en sus palabras**: un sistema para poder pasar
cada tipo de remediación de manual a automática (y viceversa) cuando
él decida confiar en ella — no todo-o-nada desde el principio.

**Tres decisiones de diseño confirmadas con Miquel (AskUserQuestion,
2026-08-13), las tres con la opción recomendada**:

1. **Granularidad del interruptor: por tipo de acción**, no por
   componente individual — un interruptor para "rotar log", válido
   para todos los logs elegibles a la vez. Mismo nivel que ya usa
   `docker_monitor.py` para tratar a los contenedores no críticos como
   grupo.
2. **Interfaz: solo CLI** — mismo patrón que `diagnostico.cli`, ningún
   cambio de modo por accidente ni desde el móvil.
3. **Requisito para pasar a automático: solo la decisión de Miquel, en
   cualquier momento** — el sistema lleva la cuenta de aciertos/fallos
   por tipo de acción y se la enseña, pero nunca se autopromueve solo
   (Principio VII, un actor por acción). Sin barrera de "N aciertos
   mínimos".

**Hallazgo real que cambió el planteamiento, encontrado investigando
antes de especificar**: la constitución dice que el alcance de
remediación es *"para causas ya diagnosticadas con certeza"*. Se
comprobó cuántos diagnósticos `causa_probable` existen hoy en
`diagnostico.db`, de los 36 producidos por el motor (007-017):

```
$ sqlite3 diagnostico.db "SELECT conclusion_tipo, count(*) FROM diagnosticos GROUP BY conclusion_tipo;"
no_diagnosticable|36
```

**Cero.** Todos honestos "no se puede diagnosticar" — nunca ha habido
un caso real malo en el momento de validar cada feature. Atar la
remediación a que el motor DeepSeek confirme una causa dejaría esta
feature sin ningún caso real contra el que validarla hoy, rompiendo la
disciplina que ha seguido todo el proyecto desde 007 (siempre contra
evidencia real, nunca solo sintética).

**Decisión, confirmada con Miquel (segunda AskUserQuestion)**: la v1
de remediación actúa sobre **condiciones deterministas simples**
("condición conocida → acción conocida"), sin pasar por el motor
DeepSeek — mismo patrón que ya usa `docker_monitor.py` (que tampoco
usa IA). El primer y único tipo de acción de esta feature: **rotar un
log que ha crecido sin rotación**, comprobado como problema real y
activo hoy, no del barrido de hace dos semanas:

```
$ ls -la ~/Library/Logs/health-docker.log ~/Library/Logs/health-ha.log
-rw-r--r--  ...  71288308  ... health-docker.log   (63 MB el 01-08, sigue creciendo)
-rw-r--r--  ...  11640902  ... health-ha.log        (8,1 MB el 01-08, sigue creciendo)
```

De paso se comprobaron los otros hallazgos del barrido: los 4 plists
corruptos ya están arreglados (`plutil -lint` da OK en los 4) y
`beszel-agent.log` ya no existe — ninguno de los dos sigue siendo un
caso real hoy, así que no entran en el alcance de esta feature.

**Tensión real con el Principio IV, a resolver explícitamente en el
plan**: *"Ninguna acción correctiva se ejecuta sin un diagnóstico que
la justifique"*. Este proyecto usa "diagnóstico" en dos sentidos: el
artefacto formal de `src/diagnostico/` (`Diagnostico`/`Hipotesis`,
007-017), y el sentido genérico de "una causa conocida y verificada".
Una condición determinista y verificada en el momento (un fichero
concreto supera un umbral de tamaño porque nada lo rota) es un
diagnóstico en el segundo sentido —conocido, verificable, sin
inventar nada— aunque no pase por DeepSeek. Se documentará esta
distinción explícitamente en el `Constitution Check` del plan, mismo
criterio que ya aclaró el alcance real de Principio XI en 016.

**Arquitectura propuesta (borrador, para `/speckit-plan`)**:

- Paquete nuevo `src/remediacion/`, independiente de
  `src/diagnostico/` (sin dependencia entre ambos en v1 — se podría
  tender un puente en un feature futuro si el motor empieza a producir
  `causa_probable` de verdad).
- Estado propio en `remediacion.db` (nueva base, mismo patrón sqlite
  que `diagnostico.db`): `configuracion_accion` (`tipo_accion` PK,
  `modo` ∈ {manual, automatico}, por defecto manual — "si hay duda, se
  trata como de alto riesgo"), y `intentos_remediacion` (historial:
  propuesto/aprobado/rechazado/ejecutado/fallido, con detalle —
  Principio VIII extendido de hipótesis a acciones).
- CLI `remediacion.cli`, mismo patrón que `diagnostico.cli`:
  `comprobar` (evalúa la condición determinista, registra una
  propuesta), `pendientes` (lista lo que espera aprobación en modo
  manual), `aprobar ID` / `rechazar ID`, `modo TIPO_ACCION
  --automatico|--manual`, `historial TIPO_ACCION`.
- Reversibilidad escrita (Principio VI) para "rotar log": la acción
  **renombra**, nunca borra — `foo.log` → `foo.log.rotado-<ISO>`, y
  crea un `foo.log` vacío. El rollback es literalmente devolver el
  fichero rotado a su nombre original; nada se pierde nunca.

**Alcance propuesto (borrador, para que Miquel confirme en
`clarify`):**

| Pieza | Dentro / Fuera |
|---|---|
| Interruptor manual/automático por tipo de acción, con historial | Dentro |
| Un único tipo de acción: rotar un log que supera un umbral de tamaño sin rotación | Dentro |
| Cualquier otro tipo de acción del barrido (plists, logs en `/tmp`...) | Fuera — no son problemas reales activos hoy, o quedan para un feature futuro |
| Atar la remediación al motor DeepSeek (`causa_probable`) | Fuera de v1 — sin ningún caso real hoy; posible puente futuro |
| Acciones sobre contenedores o componentes críticos | Fuera siempre, sin excepción — Principio VII, regla 3 del `CLAUDE.md` general |
| Notificar a Miquel por Telegram | Fuera — el CLI es la única superficie en v1 (decisión de "interfaz" ya confirmada) |
| Mostrar el estado de remediación en el dashboard | Fuera — sigue el mismo patrón que el motor de diagnóstico: CLI primero |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> El proyecto tiene diagnóstico cerrado en los 10 orígenes (007-017)
> pero remediación automática nunca empezó (Principios IV-VIII,
> Modelo Operacional B). Quiero un sistema de remediación con un
> interruptor manual/automático por tipo de acción (no por componente
> individual), que Miquel controla siempre él mismo desde un CLI (sin
> autopromoción ni barrera de aciertos mínimos, aunque el sistema le
> enseña el historial de aciertos/fallos de cada tipo al decidir). Por
> defecto toda acción nueva empieza en modo manual: el sistema propone
> y espera aprobación explícita antes de ejecutar; en modo automático,
> ejecuta directamente y registra el resultado para revisión posterior
> — igual en ambos modos: solo actúa dentro de una lista cerrada de
> acciones reversibles con rollback escrito (Principios V/VI), nunca
> sobre un componente crítico. La v1 actúa sobre condiciones
> deterministas verificables en el momento, sin depender de que el
> motor DeepSeek (007-017) confirme una causa — hoy ese motor no ha
> producido nunca un `causa_probable` real, así que no hay ningún caso
> contra el que validar esa vía todavía. El único tipo de acción de
> esta primera feature: rotar (nunca borrar) un log que ha crecido por
> encima de un umbral sin que nada lo rote — problema real y activo
> hoy mismo. No incluye ningún otro tipo de acción del barrido de
> agosto. No incluye notificar por Telegram ni mostrar nada en el
> dashboard — el CLI es la única superficie.

---

## Feature 020 — material de partida (2026-08-13): visor de remediación en el dashboard

Con 019 cerrado y `LOGS_VIGILADOS` ampliado a 17 logs, Miquel pidió
ver esa lista con sus tamaños en el dashboard — la primera superficie
visual para el Frente 2 de remediación (FR-014 de 019 dejó
explícitamente el CLI como única interfaz en v1; este feature la
amplía, no la contradice).

**Hallazgo real que cambia la arquitectura, encontrado antes de
diseñar nada**: el contenedor `homelab-dashboard` **no monta**
`~/Library/Logs/` — comprobado en `docker-compose.yml` (solo monta
`/data`, `~/.hermes`, `/Volumes/FastData` y `/Volumes/Storage`). El
dashboard nunca ha podido leer esos ficheros directamente, y no es
razonable que empiece ahora tocando ese volumen sin más.

**Decisión, confirmada con Miquel (`AskUserQuestion`)**: mismo patrón
ya establecido en todo el homelab (`dump_socat_status.py`,
`docker_monitor.py`) — un proceso en el host escribe un JSON a `/data`
(ya montado), el dashboard solo lee ese JSON. Concretamente:

- `remediacion.cli comprobar` escribe, además de lo que ya hacía, un
  snapshot JSON con el estado de los 17 logs vigilados (tamaño actual,
  umbral, si está por encima, y el modo vigente de `rotar_log`).
- LaunchAgent nuevo, `amsterdam9.remediacion.comprobar`, que ejecuta
  `comprobar` cada 15 min — mismo cadencia que otros monitores
  ligeros del homelab (`ha_monitor.py`). No cambia el modo por
  defecto de `rotar_log` (sigue en manual); en automático, este cron
  sería el que dispara la ejecución real, exactamente para eso sirve
  el interruptor.
- `app.py` (dashboard) lee ese JSON de solo lectura, mismo patrón que
  `get_socat_relays()`/`get_external_hosts()`.

**Alcance propuesto (borrador, para `/speckit-plan`):**

| Pieza | Dentro / Fuera |
|---|---|
| `remediacion.cli comprobar` escribe el snapshot JSON | Dentro |
| LaunchAgent que dispara `comprobar` cada 15 min | Dentro (fuera de este repo) |
| Nueva sección en el dashboard con la lista de logs, tamaño, umbral y estado | Dentro (fuera de este repo) |
| Aprobar/rechazar/deshacer/cambiar modo desde el dashboard | Fuera — el CLI sigue siendo la única forma de actuar, esto es solo lectura |
| Notificación por Telegram si un log supera el umbral | Fuera — ya excluido en 019, sin cambios |
| Montar `~/Library/Logs` en el contenedor | Fuera — decisión explícita, mismo patrón JSON que el resto del homelab |

**Descripción de partida para `/speckit-specify`** (pegar tal cual o
adaptar):

> La feature 019 (remediación automática) dejó el CLI como única
> superficie. Quiero ver en el dashboard la lista de los 17 logs
> vigilados con su tamaño actual, su umbral y si están por encima —
> de solo lectura, sin poder actuar desde ahí. El contenedor del
> dashboard no tiene acceso a ~/Library/Logs, así que
> `remediacion.cli comprobar` escribe un snapshot JSON a /data (mismo
> patrón que el resto del homelab), y un LaunchAgent nuevo lo dispara
> cada 15 minutos. No incluye aprobar, rechazar, deshacer ni cambiar
> el modo desde el dashboard — solo lectura. No incluye notificación
> por Telegram.

---

## Método de trabajo

- **Miquel ejecuta** todas las skills y todos los comandos. El objetivo es que
  Miquel aprenda el método, no que Claude tenga el proyecto hecho.
- **Claude revisa** y prepara el material y los criterios antes de cada paso.
- Lo que hace que esto sea SDD de verdad es que **la especificación manda**: si
  el spec y el código no coinciden, eso es un defecto que hay que arreglar,
  aunque el spec lo haya escrito una persona.

Ver `METODO.md`, en esta misma carpeta, para el detalle de qué revisar en cada
artefacto y qué anotar en `BITACORA.md`.
