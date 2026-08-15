# Refactor — los tres `_homelab_bridge.py`

> **Resuelto el 2026-08-15 por `specs/024-consolidar-bridge-homelab/`.**
> Las cinco piezas verificadas como duplicadas (más `docker_critical`,
> base + extensión) viven ahora en dos módulos neutrales bajo `src/`:
> `_homelab_bridge_common.py` (las cuatro que los tres paquetes ya
> importaban) y `_homelab_bridge_heartbeat.py` (la única que solo
> usan diagnostico e inventory — nunca remediacion, ver research.md
> §1 de esa feature para el porqué de partir en dos). Los tres
> `_homelab_bridge.py` originales quedan como fachadas finas; ningún
> consumidor ni ningún test cambió una línea. La dependencia real
> diagnostico → inventory (desde feature 013, nunca documentada) queda
> anotada explícitamente en el docstring de
> `diagnostico/_homelab_bridge.py`. Ver
> `specs/024-consolidar-bridge-homelab/{spec,plan,research,data-model}.md`
> para el detalle completo. Este documento queda como material
> histórico de la auditoría que motivó la feature.

> Material y criterios preparados por Claude antes de `speckit-specify`,
> mismo patrón que `REFACTOR-evidencia.md` (feature 023).

## Evidencia (comprobada 2026-08-15)

Tres ficheros, mismo propósito (puente hacia scripts privados del homelab
fuera del repo): `src/diagnostico/_homelab_bridge.py` (149 líneas),
`src/inventory/_homelab_bridge.py` (164 líneas),
`src/remediacion/_homelab_bridge.py` (180 líneas).

**Solapamiento real función por función:**

| Función | diagnostico | inventory | remediacion | ¿Idéntica donde coincide? |
|---|---|---|---|---|
| `docker_never_restart()` | ✓ | ✓ | ✓ | **Sí, literal en las tres** |
| `docker_critical()` | ✓ | ✓ | ✓ (+ hook de test `REMEDIACION_TEST_FORZAR_CRITICO`) | Solo entre diagnostico/inventory; remediacion añade lógica propia |
| `get_secret()` | ✓ | ✓ | — | Sí, entre las dos que la tienen |
| `record_heartbeat()` | ✓ | ✓ | — | Sí, entre las dos que la tienen |
| `telegram_credentials()` | — | ✓ | ✓ | Sí, entre las dos que la tienen |
| `ha_checks`/`ha_history`/`ha_check_status`/`ha_recorder_corrupt_files` | ✓ | — | — | Solo diagnostico |
| `ha_monitor_checked_entities`/`_conditional_entities`/`_check_result`/`available`/`read_heartbeat` | — | ✓ | — | Solo inventory |
| `listar_contenedores`/`restart_container`/`breaker_decision`/`recent_restart_attempts`/`declarar_correccion_ia` | — | — | ✓ | Solo remediacion |

Más el boilerplate idéntico en las tres cabeceras: resolución de
`HOMELAB_SCRIPTS_DIR`, inserción en `sys.path`, y el patrón
`try/import.../except ImportError: = None` por cada script externo.

## Por qué son copias — la razón histórica, verificada contra `research.md`

- **019 (`remediacion`), research.md §2**: *"`src/remediacion/` no importa
  nada de `src/diagnostico/`... mismo aislamiento que ya separa `inventory`
  de `diagnostico` (paquetes hermanos, sin dependencia cruzada)."* §11:
  *"`_homelab_bridge.py` nuevo en `remediacion/` — copia mínima... no una
  importación cruzada entre paquetes, para no romper la independencia
  declarada del paquete."*
- **010 (`diagnostico`)**: el propio docstring del fichero dice
  *"`diagnostico` e `inventory` son dos paquetes hermanos independientes
  bajo `src/`, sin que ninguno dependa del otro."*
- **021 (`remediacion`), research.md §2 — ya relajó esta doctrina una vez**:
  *"Mantener la independencia total obligaría a duplicar código de
  producción ya probado — el mismo tipo de decisión que 019 (research.md
  §11) ya resolvió reutilizar en vez de duplicar."* A partir de ahí,
  `remediacion/acciones.py` importa directamente `diagnostico.evidencia`,
  `diagnostico.gasto` y `diagnostico.deepseek.llamar_deepseek`. **Pero el
  bridge en sí se mantuvo como copia** — 021 solo autorizó cruzar paquetes
  para código de producción, no rehízo el bridge compartido.

## Dos rupturas de "paquetes hermanos sin dependencia cruzada" — una documentada, otra no

1. **`remediacion` → `diagnostico`** (`acciones.py:18-20`, `cli.py:243`):
   autorizada y documentada explícitamente en 021 §2.
2. **`diagnostico` → `inventory`** (`diagnostico/evidencia/inventario.py`,
   heredado de feature 013, ya presente antes del refactor 023): **no
   está documentada en ningún research.md**, y el docstring del bridge de
   `diagnostico` (010) sigue afirmando la independencia total como si
   nada hubiera cambiado.

## El problema, en términos de resultado

Tres copias de un puente hacia el mismo puñado de scripts externos,
donde al menos cinco funciones son literalmente idénticas en dos o tres
de las copias. Un cambio en cómo se resuelve `HOMELAB_SCRIPTS_DIR`, en
el contrato "a prueba de fallos", o en una de esas cinco funciones
compartidas exige recordar tocar hasta tres ficheros a la vez — y nada
avisa si se te olvida uno. El propio proyecto ya decidió, en 021, que
duplicar código de producción ya probado es peor que reutilizarlo; esa
misma razón no se aplicó nunca al bridge que hizo posible esa decisión.

## Criterios de éxito candidatos

1. Las funciones verificadas como idénticas entre dos o más paquetes
   (`docker_never_restart`, `get_secret`, `record_heartbeat`,
   `telegram_credentials`, y el boilerplate de resolución de
   `HOMELAB_SCRIPTS_DIR`) existen en un solo lugar, no en tres.
2. `docker_critical()` conserva el hook de test exclusivo de
   `remediacion` (`REMEDIACION_TEST_FORZAR_CRITICO`) sin filtrarse a
   `diagnostico` ni `inventory` — nunca activo salvo en remediación.
3. Las funciones genuinamente propias de un solo paquete (`ha_checks` y
   familia en diagnostico; `ha_monitor_checked_entities` y familia en
   inventory; `restart_container`/`breaker_decision`/etc. en
   remediacion) no se mueven a ningún sitio compartido — no son
   duplicación, son alcance distinto.
4. La ruptura `diagnostico` → `inventory` (evidencia/inventario.py) se
   documenta explícitamente por primera vez — con la misma exigencia de
   research.md §2 de 021 para la ruptura `remediacion` → `diagnostico` —
   o se revierte, si se decide que no debía haber ocurrido.
5. Cero cambio de comportamiento observable para los tres paquetes.

## Fuera de alcance

- Las funciones de un solo paquete (HA, remediación de contenedores,
  correcciones del dashboard) no se tocan salvo mover su ubicación
  dentro del mismo fichero si el refactor lo exige.
- No se decide aquí si `remediacion`/`diagnostico` deberían importar de
  `inventory` para algo más — solo se documenta lo que ya existe.
