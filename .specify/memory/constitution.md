<!--
## Sync Impact Report

**Version change**: 1.1.0 → 1.1.1
**Principles added**: None
**Principles modified**: Rationale de los 12 principios (I–XII) reescrito en lenguaje más
corto y directo; las reglas de cada principio no cambian
**Sections added**: None
**Sections removed**: N/A
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
componente. La remediación automática existente (`docker_monitor.py`) DEBE seguir funcionando
con independencia del estado del agente.

**Rationale**: Si el agente sustituyera al monitor y fallara, se perdería la remediación que
lleva meses funcionando sin ayuda de nadie.

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

## Modelo Operacional

El agente opera bajo el **Modelo B**: actúa de forma autónoma únicamente en acciones
reversibles y de bajo riesgo definidas en la lista cerrada del spec. Todo lo demás es
propuesta que espera aprobación humana explícita.

El criterio de clasificación DEBE estar declarado en el spec antes de la implementación. Si
hay duda sobre si una acción es de bajo riesgo, se trata como de alto riesgo.

## Alcance y Límites

**En alcance**: diagnóstico de incidencias de contenedores, formulación y contraste de
hipótesis contra el historial de episodios, propuesta de acciones correctivas, registro del
razonamiento, y mantenimiento del dashboard (`http://homelab.amsterdam9.home/`) como
entregable del proyecto: toda alarma activa del sistema DEBE quedar reflejada allí sin
duplicados y sin ausencias (Principio XII).

**Fuera de alcance en v1**: ejecución de acciones correctivas sobre contenedores críticos
(lista del monitor), diagnóstico de Home Assistant y relays socat, cualquier incidencia que
el monitor actual resuelva sin ayuda.

**No reemplaza**: `docker_monitor.py` y su ciclo de remediación automática. El agente se
añade como capa de diagnóstico.

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

**Version**: 1.1.1 | **Ratified**: 2026-08-02 | **Last Amended**: 2026-08-02
