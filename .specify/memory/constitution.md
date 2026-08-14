<!--
## Sync Impact Report

**Version change**: 1.2.4 → 2.0.0
**Principles added**: None
**Principles modified**: **Principio VII (Un Actor por Acción)** — redefinición
incompatible con la versión anterior (MAJOR): la garantía de independencia
("DEBE seguir funcionando con independencia del estado del agente") ya no cubre
sin condiciones "la remediación automática existente" al completo — se acota
explícitamente a los **contenedores críticos**, donde `docker_monitor.py` ya
solo alertaba (nunca reiniciaba) y sigue haciendo exactamente eso. Para los no
críticos, desde el feature 021 (`specs/021-remediacion-contenedores/`), el
único actor responsable pasa a ser `remediacion` (DeepSeek decide,
`docker_monitor.py` ejecuta como biblioteca de bajo nivel) — es, literalmente,
lo que pidió Miquel al abrir la feature ("docker-monitor no tiene que hacer
nada" en la decisión de reparar; "que las reparaciones siempre las haga
deepseek"). La cesión se acepta solo junto con una contrapartida nueva: un
fallo persistente de esa capa para evaluar DEBE avisar, nunca quedar en
silencio (`specs/021-remediacion-contenedores/` FR-019, Principio I).
Detectado como conflicto real (no de redacción) por `/speckit-analyze` sobre
021 — el texto anterior de VII, sin acotar, hacía imposible que esa feature
procediera sin violar la constitución. Resuelto explícitamente con Miquel
(`AskUserQuestion`, 2026-08-14).
**Sections added**: None
**Sections removed**: N/A
**Sections clarified**: "Alcance y Límites" actualizada — el párrafo de
remediación automática ya no dice que `docker_monitor.py` es "el único
mecanismo que remedia contenedores" sin matices (quedó falso desde que 021 le
retira la decisión de reinicio de los no críticos); ahora distingue
explícitamente su rol para críticos (sin cambios) del rol para no críticos
(biblioteca invocada por `remediacion`). "No reemplaza" corregida en el mismo
sentido — ya no afirma que nada de `docker_monitor.py` se reemplaza, cuando
021 sí le retira una responsabilidad concreta y documentada.
**Deferred TODOs**: None
-->

# Homelab Diagnostic Agent Constitution

## Core Principles

### I. Alerta Persistente (NO NEGOCIABLE)

Ninguna alerta se silencia mientras la condición persista. Se puede espaciar la reemisión;
no se puede callar. Un sistema que silencia sus alertas no vigila: simula.

**Rationale**: Antes solo se avisaba al cambiar de estado, así que 49 reinicios reales no
generaron ni una alerta.

### II. Salud por Resultado

Un componente está sano solo si demuestra su último resultado, no su ejecución. Código de
salida y proceso vivo no son salud.

**Rationale**: Un proceso puede estar "vivo" y aun así fallar, o reportar datos vacíos porque
nunca llegó a arrancar. Solo el resultado dice si algo funciona de verdad.

### III. Estado Esperado Declarado

Todo lo vigilado tiene un estado esperado declarado explícitamente en el spec. Lo que no
tenga estado esperado declarado no se vigila. La declaración caduca y DEBE revisarse
periódicamente.

**Rationale**: Sin saber qué es "normal", vigilar solo genera ruido. Una declaración vieja
engaña igual que no tener ninguna.

### IV. Diagnóstico Previo a la Acción

Ninguna acción correctiva se ejecuta sin un diagnóstico que la justifique. El diagnóstico
DEBE identificar la causa probable antes de proponer la acción.

**Rationale**: Actuar sin diagnóstico repite el problema que originó este proyecto: reinicios
automáticos sin conocer la causa.

### V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE)

El agente actúa únicamente sobre la lista cerrada de acciones reversibles declarada en el
spec. Cualquier acción fuera de esa lista hace que el grafo se detenga y espere aprobación
humana explícita. El agente no puede ampliar esa lista por sí mismo en tiempo de ejecución.

