# Briefing — Agente de diagnóstico de incidencias

> Escrito el 31-07-2026, antes de la primera línea de código.
> Material de partida para `speckit-constitution` y `speckit-specify`.
> **Esto no es la especificación.** Es lo que se sabe antes de escribirla.

---

## Las cinco preguntas

**Por qué.** Hay dos problemas sin resolver, y no son del mismo tipo.

El primero: un contenedor acumuló 49 reinicios automáticos en siete semanas y nadie
sabe por qué. Se investigó a mano durante una sesión completa, se descartaron dos
hipótesis, y no salió. El sistema actual sabe *reiniciar*; no sabe *averiguar*.

El segundo, encontrado en el barrido del 01-08-2026 (`BARRIDO-2026-08-01.md`): el
dashboard (`http://homelab.amsterdam9.home/`) no mostró ninguno de los 11 problemas
reales detectados ese día. No es un problema de ruido, es de cobertura — hay alarmas
que el propio sistema genera y que nunca llegan a la pantalla, o que llegan
duplicadas y se descartan. A diferencia del primero, este tiene causa conocida
(deduplicación mal hecha, ausencia de estado esperado declarado) y arreglo directo.

**Para quién.** Para Miquel, operando su propia infraestructura. Un solo usuario,
sin requisitos de multi-tenancy, sin SLA. Y de forma secundaria, para quien lea el
caso de estudio: es la continuación natural del repositorio público del homelab.

**Cómo.** Un grafo de LangGraph que, ante un evento: detecta el error, formula
hipótesis y las comprueba una a una contra el sistema, intenta corregirlo cuando la
causa ya está diagnosticada y la acción está en la lista cerrada de reversibles, y
si no puede —porque se queda sin ideas o porque la acción es peligrosa— se lo
reporta a Miquel.

**Cuándo.** Sin límite de tiempo. Es el proyecto largo. Los hitos los marcan los
artefactos de Spec Kit, no el calendario.

---

## La premisa

- 49 reinicios automáticos de un mismo contenedor, sin causa raíz conocida.
- Ese contenedor representa el **59% de todas las intervenciones automáticas** del
  sistema (49 de 83).
- **Nunca llegó una sola alerta.** La lógica de "notificar solo en el cambio de
  estado" convertía cada episodio en un mensaje de recuperación, que no dispara
  ninguna alarma mental.
- La investigación manual descartó dos explicaciones y no encontró una tercera.

El problema existe hoy y molesta hoy. No hace falta discutir si esto es un "hecho
observado" o una "hipótesis" — lo que hace falta es el flujo de siempre: **detectar
el error, intentar corregirlo con el grafo de LangGraph dentro de lo que tiene
permitido, y si no puede, reportárselo a Miquel.**

### Lo que la investigación manual ya descartó

**Flapeo (contenedor inestable que se cae a menudo).** Descartado. No es un goteo:
son **seis episodios discretos** separados por semanas de estabilidad total. Entre
el 4 y el 16 de abril no ocurrió absolutamente nada.

**Agotamiento de recursos.** Descartado. Memoria media de 23 MB. Además, las
agregaciones horarias muestran **0,0 MB durante doce muestras consecutivas** en dos
horas en las que el sistema de recuperación registró cuatro reinicios "con éxito".
Ese 0,0 no es un contenedor consumiendo poco: es un contenedor que no estaba ahí.

**La estructura temporal, que sigue sin explicación:** ráfagas de tres reinicios en
ciclos consecutivos del monitor (5 minutos), separadas por unos cincuenta minutos de
calma, repitiéndose. Mediana entre reinicios consecutivos: 12 minutos. 44 de 48
intervalos por debajo de una hora.

Cincuenta minutos es un número sospechosamente regular. Nadie ha buscado todavía qué
tarea del sistema tiene ese periodo.

### La segunda premisa: cobertura del dashboard, ya diagnosticada

Este problema es de otra naturaleza y conviene no mezclarlo con el anterior. El
barrido del 01-08-2026 no dejó ninguna pregunta abierta sobre *por qué* fallaba cada
caso — dejó una lista de causas conocidas:

- La deduplicación de alertas se come avisos reales mientras la condición persiste
  (2.833 alertas de una sola entidad, 49 reinicios de otra, ambos silenciados).
