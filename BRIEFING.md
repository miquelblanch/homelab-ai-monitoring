# Briefing — Monitorización completa del homelab

> Escrito el 31-07-2026, revisado el 02-08-2026, antes de la primera línea de código.
> Material de partida para `speckit-constitution` y `speckit-specify`.
> **Esto no es la especificación.** Es lo que se sabe antes de escribirla.

---

## El objetivo, dicho sin rodeos

Este proyecto no nació para explicar por qué un contenedor se reinició 49 veces,
ni para arreglar cuatro casos concretos uno por uno. Nació de investigar el
primero, pero se hizo evidente algo más grande: **la monitorización del homelab
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
  esperado declarado? ¿se vigila? ¿si falla, se sabría?". El barrido del
  01-08-2026 hizo esto sobre 86 puntos del dashboard y Home Assistant; hace
  falta extenderlo a todo lo demás (Beszel y lo que Beszel vigila, las
  integraciones con Nextcloud, y lo que aparezca).
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

### Lo que la investigación manual ya descartó

**Flapeo** (que el contenedor se caiga muy a menudo, de forma inestable).
Descartado. No es un goteo continuo: son **cinco episodios** claramente
separados, con semanas de estabilidad total entre uno y otro.

**Falta de recursos (memoria).** Descartado. La memoria media usada era de 23
MB, muy poco. Además, en dos horas concretas las métricas muestran **0,0 MB
durante doce muestras seguidas**, justo mientras el sistema registraba cuatro
reinicios "con éxito" en ese mismo rato. Ese 0,0 no significa que el contenedor
usara poca memoria: significa que el contenedor ni siquiera estaba ahí.

**La pauta en el tiempo, que sigue sin explicación.** Los reinicios llegan en
ráfagas, separadas por calmas de entre cincuenta minutos y semanas. No hay un
periodo regular identificado.

### Criterio de muerte: comprobado, y no lo pasa

Antes de construir un agente que diagnostique este caso, se comprobó si la
evidencia disponible basta:

> Coger cinco episodios históricos, reconstruir a mano qué evidencia había
> disponible en cada uno, y comprobar si esa evidencia basta para distinguir un
> episodio de otro.

Resultado, con los 5 episodios reales de `restart_history`: **3 de los 5 no
tienen ningún dato más allá de la marca de tiempo** — ocurrieron antes de que
empezara la serie de métricas horarias (2026-04-17). De los 2 que sí tienen
contexto, uno muestra que el contenedor estuvo completamente ausente 2 horas
justo después de varios reinicios marcados "success" (coherente con que, antes
del 26-07-2026, "success" solo significaba que el comando de reinicio devolvió
0, no que el contenedor siguiera vivo después); el otro no muestra ninguna
anomalía.

Con eso delante, ni una persona podría decir por qué se reinició beszel esas 49
veces. **El problema no es de razonamiento, es de instrumentación.** Por eso
este caso concreto no se persigue como una causa raíz que resolver: se usa como
la prueba de que el sistema necesita vigilar mejor, que es el objetivo real de
este proyecto.

---

## Qué existe ya, y que el agente NO debe sustituir

`docker_monitor.py` corre cada cinco minutos y funciona bien. Clasifica los 41
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

## Método de trabajo

- **Miquel ejecuta** todas las skills y todos los comandos. El objetivo es que
  Miquel aprenda el método, no que Claude tenga el proyecto hecho.
- **Claude revisa** y prepara el material y los criterios antes de cada paso.
- Lo que hace que esto sea SDD de verdad es que **la especificación manda**: si
  el spec y el código no coinciden, eso es un defecto que hay que arreglar,
  aunque el spec lo haya escrito una persona.

Ver `METODO.md`, en esta misma carpeta, para el detalle de qué revisar en cada
artefacto y qué anotar en `BITACORA.md`.

---

## Orden inmediato

1. ~~`specify init --here --integration claude`~~ — hecho.
2. ~~Leer los `SKILL.md` de `constitution`, `specify` y `clarify`~~ — hecho.
3. ~~`speckit-constitution`~~ — hecho, versión 1.1.2.
4. ~~Criterio de muerte sobre los 49 reinicios de beszel~~ — hecho. No lo pasa:
   confirma que perseguir esa causa raíz concreta no es el camino, y que el
   objetivo real es ampliar la cobertura de monitorización.
5. **Pendiente, y va antes que `specify`:** el inventario sistemático de
   cobertura — recorrer todo el homelab, no solo los casos 3 y 4, y para cada
   pieza comprobar si tiene estado esperado, si se vigila, y si un fallo se
   sabría. Los casos 3 y 4 son el punto de partida, no el destino: sirven para
   validar el método antes de aplicarlo a todo lo demás.
6. `speckit-specify`, usando este briefing y el inventario como base.
