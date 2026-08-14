# Research — Clasificación de Remediación en Inventario

**Feature**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Sin ningún `NEEDS CLARIFICATION` pendiente en el Technical Context del
plan — las decisiones de diseño reales de este feature se resolvieron
antes de escribirlo, en las 4 preguntas de la sesión de
`/speckit-specify` (ver spec.md, Clarifications). Este documento cubre
las decisiones de implementación que quedaban abiertas al pasar de
spec a plan.

## §1 — Cómo se evalúa un contenedor crítico sin duplicar `evaluar_contenedor()`

**Decisión**: `comprobar_reiniciar_contenedor()` deja de excluir a los
críticos de la lista que recorre; para cada uno, llama a la misma
`evaluar_contenedor()` ya existente, pero con un parámetro nuevo
`modo_forzado="manual"` que, si se pasa, ignora por completo
`get_modo_contenedor()` — nunca se consulta la configuración para un
crítico, ni siquiera para comprobar si alguien la puso en
`"automatico"` a mano (eso ya lo impide `store.set_modo_contenedor`,
§2, pero la función de evaluación no debe *depender* de que esa guarda
exista en otro sitio — defensa en profundidad).

**Alternativas consideradas**:
- Una función `evaluar_contenedor_critico()` separada, duplicando la
  orquestación (`congelar_vivo` → presupuesto → DeepSeek → parsear →
  persistir). Rechazada: es exactamente el patrón que 021 (research.md
  §4) decidió evitar para `docker_monitor.restart_container()` —
  duplicar lógica ya probada arriesga que las dos copias diverjan.
- Una tabla `configuracion_contenedor` con un valor de modo adicional
  `"manual_forzado"` solo para críticos. Rechazada: añade un tercer
  valor a `MODOS` (hoy `("manual", "automatico")`) para una distinción
  que no necesita persistirse — la criticidad ya la sabe
  `docker_critical()` en cualquier momento, no hace falta guardarla
  dos veces (mismo principio que FR-002 del spec: nunca mantener una
  clasificación aparte de su fuente real).

## §1b — Cómo se prueba el camino de críticos sin tocar un crítico real

**Decisión**: `_homelab_bridge.docker_critical()` gana un añadido de
prueba: si `REMEDIACION_TEST_FORZAR_CRITICO` está en el entorno (lista
separada por comas), esos nombres se añaden al conjunto que devuelve
`docker_monitor.CRITICAL`, sin tocar la lista real. Mismo patrón ya
aceptado que `REMEDIACION_TEST_FORZAR_FALLO`/`REMEDIACION_DEEPSEEK_MOCK`
(021) — nunca activo salvo que alguien lo exporte a propósito, y
documentado como hook de pruebas, no como configuración de producción.

**Rationale**: sin esto, validar FR-008/FR-009/FR-010 exigiría o bien
un contenedor de prueba con nombre `homeassistant`/`traefik`/etc.
(confuso y arriesgado — un `docker ps` real mostraría un contenedor de
prueba con nombre de uno crítico) o bien tocar temporalmente
`docker_monitor.CRITICAL` en la infraestructura privada del homelab
(fuera de este repo, y no algo que un `quickstart.md` deba pedirle a
Miquel que haga). Una variable de entorno que solo *añade* nombres
arbitrarios de prueba al conjunto de críticos, sin acceso a la lista
real ni a `docker_monitor.py`, resuelve las dos.

## §2 — Por qué la guarda en `store.set_modo_contenedor()`, no solo en `acciones.py`

**Decisión**: `set_modo_contenedor(conn, contenedor, modo)` consulta
`bridge.docker_critical()` y lanza `ValueError` si `modo == "automatico"`
y el contenedor está en esa lista — antes de escribir nada. El CLI
(`remediacion.cli modo-c`) deja pasar la excepción como error de
usuario (mismo patrón que ya usan `aprobar`/`rechazar` con
`ValueError` para "intento no existe").

