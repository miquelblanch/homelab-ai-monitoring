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

## Método de trabajo

- **Miquel ejecuta** todas las skills y todos los comandos. El objetivo es que
  Miquel aprenda el método, no que Claude tenga el proyecto hecho.
- **Claude revisa** y prepara el material y los criterios antes de cada paso.
- Lo que hace que esto sea SDD de verdad es que **la especificación manda**: si
  el spec y el código no coinciden, eso es un defecto que hay que arreglar,
  aunque el spec lo haya escrito una persona.

Ver `METODO.md`, en esta misma carpeta, para el detalle de qué revisar en cada
artefacto y qué anotar en `BITACORA.md`.
