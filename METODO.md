# Método de trabajo

> Cómo se lleva este proyecto. El proyecto se llama "Homelab Diagnóstico Agent".

## El reparto

**Miquel ejecuta.** Todas las skills, todos los comandos, todo el código. El objetivo
no es tener el proyecto: es saber hacerlo.

**Claude revisa y aporta sustancia.** Antes de cada paso, el material y los criterios.
Después, la revisión crítica de lo que haya salido.

### Por qué este reparto, con precisión

Hay dos razones, y conviene no confundirlas:

**El aprendizaje.** Si Claude escribe los artefactos, Miquel no aprende el método.
Es la razón principal porque Miquel tiene que aprender SDD.

**La medición.** No se puede medir *"cuántas ambigüedades detectó `clarify`"* sin
ejecutar `clarify`. Saltarse el flujo de la herramienta no invalida el método, pero
sí invalida los números del experimento.

Lo que define a SDD es que **la especificación sea vinculante**: que la
implementación se derive de ella y que una divergencia entre lo que dice el spec y lo
que hace el código se trate como un defecto, no como algo normal.

*Spec como fuente, no spec como documentación.* Eso es lo que hay que sostener, y
se puede incumplir perfectamente aunque los ficheros los escriba un humano.

---

## Antes de nada: lee las skills

En `.claude/skills/` hay diez `SKILL.md`. **Léelos antes de invocarlos.**

Es la mejor inversión de la primera hora: entiendes qué hace cada uno, qué espera de
ti y qué produce. Invocar una skill sin haber leído su definición es exactamente el
tipo de caja negra del que va tu otro proyecto.

| Skill | Para qué |
| --- | --- |
| `speckit-constitution` | Los no negociables. Una vez por proyecto |
| `speckit-specify` | El **qué** y el **por qué**. Sin tecnología |
| `speckit-clarify` | Detecta ambigüedades en el spec y las pregunta |
| `speckit-plan` | El **cómo**: stack, arquitectura, modelo de datos |
| `speckit-tasks` | Tareas ordenadas por dependencia, con marcas de paralelizable |
| `speckit-analyze` | Coherencia entre constitución, spec, plan y tareas |
| `speckit-checklist` | Puertas de calidad |
| `speckit-implement` | Ejecuta las tareas |
| `speckit-converge` | *Leer el SKILL.md — no lo he usado nunca* |
| `speckit-taskstoissues` | Exporta tareas a issues de GitHub |

El flujo troncal es: **constitution → specify → clarify → plan → tasks → analyze →
implement**. Los demás son auxiliares.

---

## Qué mirar en cada paso

Aquí está el aprendizaje. En cada artefacto que genere una skill, la pregunta no es
*"¿está bien escrito?"* sino la de la columna derecha.

### `constitution`

**Qué buscar:** que cada principio sea **falsable**. Un principio que no puede
incumplirse no es un principio, es un adorno. *"Escribiremos código de calidad"* no
vale. *"Ningún resultado se devuelve sin verificar la condición"* sí, porque se puede
señalar código que lo incumple.

### `specify`

**Qué buscar:** que **no haya tecnología dentro**. Si aparece LangGraph, Python o un
nombre de modelo, el spec está contaminado. El spec dice qué tiene que pasar y para
quién; el cómo va en el plan.

Es la disciplina más difícil de sostener y la que más valor tiene: obliga a separar
el problema de la solución que ya tenías en la cabeza.

### `clarify`

**Qué buscar:** las preguntas que te haga. **Son el producto, no un trámite.** Cada
ambigüedad que detecte es una decisión que ibas a tomar sin darte cuenta a mitad de
implementación.

Anota cuántas encuentra. Es uno de los números del experimento.

### `plan`

**Qué buscar:** que cada decisión técnica se pueda rastrear hasta algo del spec. Si
hay un componente que no responde a ningún requisito, sobra. Si hay un requisito sin
componente, falta.

### `tasks`

**Qué buscar:** que las tareas sean **verificables una a una**. Si no sabes decir
cómo comprobarías que una tarea está terminada, está mal escrita.

Y mira las marcas de paralelizable: si casi nada lo es, probablemente el plan tiene
más acoplamiento del necesario.

### `analyze`

**Qué buscar:** incoherencias entre los cuatro documentos. Es el equivalente a lo
que en el otro proyecto no existía — una comprobación automática de que lo que dices
y lo que hay coinciden.

### `implement`

**Qué buscar:** cuántas tareas salen bien sin intervención, y **cuántas veces acabas
corrigiendo el spec en lugar del código**. Ese segundo número es el más interesante
de todo el proyecto.

---

## Lo que hay que medir

Esto no es opcional: es la mitad del valor del proyecto, y si no se registra al
vuelo, después no se reconstruye.

