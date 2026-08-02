# Briefing — Agente de diagnóstico de incidencias

> Escrito el 31-07-2026, antes de la primera línea de código.
> Material de partida para `speckit-constitution` y `speckit-specify`.
> **Esto no es la especificación.** Es lo que se sabe antes de escribirla.

---

## Los dos vectores del proyecto

Todo lo que sigue se organiza en dos vectores. Conviene tenerlos separados desde
el principio porque tienen reglas distintas:

- **Vector 1 — Diagnóstico.** El contenedor que se ha reiniciado 49 veces sin
  causa conocida. Sigue sin diagnosticar.
- **Vector 2 — Cobertura del dashboard.** Que `http://homelab.amsterdam9.home/`
  muestre todas las alarmas reales, sin ausencias ni duplicados. Ya está
  diagnosticado.

**Qué.** Dos entregables, uno por vector:

1. **Vector 1:** un agente (grafo de LangGraph) que diagnostica incidencias de
   contenedores y, cuando la causa ya está diagnosticada, la corrige dentro de una
   lista cerrada de acciones reversibles.
2. **Vector 2:** ampliar el dashboard del homelab para que muestre **todas las
   alarmas reales posibles**. Es el Principio XII de la constitución, y es un
   objetivo tan importante como el primero — no un efecto secundario de
   diagnosticar.

**Por qué.** Hay dos problemas sin resolver, y son de tipo distinto.

Vector 1: un contenedor se ha reiniciado automáticamente 49 veces en siete
semanas, y no se sabe por qué. Se investigó a mano durante una sesión completa, se
descartaron dos posibles causas, y no se encontró la verdadera. El sistema actual
sabe *reiniciar* un contenedor, pero no sabe *explicar* por qué falló.

Vector 2, encontrado en el barrido del 01-08-2026 (`BARRIDO-2026-08-01.md`): el
dashboard no mostró ninguno de los 11 problemas reales que hubo ese día. No es un
problema de demasiadas alertas — es que faltan alertas. El sistema genera avisos
que nunca llegan a la pantalla, o que llegan duplicados y se descartan. A
diferencia del Vector 1, aquí ya se sabe la causa (la deduplicación está mal
hecha, y no hay una definición de qué es "normal") y el arreglo es directo.

**Para quién.** Para Miquel, que gestiona su propia infraestructura. Es un solo
usuario: no hace falta pensar en varios usuarios ni en garantías de disponibilidad.
En segundo lugar, para quien lea el caso de estudio público: este proyecto
continúa el repositorio público del homelab.

**Cómo.** Un grafo de LangGraph que, cuando ocurre un evento:

1. Detecta el error.
2. Formula posibles causas y las comprueba una a una contra el sistema.
3. Si la causa ya está diagnosticada y la corrección está en la lista de acciones
   reversibles permitidas, la aplica.
4. Si no puede —porque se queda sin ideas, o porque la acción sería peligrosa— se
   lo dice a Miquel.

**Cuándo.** Sin fecha límite. Es un proyecto largo. El ritmo lo marcan los
artefactos de Spec Kit (constitution, spec, plan, tasks), no un calendario.

---

## Vector 1 — Diagnóstico del contenedor

Los hechos:

- El mismo contenedor se ha reiniciado automáticamente 49 veces, sin causa
  conocida.
- Esos 49 reinicios son el **59% de todas las intervenciones automáticas** del
  sistema (49 de 83 en total).
- **Nunca llegó una alerta.** La regla era "avisar solo cuando cambia el estado",
  así que cada reinicio se registraba como un simple mensaje de recuperación, y
  nadie se enteraba.
- La investigación manual descartó dos explicaciones posibles y no encontró una
  tercera.

El problema sigue ahí hoy. No hace falta debatir si esto es un "hecho observado" o
una "hipótesis" — lo que hace falta es construir el flujo de siempre: **detectar
el error, intentar corregirlo con el grafo de LangGraph dentro de lo que tiene
permitido, y si no puede, avisar a Miquel.**

### Lo que la investigación manual ya descartó

**Flapeo** (que el contenedor se caiga muy a menudo, de forma inestable).
Descartado. No es un goteo continuo: son **seis episodios** claramente separados,
con semanas de estabilidad total entre uno y otro. Entre el 4 y el 16 de abril no
pasó nada.

**Falta de recursos (memoria).** Descartado. La memoria media usada era de 23 MB,
muy poco. Además, en dos horas concretas las métricas muestran **0,0 MB durante
doce muestras seguidas**, justo mientras el sistema registraba cuatro reinicios
"con éxito" en ese mismo rato. Ese 0,0 no significa que el contenedor usara poca
memoria: significa que el contenedor ni siquiera estaba ahí.

