# Phase 0 — Research: Puente Único hacia los Scripts del Homelab

## 1. Por qué dos módulos compartidos, no uno

**Decisión**: `_homelab_bridge_common.py` (homelab_secrets + docker_monitor,
usado por los tres paquetes) y `_homelab_bridge_heartbeat.py` (heartbeat,
usado solo por diagnostico e inventory) — nunca un único módulo que
los tres importen indiscriminadamente.

**Evidencia real** (verificado import por import, no supuesto):

| Script externo | Lo importa hoy | ¿Lo importan los 3? |
|---|---|---|
| `homelab_secrets` | diagnostico (`get_secret`), inventory (`get_secret`+`telegram_credentials`), remediacion (`telegram_credentials`) | **Sí, los 3** |
| `docker_monitor` | diagnostico, inventory, remediacion (los 3 usan `docker_critical`/`docker_never_restart`) | **Sí, los 3** |
| `heartbeat` | diagnostico (`record_heartbeat`), inventory (`record_heartbeat`+`read_heartbeat`) | **No — remediacion nunca lo importa** |
| `ha_monitor` | diagnostico, inventory | **No — remediacion nunca lo importa** |

**Rationale**: en Python, `from modulo import nombre` ejecuta el
cuerpo entero de `modulo` una vez, sin importar cuántos ni cuáles
nombres se tomen de él. Si `record_heartbeat()` (que necesita
`import heartbeat`) viviera en el mismo fichero que
`docker_never_restart()` (que `remediacion` sí necesita),
`remediacion` importaría ese fichero por `docker_never_restart` y
arrastraría consigo el intento de `import heartbeat`.

> **Corrección tras implementar (T010, verificado empíricamente):** la
> premisa "`remediacion` no importa `heartbeat` hoy" era **falsa**.
> `docker_monitor.py:30` (fuera de este repo) hace `import heartbeat`
> en su propia cabecera — como `remediacion/_homelab_bridge.py` ya
> importaba `docker_monitor` antes de este refactor, `heartbeat` ya
> se cargaba de forma transitiva en el proceso de `remediacion`, con
> o sin este cambio. Comprobado ejecutando el bridge **original**
> (`git show HEAD:src/remediacion/_homelab_bridge.py`) contra un
> proceso limpio: `'heartbeat' in sys.modules` da `True` también ahí.
>
> Esto no invalida la decisión de separar `_homelab_bridge_heartbeat.py`
> — solo invalida el motivo original. La separación sigue siendo
> correcta por una razón más sólida: no depender de que
> `docker_monitor.py` siga important `heartbeat.py` en el futuro para
> mantener el aislamiento de `remediacion`. Es una dependencia directa
> y explícita (la de este repo) la que debe seguir sin existir, no una
> transitiva y accidental (la de un script externo) la que hay que
> vigilar. FR-006/SC-003 hablan de comportamiento observable de este
> repo, no de qué importa por su cuenta un script de terceros.

**Mismo razonamiento aplicado y descartado para `ha_monitor`**: el
bloque de import de `ha_monitor` es idéntico byte a byte entre
`diagnostico` e `inventory` (comprobado con `diff`) — sexto duplicado
real que `REFACTOR-homelab-bridge.md` no había detectado. No se
consolida en ninguno de los dos módulos compartidos por el mismo
motivo que `heartbeat`: aunque solo lo usan 2 de los 3 paquetes (nunca
remediacion), lo que cada uno HACE con `_ha_monitor` es exclusivo y
distinto — no hay una función compartida que envolver, solo el bloque
de import en sí. Consolidarlo exigiría un tercer módulo de una sola
utilidad (el handle, sin ninguna función alrededor) por 4 líneas de
ahorro — desproporcionado. Queda duplicado a propósito, documentado
aquí en vez de "descubierto y ocultado".

**Alternativas consideradas**:
- *Un único `_homelab_bridge_common.py` con las cinco piezas de
  `REFACTOR-homelab-bridge.md`*. Rechazada: fuerza a `remediacion` a
  importar `heartbeat` sin necesitarlo (ver arriba).
