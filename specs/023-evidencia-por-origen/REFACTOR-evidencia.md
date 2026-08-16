# Refactor — partir evidencia.py

> **Resuelto el 2026-08-15 por `specs/023-evidencia-por-origen/`.**
> `evidencia.py` (1.864 líneas) es ahora el paquete
> `src/diagnostico/evidencia/`: un módulo por origen más
> `_compartido.py` para lo que de verdad usan varios orígenes a la vez.
> `tests/selftest/test_evidencia.py` se dividió igual, en diez
> ficheros `test_evidencia_<origen>.py`. Los tres consumidores reales
> (`diagnostico/cli.py`, `remediacion/acciones.py`,
> `diagnostico/deepseek.py`) no cambiaron una línea — ver
> `specs/023-evidencia-por-origen/{spec,plan,research,data-model}.md` y
> `contracts/fachada-evidencia.md` para el detalle completo. Este
> documento queda como material histórico de la auditoría que motivó
> la feature — no como referencia del estado actual del código.

> Material y criterios preparados por Claude antes de `speckit-specify`, según el
> reparto de `METODO.md`. No es la especificación — es lo que se sabe antes de
> escribirla.

## Evidencia (comprobada 2026-08-15)

- `src/diagnostico/evidencia.py`: 1.864 líneas. Es el fichero más grande de
  `src/`, más de la mitad del código del paquete `diagnostico`.
- Mezcla diez orígenes de evidencia, cada uno con su par
  `congelar_<origen>_vivo` / `congelar_<origen>_historico` (dos de ellos,
  agente y latido, solo tienen versión `_vivo` — no existe evidencia histórica
  real para LaunchAgents ni latidos):
  contenedor, disco, HA, backup, relay, inventario, host externo, hub Beszel,
  agente, latido.
- Delante de los diez hay siete funciones compartidas (conexión a la base de
  datos, `docker_inspect`, `docker_logs_tail`, `es_critico`,
  `_parse_docker_inspect`...) que sí usan varios orígenes a la vez — es el
  único acoplamiento real entre ellos.
- El único punto de dispatch entre los diez orígenes está en
  `diagnostico/cli.py` (18 llamadas `evidencia.congelar_*`, una por origen y
  variante).
- `remediacion/acciones.py` importa el módulo entero pero solo llama a una
  función, la de contenedor en vivo (línea 518).
- El test asociado, `tests/selftest/test_evidencia.py`, es igual de grande:
  1.638 líneas, dentro de la suite de 595 aserciones que hoy pasa entera con
  `--selftest` en los tres paquetes (`diagnostico`, `inventory`,
  `remediacion`).

## El problema, en términos de resultado (sin tecnología)

Cada uno de los diez orígenes de evidencia que reconoce el sistema tiene su
propia lógica de "congelar en vivo" y "congelar histórico", pero las diez
viven juntas en un único lugar que ya no cabe en una sola lectura. Para tocar
o verificar el comportamiento de un solo origen hay que orientarse dentro de
un contenido diez veces mayor del que le corresponde, y nada impide que un
cambio pensado para un origen roce por accidente el código de otro con el que
no tiene relación.

## Criterios de éxito candidatos (falsables)

1. Ningún origen de evidencia depende, en su lectura o en su código, del
   contenido de otro origen que no sea el suyo — se puede señalar una línea
   que lo incumpla.
2. Añadir un origen de evidencia nuevo (como se ha hecho nueve veces ya, en
   los features 007-018) no requiere modificar el código de ningún origen
   existente, solo el mecanismo compartido y el nuevo origen.
3. Cada origen se puede localizar, leer y verificar (tests) de forma aislada,
   sin tener que abrir o ejecutar el contenido de los otros nueve.
4. Cero cambio de comportamiento observable — incluye especialmente
   `remediacion/acciones.py` (evidencia de contenedor en producción) y
   `diagnostico/cli.py` (el dispatch de los diez orígenes). Los 595 aserciones
   existentes siguen en verde sin modificar su intención.

## Fuera de alcance

- Los tres `_homelab_bridge.py` y su duplicación con
  `remediacion/deepseek_contenedores.py` — es el segundo hallazgo de la
  auditoría de refactor, va como spec aparte.
- Decidir si `tests/selftest/test_evidencia.py` se divide en paralelo al
  código o se queda como suite única — abierto, candidato a
  `[NEEDS CLARIFICATION]`.

## Preguntas que probablemente salgan en `clarify`

- Qué pasa con las siete funciones compartidas del principio: ¿cuentan como
  un origen más, o como mecanismo común explícitamente distinto de los diez?
- Si el test de 1.638 líneas debe seguir la misma partición que el código o
  no es parte de esta spec.