**La pauta en el tiempo, que sigue sin explicación.** Los reinicios llegan en
ráfagas de tres, en ciclos seguidos del monitor (cada 5 minutos), y luego hay una
calma de unos cincuenta minutos antes de que se repita. La mediana entre un
reinicio y el siguiente es de 12 minutos. 44 de los 48 intervalos entre reinicios
duran menos de una hora.

Cincuenta minutos es un número raro, demasiado regular para ser casualidad.
Todavía nadie ha comprobado si alguna tarea del sistema se ejecuta justo con ese
periodo.

## Vector 2 — Cobertura del dashboard, ya diagnosticada

Este problema es distinto y conviene no mezclarlo con el Vector 1. El barrido del
01-08-2026 no dejó ninguna pregunta sin responder sobre por qué fallaba cada caso:
dejó una lista de causas ya conocidas.

- La deduplicación de alertas descarta avisos reales mientras el problema sigue
  activo. Ejemplo: 2.833 alertas de una entidad y 49 reinicios de otra, todos
  silenciados.
- No existe una definición de "cómo debería estar" cada cosa. Sin eso, el sistema
  no puede distinguir entre algo apagado a propósito (como `frigate`) y algo roto
  de verdad.
- Hay fallos que no dan ninguna señal hasta que ocurre otra cosa —por ejemplo,
  unos ficheros de configuración corruptos que solo fallarán en el próximo
  reinicio del sistema—. El dashboard solo mira el estado actual, así que no los
  ve.

Nada de esto requiere formular una hipótesis y comprobarla contra el sistema: la
causa de cada caso ya se conoce y está escrita en `BARRIDO-2026-08-01.md`. Es una
lista de tareas de ingeniería, no un problema de diagnóstico. Por eso el criterio
de muerte (más abajo) no le aplica a este vector.

---

## Qué existe ya, y que el agente NO debe sustituir

`docker_monitor.py` corre cada cinco minutos y funciona bien. Clasifica los 41
contenedores en tres grupos: **CRITICAL** (si falla, avisa, pero no lo toca),
**NEVER_RESTART** (lo ignora) y el resto (lo reinicia y, a los 10 segundos,
comprueba que siga funcionando). Además tiene un límite de seguridad: si falla 3
veces en 6 horas, deja de intentarlo.

**El agente se añade a esto, no lo reemplaza.** El monitor seguirá siendo quien
reinicie los contenedores — eso no cambia. Lo que el agente aporta es lo que hoy
no existe: explicar *por qué* pasó algo (Vector 1), y corregir —dentro de una
lista cerrada de acciones reversibles— lo que el barrido ya diagnosticó y que el
monitor no toca, como la deduplicación, los ficheros corruptos o la rotación de
logs (Vector 2). Ninguna de las dos cosas sustituye al monitor, y ninguna actúa
sobre contenedores críticos.

Por qué importa esto: si el agente reemplazara al monitor y el agente fallara, se
perdería la remediación automática que lleva meses funcionando bien. Un
componente nuevo y experimental no puede poner en riesgo algo que ya funciona.

---

## Principios candidatos para la constitución

Escritos para que se puedan incumplir de forma comprobable — si un principio no se
puede señalar como incumplido en el código, no sirve. No son definitivos: son el
material de partida para `speckit-constitution`.

**1 · Ninguna acción sobre un contenedor crítico sin aprobación humana explícita.
NO NEGOCIABLE.** La lista de críticos es la que ya usa el monitor. Si toca a uno
de esos, el grafo se detiene y espera; no pide permiso y sigue adelante por su
cuenta.

**2 · El agente diagnostica; el monitor sigue actuando.** Ninguna parte del grafo
puede dejar al sistema sin la remediación automática que ya existe.

**3 · Toda hipótesis se registra, con su comprobación y su resultado.** Si una
hipótesis se descarta sin dejar constancia de cómo se descartó, se acabará
formulando otra vez. El registro es parte del producto, no un simple log.

**4 · Nada cuenta como mejora hasta que se compara con la línea base.** La línea
base es el comportamiento actual sobre los 83 episodios históricos. Sin ese
número de referencia, ninguna afirmación de "esto ha mejorado" entra en la
documentación.

**5 · Local por defecto.** Los datos son de infraestructura privada: rutas,
nombres de host, salidas de diagnóstico. Cualquier parte que salga de la máquina
necesita una justificación explícita, caso por caso, en el spec.

**6 · Todo diagnóstico tiene que poder reproducirse en diferido.** Si una
conclusión solo se puede alcanzar con el sistema en vivo, no cuenta: no es posible
evaluarla.

---

## Criterio de muerte

**Aplica solo al Vector 1** (los 49 reinicios sin causa conocida). Hay que
comprobarlo **antes** de escribir código de agente para este vector:

> Coger cinco episodios históricos, reconstruir a mano qué evidencia había
> disponible en cada uno, y comprobar si **esa evidencia basta para distinguir un
> episodio de otro**.