**Rationale**: El agente es experimental y no debe poner en riesgo la fiabilidad existente. Se
añade al sistema, no lo sustituye.

### VI. Reversibilidad Escrita

Reversible significa que la vuelta atrás está documentada antes de ejecutar la acción. Una
acción sin procedimiento de rollback escrito no es reversible en el sentido de este principio.

**Rationale**: No basta con que deshacer algo sea "técnicamente posible": tiene que haber un
procedimiento escrito que alguien pueda seguir.

### VII. Un Actor por Acción

Una acción tiene un único actor responsable. Nadie remedia lo que ya remedia otro
componente.

Para los **contenedores críticos**, `docker_monitor.py` sigue siendo el único mecanismo
de vigilancia y aviso, y DEBE seguir funcionando con independencia del estado del agente
— nadie le retira ni le compite esa responsabilidad.

Para una acción que una capa de remediación con su propio diagnóstico asume
explícitamente (p. ej. `remediacion` decidiendo reinicios de contenedores no críticos
desde el feature 021, Principio IV), el único actor responsable pasa a ser esa capa —
`docker_monitor.py` se convierte en la biblioteca de bajo nivel que ejecuta la acción
(`restart_container()`, `breaker_decision()`), no en un actor independiente compitiendo
por el mismo contenedor. Esta cesión de responsabilidad exige una contrapartida
explícita, no implícita: un fallo persistente de la nueva capa para evaluar o actuar
(sin presupuesto, sin respuesta del modelo, etc.) DEBE avisar igual que cualquier otra
alarma (Principio I) — nunca un silencio indistinguible de "sigue vigilado" cuando ya no
lo está. El spec que hace la cesión DEBE declarar esa contrapartida explícitamente.

**Rationale**: Si el agente sustituyera al monitor y fallara sin que nadie se enterase, se
perdería la remediación que lleva meses funcionando sin ayuda de nadie — el motivo
original de este principio. Acotar la garantía a los críticos permite que una capa de
remediación más inteligente (que sí diagnostica antes de actuar, Principio IV) asuma
progresivamente responsabilidades sobre componentes no críticos, siempre que ceder esa
responsabilidad no cree un punto ciego nuevo: de ahí que la contrapartida del aviso
persistente no sea opcional.

### VIII. Registro de Acciones e Hipótesis

Toda acción ejecutada y toda hipótesis formulada DEBE registrarse con su justificación y su
desenlace. Una hipótesis descartada sin rastro de cómo se descartó es una hipótesis que se
volverá a formular.

**Rationale**: Sin registro, una hipótesis descartada se vuelve a probar más tarde. Poder
reconstruir qué se pensó y por qué es parte del producto, no un extra.

### IX. Mejora Medida Contra la Línea Base

Nada se considera una mejora hasta que se mide contra la línea base establecida. La línea
base es el barrido del 2026-08-01: 11 problemas reales detectados, invisibles al dashboard,
con 2 falsos positivos de 12 comprobaciones.

**Rationale**: Sin una cifra de referencia, "ha mejorado" es solo una opinión. El barrido del
2026-08-01 es esa cifra.

### X. Local por Defecto

Los datos de diagnóstico no salen de la máquina salvo justificación explícita caso por caso
en el spec. Rutas, nombres de contenedor y salidas de diagnóstico son infraestructura privada.

**Rationale**: Son datos reales de la red doméstica. Lo público puede nombrar el software
usado, nunca la topología real.

### XI. Reproducibilidad Diferida

Toda conclusión DEBE ser reproducible ejecutando el agente en diferido contra el mismo
episodio histórico. Una conclusión que solo puede alcanzarse con el sistema en vivo no es
evaluable.

**Rationale**: Si solo funciona en vivo, cada prueba exige esperar a que algo se rompa.
Separar la evidencia de su origen es lo que permite medir sin esperar.