**Rationale**: FR-008 es NO NEGOCIABLE (deriva de la regla 3 del
`CLAUDE.md` general y del Principio VII enmendado). Una sola guarda en
`acciones.py` (§1) protege la evaluación automática, pero no impide
que alguien ejecute `remediacion.cli modo-c homeassistant automatico`
por error y deje esa fila persistida, aunque nunca se llegue a usar —
un futuro cambio en `acciones.py` que confiara en la tabla sin
recordar el forzado de §1 sería una regresión silenciosa. Dos guardas
independientes (una en el punto de escritura, otra en el punto de
evaluación) hacen que ninguna de las dos, por sí sola, sea la única
línea de defensa de una garantía NO NEGOCIABLE — mismo criterio que ya
aplica el proyecto a `docker_critical()`/`docker_never_restart()` en
`comprobar_reiniciar_contenedor()` (comprobados antes de construir la
evidencia, no después).

## §3 — Forma del bloque `contenedores[]` en el snapshot

**Decisión**: `escribir_snapshot()` (ya existente, 020) gana una clave
`contenedores`, lista de objetos:

```json
{
  "nombre": "beszel",
  "critico": false,
  "never_restart": false,
  "clasificacion": "ia",
  "modo": "automatico",
  "intento_vigente": {
    "estado": "ejecutado",
    "detalle": "reiniciado y verificado",
    "creado_en": "2026-08-14T10:03:00+00:00"
  }
}
```

`clasificacion` se deriva con `clasificacion.clasificar_contenedor()`
(§4) — nunca se lee de una columna persistida. `modo` es `null` para
un contenedor crítico o `NEVER_RESTART` (no aplica: no hay modo
configurable). `intento_vigente` es `null` si no hay ningún intento
sin resolver (o resuelto en el propio ciclo de 5 min) para ese
contenedor — mismo criterio de "vigente" ya usado en 019/021 para
decidir si crear un intento nuevo (`intento_reciente_pendiente_o_sin_evaluar`).

**Alternativas consideradas**: exponer `intentos_reinicio` completo
(todo el historial) en el snapshot. Rechazada — el dashboard no
necesita historial para pintar el estado actual de una alarma activa
(US3 del spec); el historial completo ya es consultable por el CLI
(`remediacion.cli historial`) si hace falta, sin ensanchar un fichero
que se reescribe cada 5 min.

## §4 — `clasificacion.py`: módulo puro, sin I/O

**Decisión**: dos funciones, sin dependencias de `sqlite3` ni de red:

```python
def clasificar_contenedor(nombre: str, criticos: set[str], never_restart: set[str], modo: str | None) -> str:
    """"Manual" si nombre está en criticos o never_restart (modo se ignora).
    Si no, "IA" siempre — con independencia de modo (FR-004)."""

def clasificar_log(modo: str) -> str:
    """"Automática" si modo == "automatico", si no "Manual" (FR-005)."""
```

**Rationale**: FR-002 exige que la clasificación se derive de la
configuración real, nunca se mantenga aparte — hacerlo con funciones
puras, llamadas en el momento de generar el snapshot, es la forma más
directa de garantizar eso: no hay ningún sitio donde una clasificación
pueda quedar desincronizada de su fuente, porque no se guarda en
ningún sitio. Separado de `acciones.py` (que sí tiene I/O) para que
los tests de clasificación (`test_remediacion_clasificacion.py`) no
necesiten una conexión SQLite ni mocks de red — casos de tabla puros,
igual que ya se prueba `breaker_decision()` en 021.

Las categorías sin acción real (`entidad_ha`, `integracion`,
`host_externo`, `hermes`, `telegram`) no tienen función de
clasificación propia en este módulo — el valor por defecto ("Manual")
lo aplica el dashboard cuando no encuentra al componente en ningún
bloque del snapshot (`contenedores[]`/`logs[]`), no una tercera
función que siempre devuelva la misma constante (FR-003: no se
construye nada nuevo para lo que no tiene acción).