Si ni siquiera un humano, con todos los datos delante, puede decir qué pasó, el
problema no es de razonamiento, es de **falta de instrumentación**. En ese caso lo
que hace falta es recoger más información —logs del contenedor, eventos de
Docker, cruzarlo con las tareas programadas— y no construir un agente. Construir
un grafo sobre evidencia insuficiente solo produce hipótesis que suenan bien pero
no se pueden comprobar, y eso es peor que no tener nada.

Es la misma lección del proyecto anterior, aplicada esta vez antes de empezar, no
después.

**No aplica al Vector 2** (cobertura del dashboard y arreglar lo que ya
diagnosticó el barrido). Ahí no hay ninguna hipótesis que comprobar contra
evidencia insuficiente: la causa de cada hallazgo ya está escrita. Aplicar el
mismo chequeo ahí sería resolver un problema que no existe.

---

## En alcance ahora

- **Diagnosticar el Vector 1** (el contenedor de los 49 reinicios), pero solo
  después de pasar el criterio de muerte.
- **Cobertura y precisión del dashboard** (`http://homelab.amsterdam9.home/`, Vector
  2): que toda alarma real activa aparezca, una sola vez, sin que falte ninguna
  (Principio XII de la constitución).
- **Corregir, de forma reversible, lo que el barrido ya diagnosticó** — la
  deduplicación, los ficheros corruptos, la rotación de logs, los logs guardados
  en `/tmp`, los healthchecks que faltan — dentro de una lista cerrada de acciones
  reversibles, cada una con su forma documentada de deshacerla (Principios V y
  VI). Esto es nuevo respecto a la versión anterior de este briefing: antes,
  "actuar" estaba fuera de alcance sin excepciones; ahora lo está solo para el
  Vector 1, que sigue sin diagnosticar.

## Fuera de alcance en la primera versión

- **Actuar sobre el Vector 1 mientras siga sin diagnosticar.** Mientras la causa
  de los 49 reinicios no pase el criterio de muerte, el agente no actúa sobre ese
  contenedor: solo propone qué podría hacerse.
- **Cualquier acción sobre contenedores críticos** (la lista del monitor), esté
  diagnosticado o no el problema. Ahí siempre se detiene y espera que Miquel lo
  apruebe.
- Diagnosticar Home Assistant y los relays. Es otro terreno, con otras fuentes de
  información.
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
datos propia, no de un tercero. Aquí no aplica la regla del proyecto anterior de
"usar siempre la API, nunca la base de datos": aquel esquema era de Immich y
cambiaba con cada actualización de la app; este lo controla Miquel y no va a
cambiar por sorpresa.

**La entrega es por Telegram**, como el resto de las automatizaciones del
homelab. No hace falta construir una interfaz nueva.

**El dashboard ya existe, no se construye uno nuevo.** El Vector 2 se resuelve
arreglando qué llega y cómo se deduplica en `http://homelab.amsterdam9.home/`,
que ya está ahí.

---

## Método de trabajo

El mismo que en el proyecto anterior, que funcionó bien:

- **Miquel ejecuta** todas las skills y todos los comandos. El objetivo es que
  Miquel aprenda el método, no que Claude tenga el proyecto hecho.
- **Claude revisa** y prepara el material y los criterios antes de cada paso.
- Lo que hace que esto sea SDD de verdad es que **la especificación manda**: si el
  spec y el código no coinciden, eso es un defecto que hay que arreglar, aunque el
  spec lo haya escrito una persona.

Ver `METODO.md`, en esta misma carpeta, para el detalle de qué revisar en cada
artefacto y qué anotar en `BITACORA.md`.

---

## Orden inmediato

1. ~~`specify init --here --integration claude`~~ — hecho.
2. ~~Leer los `SKILL.md` de `constitution`, `specify` y `clarify`~~ — hecho.
3. ~~`speckit-constitution`~~ — hecho, versión 1.1.2. Incluye el Principio XII
   (precisión del dashboard) y deja claro que el alcance permite ejecutar, no
   solo proponer, sobre causas ya diagnosticadas. Los dos se añadieron después de
   incorporar el Vector 2.
4. **Pendiente.** Sigue yendo antes que `specify`, pero solo afecta al Vector 1:
   el criterio de muerte sobre los 49 reinicios. Coger cinco episodios de
   `restart_history`, reconstruir a mano qué evidencia había, y ver si basta para
   distinguirlos. El Vector 2 (dashboard y corrección de lo diagnosticado) no
   necesita este paso: puede alimentar `speckit-specify` ya.
5. `speckit-specify`, usando este briefing como base.

Sigue sin tener sentido escribir una especificación para diagnosticar algo que,
con la evidencia actual, resulte imposible de diagnosticar. Por eso el paso 4
sigue pendiente para el Vector 1. El Vector 2 no depende de eso.
