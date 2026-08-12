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
| **3 · Beszel no vigila bien lo que vigila** | El propio Beszel —la herramienta que vigila CPU/memoria/disco de otras máquinas— muestra 2 de sus 3 sistemas en rojo (`AdGuardHome`, `UptimeKuma`). Solo `Mac Mini Server` en verde. | **Sin investigar todavía.** Visto el 06-08-2026. No se sabe si es un fallo real de esos sistemas, un fallo de la propia conexión de Beszel, o algo ya sabido y sin resolver (Uptime Kuma cambió de IP el 04-08 y no tiene reserva DHCP fija). |
| **4 · Recordatorios de Nextcloud** | Los recordatorios de Tareas/Calendario de Nextcloud, que deberían avisar por Telegram, no llegan. | **Sin investigar todavía.** Reportado por Miquel. No se sabe si falla el propio Nextcloud, el puente a Telegram, o la configuración del recordatorio. |

Los casos 1 y 2 ya se investigaron a fondo — el resto de este documento explica
qué se encontró. Los casos 3 y 4 son nuevos y todavía no se han investigado.

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

## Método de trabajo

- **Miquel ejecuta** todas las skills y todos los comandos. El objetivo es que
  Miquel aprenda el método, no que Claude tenga el proyecto hecho.
- **Claude revisa** y prepara el material y los criterios antes de cada paso.
- Lo que hace que esto sea SDD de verdad es que **la especificación manda**: si
  el spec y el código no coinciden, eso es un defecto que hay que arreglar,
  aunque el spec lo haya escrito una persona.

Ver `METODO.md`, en esta misma carpeta, para el detalle de qué revisar en cada
artefacto y qué anotar en `BITACORA.md`.