### XII. Precisión del Dashboard (NO NEGOCIABLE)

El dashboard (`http://homelab.amsterdam9.home/`) DEBE reflejar en todo momento el conjunto
exacto de alarmas activas del sistema: cero duplicados, cero ausencias. Toda alarma real
generada por la capa de monitorización DEBE aparecer en el dashboard una única vez mientras
la condición que la origina persista, y DEBE dejar de aparecer cuando la condición se
resuelve. Una misma condición reportada por dos vías (por ejemplo, monitor y agente) cuenta
como una alarma, no como dos.

**Rationale**: El barrido de referencia ya encontró problemas invisibles al dashboard y
falsos positivos. Si duplica, se deja de mirar por ruido; si omite, se deja de confiar en él.

### XIII. Cobertura Sistemática, No Anecdótica

Ningún componente del homelab queda sin vigilar por el simple hecho de no haber
fallado todavía de forma visible. La cobertura se decide recorriendo
sistemáticamente qué existe —contenedores, integraciones, la propia
infraestructura de monitorización—, no reaccionando a lo que ya ha fallado. Todo
lo que se añada al homelab hereda esta misma obligación desde el momento en que
se añade.

**Rationale**: Los cuatro casos que dieron origen a este proyecto —los reinicios
de beszel, el barrido del 2026-08-01, Beszel sin vigilar bien sus propios
sistemas monitorizados, y los recordatorios de Nextcloud que no llegan por
Telegram— se encontraron por casualidad, en momentos y contextos distintos,
mirando cosas distintas cada vez. Si cuatro aparecieron sin buscarlos
activamente, parchear uno por uno nunca cierra el agujero real: hace falta un
método que no dependa de la suerte.

## Modelo Operacional

El agente opera bajo el **Modelo B**: actúa de forma autónoma únicamente en acciones
reversibles y de bajo riesgo definidas en la lista cerrada del spec. Todo lo demás es
propuesta que espera aprobación humana explícita.

El criterio de clasificación DEBE estar declarado en el spec antes de la implementación. Si
hay duda sobre si una acción es de bajo riesgo, se trata como de alto riesgo.

## Alcance y Límites

**En alcance**: cobertura sistemática de vigilancia sobre todo el homelab —no solo
contenedores Docker: también integraciones (p. ej. los recordatorios de Nextcloud) y la
propia infraestructura de monitorización (p. ej. qué vigila Beszel y si lo vigila bien)—,
formulación y contraste de hipótesis contra el historial de episodios, propuesta de
acciones correctivas, registro del razonamiento, y mantenimiento del dashboard
(`http://homelab.amsterdam9.home/`) como entregable del proyecto: toda alarma activa del
sistema DEBE quedar reflejada allí sin duplicados y sin ausencias (Principio XII). Para
causas ya diagnosticadas con certeza —no para lo que sigue en fase de hipótesis— el
alcance incluye también la **ejecución**, no solo la propuesta, de la acción correctiva,
siempre dentro de la lista cerrada de acciones reversibles con rollback escrito
(Principios V y VI) y bajo el Modelo Operacional B.

**Fuera de alcance en v1**: ejecución de acciones correctivas sobre contenedores críticos
(lista del monitor), cualquier incidencia que el monitor actual resuelva sin ayuda.

Los diez orígenes/mecanismos de la Central de Alarmas (contenedor, disco, Home Assistant,
backup, relay socat, inventario, host externo, hub de Beszel, agente, latido de monitores)
están en alcance de diagnóstico y generalizados desde el feature 017 — ver
`specs/007-diagnostico-episodios/` a `specs/017-diagnostico-latidos/`. El feature 018
generalizó, además, la superficie del dashboard (Principio XII) a esos mismos 10 orígenes
— antes solo contenedor era visible fuera de la línea de comandos.

