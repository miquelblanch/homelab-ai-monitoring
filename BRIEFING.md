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
     (`192.168.4.87:5540/5541`), vigilados en `dump_socat_status.py`.
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

## Método de trabajo

- **Miquel ejecuta** todas las skills y todos los comandos. El objetivo es que
  Miquel aprenda el método, no que Claude tenga el proyecto hecho.
- **Claude revisa** y prepara el material y los criterios antes de cada paso.
- Lo que hace que esto sea SDD de verdad es que **la especificación manda**: si
  el spec y el código no coinciden, eso es un defecto que hay que arreglar,
  aunque el spec lo haya escrito una persona.

Ver `METODO.md`, en esta misma carpeta, para el detalle de qué revisar en cada
artefacto y qué anotar en `BITACORA.md`.
