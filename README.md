# Homelab Diagnostic Agent

Caso de estudio público de **Spec-Driven Development (SDD)** aplicado a un
problema real: la monitorización de un homelab doméstico de 40 contenedores.
No es una demo — es el desarrollo real, con sus especificaciones, sus
correcciones y sus errores, de un sistema que hoy vigila ~800 componentes
reales sin ninguna brecha de cobertura conocida.

> Este repo es autocontenido: no depende de ningún fichero privado para
> tener sentido. Nombra el software que se usa, nunca la topología real de
> la red (ver "Decisiones ya tomadas" en [`BRIEFING.md`](BRIEFING.md)).

## El problema, en una frase

No es resolver un misterio concreto ni una lista fija de incidencias. Es
construir un sistema de monitorización que cubra **sistemáticamente** todo
un homelab —no solo lo que ya ha fallado alguna vez de forma visible— y
que, para cada problema real que detecte, o lo corrija solo (si la causa ya
está diagnosticada y la acción es segura y reversible) o avise con
contexto suficiente para que una persona lo resuelva.

Cuatro casos, encontrados por casualidad en momentos distintos, motivaron
el proyecto — no son la lista de tareas, son la prueba de que el problema
es sistémico:

1. Un contenedor se reinició automáticamente 49 veces en siete semanas sin
   que saltara ni una alerta.
2. Un barrido manual encontró 11 problemas reales, invisibles al dashboard
   existente.
3. La propia herramienta de monitorización no vigilaba bien 2 de los 3
   sistemas que tenía a su cargo.
4. Un mecanismo de avisos llevaba semanas sin funcionar sin que nadie lo
   notara.

Si cuatro problemas de este calibre aparecieron sin buscarlos activamente,
la pregunta no es "¿cómo arreglo estos cuatro?" — es "¿cuántos más hay, y
cómo dejo de depender de la suerte para encontrarlos?". Detalle completo de
cada caso en [`BRIEFING.md`](BRIEFING.md).

## El método