- *Poner el módulo compartido dentro de `inventory/`* (el paquete más
  antiguo). Rechazada: crearía una dependencia nueva de `remediacion`
  hacia `inventory` que hoy no existe — fuera del alcance de esta
  feature (spec.md, Assumptions: "no se decide si conviene que algún
  paquete importe de inventory para algo nuevo").

## 2. Los tests existentes no necesitan tocarse — verificado, no asumido

**Hallazgo clave**, distinto de 023: en 023, dividir `evidencia.py`
obligó a reescribir `test_evidencia.py` entero porque las funciones
internas se llamaban unas a otras por nombre global dentro del mismo
módulo (`patch.object(evidencia, "_run_ro", ...)` dejaba de alcanzar
la llamada real tras el split). Aquí no pasa lo mismo, porque **todo
consumidor real de un bridge —código de producción y tests— accede
siempre por atributo de módulo, nunca importando el nombre suelto**:

```python
from . import _homelab_bridge as bridge   # el módulo entero
...
bridge.docker_critical()                   # atributo, resuelto en cada llamada
```

Comprobado con grep sobre las 12 llamadas `bridge.<función>(...)` en
producción (acciones.py, cli.py, deepseek.py, evidencia/contenedor.py,
evidencia/ha.py, inventory/sources.py, inventory/evaluate.py,
inventory/deliver.py, remediacion/store.py) y las ~25 líneas
`patch.object(_homelab_bridge, "...", ...)` / `patch.object(x.bridge,
"...", ...)` en los tests (`test_remediacion_cli.py`,
`test_remediacion_acciones.py`, `test_evaluate.py`,
`test_evidencia_contenedor.py`, `test_evidencia_ha.py`): ninguna hace
`from ._homelab_bridge import docker_critical`. Todas pasan por el
módulo. Un `patch.object(módulo, "nombre", ...)` sustituye el
atributo del módulo en sí — y como la llamada real también resuelve
`bridge.nombre` en el momento de ejecutarse (no antes), da igual si
`nombre` está definido ahí mismo o reexportado desde otro fichero: el
parche y la llamada real coinciden siempre en el mismo sitio.

**Consecuencia para tasks.md**: no hay tarea de "mover tests" en este
refactor — solo una tarea de verificación que confirme, tras el
cambio, que la suite sigue en verde con el mismo recuento.

## 3. `docker_critical()` — base compartida más extensión, no dos copias

**Decisión**: `_homelab_bridge_common.docker_critical()` implementa
solo la lectura de `docker_monitor.CRITICAL` (idéntica hoy entre
diagnostico e inventory, comprobado con `diff`). El
`remediacion/_homelab_bridge.py` deja de tener su propia copia
completa y pasa a:

```python
from _homelab_bridge_common import docker_critical as _docker_critical_base

def docker_critical() -> set[str]:
    criticos = _docker_critical_base()
    forzados = os.environ.get("REMEDIACION_TEST_FORZAR_CRITICO", "")
    if forzados:
        criticos |= {n.strip() for n in forzados.split(",") if n.strip()}
    return criticos
```

**Rationale**: FR-003/SC-002 exigen que el hook de prueba
(`REMEDIACION_TEST_FORZAR_CRITICO`) nunca sea alcanzable desde
diagnostico ni inventory. Una función envoltorio LOCAL en
`remediacion/_homelab_bridge.py` (no una reexportación plana) es la
única forma de que ese hook exista solo ahí — y de que
`patch.object(remediacion._homelab_bridge, "docker_critical", ...)`
(usado hoy por `test_remediacion_cli.py`) siga sustituyendo la función
completa, exactamente como antes.

## 4. Documentar la dependencia diagnostico → inventory (FR-005)

**Decisión**: mismo nivel de detalle que 021 §2 dio a
`remediacion` → `diagnostico` — una entrada explícita en el
`research.md` de la feature que la introduce (aquí, ya que 013 nunca
lo hizo) más la corrección del docstring que hoy afirma lo contrario.

**Evidencia real**: `src/diagnostico/evidencia/inventario.py` importa
`inventory.diff`, `inventory.store` e `inventory.model.TIPOS_BRECHA`
desde el feature 013 (specs/013-diagnostico-inventario/) — nunca
documentado como ruptura de aislamiento en ningún research.md de esa
época. Mientras tanto, `src/diagnostico/_homelab_bridge.py` sigue
afirmando en su docstring: *"`diagnostico` e `inventory` son dos
paquetes hermanos independientes bajo `src/`, sin que ninguno dependa
del otro"* — falso desde 013, cinco features antes de esta.

**Rationale**: 021 §2 marcó el precedente correcto — cuando se relaja
la independencia entre paquetes, el research.md de la feature que lo
hace (o, si ya pasó sin anotarse, la primera feature que lo detecta)
debe decirlo explícitamente, no dejar que el código calle. La
diferencia con remediacion → diagnostico es que aquélla fue una
decisión consciente tomada en su momento (021 §2, con su propio
razonamiento); ésta es una dependencia que ya existía de hecho sin que
nadie la hubiera decidido conscientemente ni anotado — más motivo para
documentarla ahora, no menos.

**Acción concreta para `tasks.md`**: corregir el docstring de
`diagnostico/_homelab_bridge.py`, quitando la afirmación de
independencia total y anotando la dependencia real hacia `inventory`
(vía `evidencia/inventario.py`), con referencia a este documento.

## Resumen de decisiones

| # | Decisión | Afecta a |
|---|---|---|
| 1 | Dos módulos compartidos neutrales, no uno — separados por qué script externo necesitan | data-model.md, tasks.md |
| 2 | Ningún test se reescribe — todos los consumidores acceden por atributo de módulo | tasks.md (solo verificación, no migración) |
| 3 | `docker_critical()` en remediacion sigue siendo una función local que envuelve la base compartida | data-model.md, contracts |
| 4 | Corregir el docstring de `diagnostico/_homelab_bridge.py` — ya no son paquetes hermanos independientes | tasks.md |