- No existe una capa de estado esperado: sin ella, lo intencionado (p. ej. `frigate`
  parado) y lo roto son indistinguibles para el sistema.
- Hay fallos latentes (plists corruptos) que no producen síntoma hasta el próximo
  reinicio, y el dashboard solo mira el estado actual.

Nada de esto requiere formular una hipótesis y contrastarla contra el sistema: la
causa ya se conoce, está escrita en `BARRIDO-2026-08-01.md`. Es una lista de tareas
de ingeniería, no un problema de diagnóstico. Por eso el criterio de muerte (más
abajo) no le aplica.

---

## Qué existe ya, y que el agente NO debe sustituir

`docker_monitor.py` corre cada cinco minutos y funciona. Lista 41 contenedores,
clasifica en **CRITICAL** (alerta, no toca), **NEVER_RESTART** (ignora) y el resto
(reinicia y **verifica a los 10 segundos** que sigue corriendo). Tiene cortacircuitos:
3 intentos en 6 horas y se detiene.

**El agente se añade, no reemplaza.** El monitor seguirá siendo quien reinicie
contenedores — eso no cambia. Lo que el agente añade son dos cosas que hoy no
existen: explicar *por qué* pasó algo (primera premisa) y remediar, dentro de una
lista cerrada y reversible, lo que el barrido ya diagnosticó y el monitor no toca
—dedup, plists, rotación de logs— (segunda premisa). Ninguna de las dos rutas
sustituye al monitor ni actúa sobre contenedores críticos.

Motivo: si el agente sustituye al monitor y el agente falla, se pierde la
remediación automática que lleva meses funcionando. Un componente experimental no
puede estar en el camino crítico de la fiabilidad.

---

## Principios candidatos para la constitución

Redactados para ser **falsables** — se debe poder señalar código que los incumple.
No son definitivos: son la materia prima de `speckit-constitution`.

**1 · Ninguna acción sobre un contenedor crítico sin aprobación humana explícita.
NO NEGOCIABLE.** La lista de críticos es la del monitor. El grafo debe detenerse y
esperar, no pedir permiso y continuar.

**2 · El agente diagnostica; el monitor sigue actuando.** Ninguna ruta del grafo
puede dejar al sistema sin la remediación automática existente.

**3 · Toda hipótesis se registra con su comprobación y su desenlace.** Una hipótesis
descartada sin dejar rastro de cómo se descartó es una hipótesis que se volverá a
formular. El registro es parte del producto, no un log.

**4 · Nada es mejor hasta que se mide contra la línea base.** La línea base es el
comportamiento actual sobre los 83 episodios históricos. Sin ese número, ninguna
afirmación de mejora entra en la documentación.

**5 · Local por defecto.** Son datos de infraestructura privada: rutas, nombres de
host, salidas de diagnóstico. Cualquier componente que salga de la máquina se
justifica explícitamente en el spec, caso por caso.

**6 · Todo diagnóstico debe ser reproducible en diferido.** Si una conclusión solo
puede alcanzarse con el sistema en vivo, no es evaluable y no cuenta.

---

## Criterio de muerte

**Aplica solo a la primera premisa** (los 49 reinicios sin causa conocida). Se
comprueba **antes** de escribir código de agente para esa parte:

> Coger cinco episodios históricos, reconstruir a mano qué evidencia había disponible
> en cada uno, y comprobar que **la evidencia basta para distinguirlos**.

Si con todos los datos delante un humano tampoco puede decir qué pasó, el problema
no es de razonamiento: es de **instrumentación**. En ese caso lo que hace falta es
recoger más señal —logs del contenedor, eventos de Docker, correlación con tareas
programadas— y no un agente. Construir un grafo sobre evidencia insuficiente produce
un generador de hipótesis plausibles e incontrastables, que es peor que nada.

Es la misma lección del proyecto anterior, aplicada antes en vez de después.

**No aplica a la segunda premisa** (cobertura del dashboard y remediación de la
lista ya diagnosticada del barrido). Ahí no hay hipótesis que contrastar contra
evidencia insuficiente: la causa de cada hallazgo ya está escrita. Exigir el mismo
chequeo ahí sería aplicar la solución a un problema que no tiene.