La capa de **remediación automática** tiene su primer tipo de acción real desde el feature
019 (`specs/019-remediacion-automatica/`): `rotar_log`, sobre una lista cerrada de logs del
homelab, con interruptor manual/automático por tipo de acción controlado siempre por
Miquel (nunca autopromovido — Principio VII) y rollback escrito y verificado (Principio
VI). El feature 020 (`specs/020-visor-remediacion/`) hizo visible su estado en el
dashboard, de solo lectura.

El feature 021 (`specs/021-remediacion-contenedores/`) añade el segundo tipo de acción
real, `reiniciar_contenedor`, con una diferencia deliberada respecto a `rotar_log`: la
decisión de si aplica no es una condición fija, sino el juicio de DeepSeek sobre evidencia
real (Principio IV), dentro de la misma lista cerrada de acciones reversibles (Principio
V). Desde este feature, `docker_monitor.py` deja de decidir reinicios de contenedores no
críticos por su cuenta — pasa a ser la biblioteca de bajo nivel (`restart_container()`,
`breaker_decision()`) que `remediacion` invoca, no un actor independiente compitiendo por
el mismo contenedor (Principio VII, acotado desde esta versión). Para los contenedores
**críticos**, `docker_monitor.py` sigue siendo el único mecanismo — vigilancia, aviso y
exclusión explícita de cualquier reinicio automático o evaluación de DeepSeek — sin
ningún cambio introducido por 021 (FR-006 de esa feature). La cesión de responsabilidad
sobre los no críticos exige, como contrapartida no negociable del propio Principio VII, un
aviso explícito cuando `remediacion` lleva evaluaciones consecutivas sin poder decidir
(sin presupuesto, sin respuesta de DeepSeek) — nunca un silencio equivalente a "sigue
vigilado" cuando ya no lo está (FR-019 de 021).

Los dos candidatos que quedaban aquí como fuera de alcance —relays que escribían su log en
`/tmp`, y contenedores sin healthcheck— se resolvieron el 2026-08-13 mediante intervención
directa sobre el homelab, no como un nuevo tipo de acción de esta capa: ninguno de los dos
encaja bien en el modelo de "acción reversible puntual" de `rotar_log`. No hay ningún otro
candidato pendiente documentado en este momento.

**No reemplaza**: la vigilancia y el aviso de `docker_monitor.py` sobre contenedores
críticos, ni su recogida de métricas/discos — eso sigue exactamente igual. El agente de
diagnóstico (007-018) se añade como capa aparte, sin sustituir nada. La capa de
remediación automática (019+) sí asume, acción por acción y siempre con su propio
interruptor manual/automático, decisiones que antes tomaba `docker_monitor.py` en
solitario — primero `rotar_log` (019), y desde 021 también los reinicios de contenedores
no críticos: esa cesión, acotada y con contrapartida de aviso (Principio VII), es
deliberada, no una regresión silenciosa.

## Governance

Esta constitución es la fuente de autoridad para todo el proyecto. Una divergencia entre lo
que dice este documento y lo que hace el código se trata como un defecto del código, no de
la constitución.

**Enmiendas**: cualquier cambio a un principio marcado NO NEGOCIABLE requiere revisión
explícita y justificación documentada. Los demás cambios siguen versionado semántico:
MAJOR para redefiniciones incompatibles con la versión anterior, MINOR para adiciones de
principios o secciones, PATCH para clarificaciones y correcciones menores.

**Cumplimiento**: cada artefacto de Spec Kit (spec, plan, tasks) DEBE poder rastrearse hasta
los principios de esta constitución. Si un componente del plan no responde a ningún
principio, sobra. Si un principio no tiene componente, falta.

**Revisión**: la declaración de estado esperado (Principio III) DEBE revisarse al inicio de
cada ciclo de implementación. La línea base (Principio IX) DEBE actualizarse cuando se
establezca un nuevo conjunto de evaluación validado.

**Version**: 2.0.0 | **Ratified**: 2026-08-02 | **Last Amended**: 2026-08-14
