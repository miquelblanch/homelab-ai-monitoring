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

El proyecto tiene dos frentes. El primero está cerrado. Del segundo,
la mitad de diagnóstico está cerrada; la mitad de remediación
automática no ha empezado.

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

### Frente 2 — Diagnóstico (cerrado, los 10 orígenes) y remediación (sin empezar)

**Diagnóstico**: ante un episodio de cualquiera de los 10 orígenes de
alarma del homelab, un motor (`src/diagnostico/`) reúne su evidencia
real, pide a DeepSeek varias hipótesis de causa probable ya
contrastadas contra esa evidencia, y registra cada una — nunca inventa
una causa sin respaldo (principios IV, VIII, XI). Doce features, del
primer origen (contenedor) hasta el décimo (latido de monitores) y su
superficie en el dashboard:

| Feature | Qué cierra |
|---|---|
| [`007-diagnostico-episodios`](specs/007-diagnostico-episodios/) | El motor mismo — origen `contenedor`, hipótesis contrastadas contra métricas/logs/estado real, límite de gasto diario compartido |
| [`008-visor-diagnosticos-correcciones`](specs/008-visor-diagnosticos-correcciones/) | Primer intento de mostrar el diagnóstico en el dashboard — una migración de esquema posterior lo dejó roto en producción durante dos días, sin que nadie lo notara; corregido en 018 |
| [`009-diagnostico-discos`](specs/009-diagnostico-discos/) | Generaliza el motor a discos |
| [`010-diagnostico-ha`](specs/010-diagnostico-ha/) | Generaliza a Home Assistant |
| [`011-diagnostico-backups`](specs/011-diagnostico-backups/) | Generaliza al backup diario |
| [`012-diagnostico-relays`](specs/012-diagnostico-relays/) | Generaliza a relays `socat` — en diferido solo con el recuento agregado al principio, sin poder nombrar cuál relay concreto |
| [`013-diagnostico-inventario`](specs/013-diagnostico-inventario/) | Generaliza al propio inventario de cobertura (Frente 1) |
| [`014-diagnostico-hosts-externos`](specs/014-diagnostico-hosts-externos/) | Generaliza a hosts físicos externos vigilados por Beszel |
| [`015-diagnostico-hub-beszel`](specs/015-diagnostico-hub-beszel/) | Generaliza al propio hub de Beszel |
| [`016-diagnostico-agentes`](specs/016-diagnostico-agentes/) | Generaliza a los LaunchAgents — único origen sin ningún modo diferido: no existe ninguna fuente histórica real que consultar |
| [`017-diagnostico-latidos`](specs/017-diagnostico-latidos/) | Generaliza a los latidos de monitores — el mecanismo relacionado que había quedado fuera de 016 |
| [`018-visor-diagnosticos-origenes`](specs/018-visor-diagnosticos-origenes/) | Generaliza el visor del dashboard a los 10 orígenes, corrige el bug de contenedor, y arregla hacia adelante la limitación de relay |

**Remediación automática: sin empezar.** Ejecutar, dentro de una lista
cerrada de acciones reversibles con rollback escrito, la corrección de
una causa ya diagnosticada con certeza (Principios V y VI de la
constitución). `docker_monitor.py` sigue siendo el único mecanismo que
remedia algo hoy, y solo reinicia contenedores.

## Estructura del repo

```
.specify/memory/constitution.md   Los no negociables del proyecto
BRIEFING.md                        El problema, la premisa, qué está en alcance
METODO.md                          Reparto de trabajo y qué mide cada skill de Spec Kit
PRINCIPIOS.md                      Entrada original a speckit-constitution (histórico)
BARRIDO-2026-08-0*.md              Barridos manuales que motivaron o validaron features
BITACORA.md                        Una línea por sesión: qué midió el método
specs/0NN-*/                       Un directorio por feature: spec, plan, tasks, research...
src/inventory/                     El inventario de cobertura (feature 001)
src/diagnostico/                   El motor de diagnóstico (features 007-017), 10 orígenes
tests/selftest/                    Autocomprobaciones del inventario y del motor de
                                    diagnóstico — sin tocar datos reales ni llamar a DeepSeek
```

## El inventario de cobertura

Una de las dos piezas con código real de este repo (la otra es el motor
de diagnóstico, más abajo). Recorre contenedores, integraciones de Home
Assistant y la propia infraestructura de monitorización, y para cada
componente responde tres preguntas: ¿tiene un estado esperado
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

## El motor de diagnóstico

Congela evidencia real de un episodio (métricas, logs, estado del
componente — nunca inventada) para uno de los 10 orígenes, pide a
DeepSeek varias hipótesis de causa probable ya contrastadas contra esa
evidencia, y registra cada hipótesis y la conclusión final. Nunca
ejecuta ni propone una acción correctiva — es estrictamente
diagnóstico (Frente 2, mitad de remediación sin empezar). Un límite de
gasto diario compartido protege las llamadas a DeepSeek entre los 10
orígenes.

```bash
# Congelar evidencia real de un contenedor caído ahora mismo, y diagnosticarlo
# — solo tiene sentido dentro del homelab real, con sus credenciales de DeepSeek
PYTHONPATH=src python3 -m diagnostico.cli congelar --vivo CONTENEDOR
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar EPISODIO_ID
PYTHONPATH=src python3 -m diagnostico.cli mostrar EPISODIO_ID

# Cada uno de los otros 9 orígenes tiene su propio flag --ORIGEN-vivo,
# y la mayoría también --ORIGEN-historico para un momento pasado concreto
# (agente y latido son los únicos sin modo diferido — no existe ninguna
# fuente histórica real que consultar, ver specs/016 y specs/017)

# Autocomprobación de la lógica pura — no toca DeepSeek, Docker, HA ni
# ninguna otra fuente real
PYTHONPATH=src python3 -m diagnostico.cli --selftest
```

Fuera del homelab real (sin las credenciales ni los ficheros de datos
privados) el `--selftest` es la única vía con sentido: valida la lógica de
evaluación, identidad de componentes y comparación entre ejecuciones contra
datos sintéticos.

## Qué no está aquí

Por diseño (ver "Decisiones ya tomadas" en `BRIEFING.md`): topología real
de la red, credenciales, IPs, y cualquier dato ligado a la seguridad física
de la vivienda. El código que corre dentro del homelab en sí —los scripts
que Docker y Home Assistant ejecutan de verdad, incluido el propio
dashboard web (`homelab-dashboard/scripts/app.py`, que consume lo que
persiste el motor de diagnóstico)— vive fuera de este repositorio, en el
homelab real; este repo contiene el inventario de cobertura y el motor de
diagnóstico (ambos públicos desde el diseño) y la documentación completa
del método.

## Leer más

En este orden, si quieres entender el proyecto de verdad y no solo
hojearlo: [`constitution.md`](.specify/memory/constitution.md) →
[`BRIEFING.md`](BRIEFING.md) → [`METODO.md`](METODO.md) →
[`BARRIDO-2026-08-01.md`](BARRIDO-2026-08-01.md).