---

## En alcance ahora

- **Diagnóstico de la primera premisa** (el contenedor de los 49 reinicios), sujeto
  al criterio de muerte antes de escribir código de agente para esta parte.
- **Cobertura y precisión del dashboard** (`http://homelab.amsterdam9.home/`): toda
  alarma real activa, una sola vez, sin ausencias (Principio XII de la constitución).
- **Remediación reversible de la lista ya diagnosticada del barrido** — dedup,
  plists corruptos, rotación de logs, logs en `/tmp`, healthchecks — dentro de la
  lista cerrada de acciones reversibles con rollback escrito (Principios V y VI).
  Esto es nuevo respecto a la versión anterior de este briefing: antes "actuar"
  estaba fuera de alcance sin matices; ahora lo está solo para lo que sigue sin
  diagnosticar.

## Fuera de alcance en la primera versión

- **Actuar sobre lo que sigue sin diagnosticar.** Mientras la causa de los 49
  reinicios no pase el criterio de muerte, el agente no actúa sobre ese contenedor:
  solo propone.
- **Cualquier acción sobre contenedores críticos** (lista del monitor), diagnosticada
  o no. Ahí siempre se detiene y espera aprobación humana explícita.
- Diagnóstico de Home Assistant y de los relays. Otro dominio, otras fuentes.
- Cualquier incidencia que el monitor actual ya resuelva sin ayuda.

---

## Decisiones ya tomadas

**Repositorio público.** Contiene rutas, nombres de contenedores y salidas de
diagnóstico reales, saneados con la política de siempre: **se nombra el software,
no la topología** — no van datos de seguridad física (p. ej. entidades atadas a una
cerradura real) ni credenciales. Decidirlo ahora es gratis; decidirlo tras tres
meses de commits significa reescribir el historial.

**Acceso a los datos por consulta directa a SQLite**, que es una base de datos
propia y no la de un tercero. No aplica aquí la regla de "la API, nunca la base de
datos" del proyecto anterior: aquel esquema era de Immich y cambiaba con cada
actualización; este lo controla Miquel.

**Entrega por Telegram**, coherente con el resto del homelab. Sin interfaz nueva.

**Dashboard existente, no interfaz nueva.** La cobertura de alarmas (segunda
premisa) se resuelve arreglando qué llega y cómo se deduplica en
`http://homelab.amsterdam9.home/`, que ya existe. No se construye una pantalla
nueva.

---

## Método de trabajo

El mismo del proyecto anterior, que funcionó:

- **Miquel ejecuta** todas las skills y todos los comandos. El objetivo es aprender
  el método, no tener el proyecto.
- **Claude revisa** y aporta el material y los criterios antes de cada paso.
- Lo que define a SDD es que **la especificación sea vinculante**: que una
  divergencia entre lo que dice el spec y lo que hace el código se trate como un
  defecto. No que la escriba un humano.

Ver `METODO.md`, en esta misma carpeta, para el detalle de qué mirar en cada
artefacto y qué métricas anotar en el `BITACORA.md`.

---

## Orden inmediato

1. ~~`specify init --here --integration claude`~~ — hecho.
2. ~~Leer los `SKILL.md` de `constitution`, `specify` y `clarify`~~ — hecho.
3. ~~`speckit-constitution`~~ — hecho, v1.1.2. Incluye el Principio XII (precisión
   del dashboard) y el alcance corregido para autorizar ejecución, no solo
   propuesta, sobre causas ya diagnosticadas — ambos añadidos tras acordar la
   segunda premisa.
4. **Pendiente — sigue yendo antes que `specify`, pero acotado a la primera
   premisa**: el criterio de muerte sobre los 49 reinicios. Cinco episodios de
   `restart_history`, evidencia disponible reconstruida a mano, ¿bastaría para
   distinguirlos? La segunda premisa (dashboard + remediación diagnosticada) no
   necesita este paso y puede alimentar `speckit-specify` sin esperar.
5. `speckit-specify`, alimentado por este briefing.

Sigue sin tener sentido especificar el diagnóstico de algo que resulte
indiagnosticable con la evidencia actual — de ahí que el paso 4 siga pendiente para
esa mitad. La otra mitad (dashboard y remediación) no tiene esa dependencia.