| Métrica | Cuándo se anota |
| --- | --- |
| Tiempo dedicado a especificar vs a implementar | En cada sesión |
| Ambigüedades detectadas por `clarify` | Al ejecutarlo |
| Tareas implementadas sin intervención | En cada `implement` |
| Veces que se corrigió el **spec** en lugar del código | Cuando pase |
| Veces que se reescribió el spec entero | Cuando pase |
| ¿Al terminar, el spec sigue describiendo lo que hay? | Al cerrar cada hito |

Llévalo en un `BITACORA.md` con fecha. Una línea por sesión basta.

---

## Cómo pedir revisión

Funciona mejor si es concreto:

- **"He ejecutado `specify`, aquí está el `spec.md`, revísalo"** — devuelvo qué falta,
  qué sobra y qué está contaminado de tecnología.
- **"`clarify` me ha preguntado esto, ¿qué contesto?"** — razonamos la respuesta juntos.
- **"No entiendo por qué `plan` ha decidido X"** — lo desmontamos.

Y al revés, cuando algo no cuadre: **dilo antes de seguir**. Un spec malo se propaga
a plan, a tareas y a código, y cada paso multiplica el coste de arreglarlo.

---

## El `CLAUDE.md` del proyecto

Aparte de los artefactos de SDD (constitución, spec, plan, tareas), este repo
mantiene un `CLAUDE.md` propio en la raíz. No es un artefacto de Spec Kit: es el
fichero que lee cualquier instancia de Claude Code al abrir el repo en frío, así que
tiene una función distinta a los demás — orientar, no especificar.

### Por qué existe uno aquí y no basta con el general del homelab

El `CLAUDE.md` general (`/Volumes/FastData/homelab/CLAUDE.md`) es privado y mezcla
topología real de la infraestructura. Este repo es público y autocontenido: no puede
depender de un fichero que vive fuera de él y que nunca se va a versionar aquí. De
ahí que la primera línea del `CLAUDE.md` de este repo sea "el general no aplica, este
es aparte".

### Qué va dentro

Cinco piezas, en este orden, y ninguna más larga de lo necesario:

1. **Una frase de qué es el proyecto** — coherente con `BRIEFING.md`, no una copia.
2. **Orden de lectura** — qué leer y en qué orden antes de tocar nada: la
   constitución, `BRIEFING.md`, `METODO.md`, `BARRIDO-2026-08-01.md`,
   `PRINCIPIOS.md`.
3. **El problema, en una frase** — el resumen vigente del objetivo del proyecto.
   Es la sección que más caduca: cuando la constitución o el briefing se
   reformulan (como al pasar de una lista de dos premisas a la cobertura
   sistemática de Principio XIII), esta sección queda desfasada primero y nadie se
   da cuenta hasta que alguien se la lee entera.
4. **Datos disponibles para el agente** — el esquema de la base de datos. Vive solo
   aquí: no se duplica en `BRIEFING.md`.
5. **Reglas operativas rápidas** — lo mínimo para no romper nada por accidente, con
   enlace a este `METODO.md` para el reparto de trabajo.

### Qué no va dentro

- **Tecnología ni decisiones de plan.** Lo que pertenece al `plan.md` de una
  feature no pertenece al `CLAUDE.md` del repo.
- **Topología real.** Mismo criterio que en `BRIEFING.md`: se nombra el software,
  no IPs, dispositivos ni nombres ligados a seguridad física.
- **Contenido duplicado de otro fichero.** El `CLAUDE.md` apunta, no repite. Si una
  sección empieza a acumular detalle que ya está en `BRIEFING.md` o en la
  constitución, es señal de recortarla y dejar el enlace.

### Cuándo se actualiza

No en cada commit — solo cuando cambia el terreno que resume:

- Un principio nuevo o reformulado en la constitución.
- Un reframe del briefing (cambia qué es "el problema").
- Un documento nuevo que debería entrar en el orden de lectura.

El criterio es el mismo que para la constitución: si el `CLAUDE.md` describe un
estado del proyecto que ya no es el vigente, es un defecto del fichero, no un
detalle menor — es lo primero que lee cualquiera, humano o Claude, al entrar al
repo.

### Quién lo escribe

Mismo reparto que el resto de la documentación del proyecto: **Claude redacta**, a
partir de lo que cambió en la constitución o el briefing; **Miquel revisa y hace el
commit**. No es una skill `speckit-*`, así que no aplica la regla de "Miquel
ejecuta" — es documentación de proyecto, igual que este propio `METODO.md`.

---

Sobre todo es importante que Claude lea bien como es un proyecto de SDD y que siga 
todos los pasos con detalle uno a uno: Claude redacta los temas, Miquel revisa la 
documentación y ejecuta todos los comandos de SDD