Este proyecto es, a la vez, la solución a ese problema y un experimento
sobre cómo construirla: todo el desarrollo sigue Spec-Driven Development
con [Spec Kit](https://github.com/github/spec-kit), y **la especificación
manda** — una divergencia entre lo que dice el spec y lo que hace el
código es un defecto del código, nunca de la especificación.

El flujo, para cada pieza de trabajo:

```
constitution → specify → clarify → plan → tasks → analyze → implement
```

Trece principios gobiernan el proyecto entero —tres de ellos marcados
como no negociables: "ninguna alerta se silencia mientras la condición
persista", "el agente actúa solo sobre una lista cerrada de acciones
reversibles, declarada en el spec" y "el dashboard refleja en todo
momento el conjunto exacto de alarmas activas, sin duplicados y sin
ausencias"— recogidos en
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

Cada sesión de trabajo queda registrada en [`BITACORA.md`](BITACORA.md):
cuántas ambigüedades detectó `clarify`, cuántas tareas se completaron sin
intervención, cuántas veces hubo que corregir el spec en vez del código.
Es la mitad del valor del proyecto — no solo construir el sistema, sino
medir cómo de bien funciona el método para construirlo.

## Estado actual

El proyecto tiene dos frentes, y solo el primero está cerrado.

### Frente 1 — Cobertura sistemática (cerrado)

Recorrer todo lo que compone el homelab y, para cada pieza, declarar un
estado esperado, vigilarlo de verdad, y asegurarse de que un fallo llega
al dashboard. Seis features, de la primera línea de código al despliegue
real:

| Feature | Qué cierra |
|---|---|
| [`001-inventario-cobertura-homelab`](specs/001-inventario-cobertura-homelab/) | El inventario mismo: recorre contenedores, integraciones y entidades de Home Assistant y responde, de cada uno, si tiene estado esperado, si se vigila, y si llegaría al dashboard |
| [`002-alarmas-al-dashboard`](specs/002-alarmas-al-dashboard/) | Dos alarmas que ya se calculaban (contenedores caídos, hosts externos) pero nunca llegaban al panel |
| [`003-latidos-beszel-calendario`](specs/003-latidos-beszel-calendario/) | Latido propio para dos piezas de la infraestructura de monitorización que nadie vigilaba a sí misma |
| [`004-triage-entidad-ha`](specs/004-triage-entidad-ha/) | Triaje de ~300 entidades de Home Assistant marcadas como brecha, separando ruido de señales de seguridad reales |
| [`005-movil-y-backup-ha`](specs/005-movil-y-backup-ha/) | Metadatos de apps móviles fuera de alcance; vigilancia del backup propio de Home Assistant |
| [`006-central-alarmas`](specs/006-central-alarmas/) | Pestaña única que unifica los 10 orígenes de alarma del homelab, con explicación y remediación sugerida en texto — sin IA, sin ejecutar nada |

Resultado medible: la primera ejecución real encontró 385 brechas sobre
830 componentes. Hoy, cero.

### Frente 2 — Diagnóstico y remediación (sin empezar)

Un agente que, ante un fallo cuya causa **no** se conoce de antemano,
formule hipótesis, las contraste contra datos reales, y para las que
queden confirmadas con certeza y tengan una corrección segura y
reversible, la aplique — documentado en los principios IV, V, VI, VII y
VIII de la constitución. Todavía en fase de material de partida (ver la
sección "Feature 007" de `BRIEFING.md`).

## Estructura del repo

```
.specify/memory/constitution.md   Los no negociables del proyecto
BRIEFING.md                        El problema, la premisa, qué está en alcance
METODO.md                          Reparto de trabajo y qué mide cada skill de Spec Kit
PRINCIPIOS.md                      Entrada original a speckit-constitution (histórico)
BARRIDO-2026-08-0*.md              Barridos manuales que motivaron o validaron features
BITACORA.md                        Una línea por sesión: qué midió el método
specs/00N-*/                       Un directorio por feature: spec, plan, tasks, research...
src/inventory/                     El inventario de cobertura (feature 001), ~2.100 líneas
tests/selftest/                    Autocomprobaciones del inventario, sin tocar datos reales
```

## El inventario de cobertura

La pieza con código real de este repo. Recorre contenedores, integraciones
de Home Assistant y la propia infraestructura de monitorización, y para
cada componente responde tres preguntas: ¿tiene un estado esperado
declarado?, ¿se vigila de verdad?, ¿llegaría al dashboard si fallara?

```bash
# Ejecución completa (persiste, entrega por Telegram y actualiza el dashboard
# — solo tiene sentido dentro del homelab real, con sus credenciales)
PYTHONPATH=src python3 -m inventory.cli

# Solo el listado de brechas, sin tocar nada en vivo
PYTHONPATH=src python3 -m inventory.cli --gaps --no-telegram --no-dashboard

# Autocomprobación de la lógica pura — no toca Docker, HA ni Telegram reales
PYTHONPATH=src python3 -m inventory.cli --selftest
```

Fuera del homelab real (sin las credenciales ni los ficheros de datos
privados) el `--selftest` es la única vía con sentido: valida la lógica de
evaluación, identidad de componentes y comparación entre ejecuciones contra
datos sintéticos.

## Qué no está aquí

Por diseño (ver "Decisiones ya tomadas" en `BRIEFING.md`): topología real
de la red, credenciales, IPs, y cualquier dato ligado a la seguridad física
de la vivienda. El código que corre dentro del homelab en sí —los scripts
que Docker y Home Assistant ejecutan de verdad— vive en un repositorio
privado aparte; este repo contiene el inventario de cobertura (público
desde el diseño) y la documentación completa del método.

## Leer más

En este orden, si quieres entender el proyecto de verdad y no solo
hojearlo: [`constitution.md`](.specify/memory/constitution.md) →
[`BRIEFING.md`](BRIEFING.md) → [`METODO.md`](METODO.md) →
[`BARRIDO-2026-08-01.md`](BARRIDO-2026-08-01.md).
