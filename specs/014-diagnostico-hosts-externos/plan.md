# Implementation Plan: Generalizar el Diagnóstico a los Hosts Externos

**Branch**: `014-diagnostico-hosts-externos` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-diagnostico-hosts-externos/spec.md`

## Summary

Generalizar `src/diagnostico/` (007, generalizado a discos en 009, HA
en 010, backups en 011, relays en 012 e inventario en 013) para que un
`Episodio` pueda ser también de host externo: un séptimo valor de
`origen` (`"host_externo"`, sin migración de esquema). Identificador
simétrico (a diferencia de relays, igual que inventario): `NOMBRE` del
host, uno de los 2 canónicos (`"Host de Uptime Kuma"`/`"Host de
AdGuard Home (DNS primario)"`) — en vivo solo, en diferido combinado
con `MOMENTO_ISO` (`--host-externo-historico "NOMBRE@MOMENTO_ISO"`,
mismo orden que `LABEL@MOMENTO_ISO` de discos/HA). La evidencia es
asimétrica por **fuente**, no por si identifica el componente (a
diferencia de relays): en vivo, `beszel_hosts.json` +
el latido de `beszel-hosts` (research.md §3, replica exactamente la
política de frescura de 900 s que ya usa `app.py::get_external_hosts()`
— nunca recalculada de otra forma); en diferido, una consulta de solo
lectura contra la propia base de datos del hub de Beszel
(`beszel_hub_data`, `docker run` de solo lectura, mismo patrón que
`beszel_hosts_monitor.py`), resumida como densidad de muestras
(cuántas, primera, última, por resolución de retención), nunca como un
booleano "caído" inventado (FR-006a). Primera vez que este motor
necesita convertir entre husos horarios: la convención local del
motor (hora de Madrid sin marca de zona) contra el UTC real que
almacena Beszel (research.md §4). El gasto diario sigue siendo un
único acumulado compartido (FR-007) — `gasto.py` no cambia. `store.py`
tampoco cambia.

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a
007/009/010/011/012/013)

**Primary Dependencies**: `zoneinfo` de la librería estándar (nueva
para este motor — conversión Europe/Madrid → UTC, research.md §4).
Subproceso `docker run` de solo lectura contra un volumen ajeno
(`beszel_hub_data`), mismo patrón ya usado en producción por
`scripts/beszel_hosts_monitor.py` — primera vez que **este** motor
ejecuta `docker run` (los orígenes anteriores solo usaban `docker
inspect`/`docker logs`/`docker ps` vía `_run_ro()`, introspección de
contenedores ya existentes, nunca arrancar uno nuevo).

**Storage**: `diagnostico.db` existente, **sin migración de esquema**
(research.md §1). Lectura de dos fuentes nuevas: `beszel_hosts.json`
(`/Volumes/FastData/homelab/docker/homelab-orchestrator/data/`, estado
actual, sobreescrito cada 5 min) + el latido
`data/heartbeats/beszel-hosts.json`, para vivo; la tabla `system_stats`
del hub de Beszel (`beszel_hub_data`, volumen Docker, no un fichero),
para diferido. Nunca escritura en ninguna — ni en las dos fuentes de
vivo, ni en la base de datos del hub (solo `SELECT`, con parámetros,
nunca interpolación de texto en SQL).

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
007-013 — nuevos casos en `test_evidencia.py` (parseo de
`beszel_hosts.json`+latido con la política de frescura de 900s,
conversión Madrid→UTC, resumen de `system_stats` simulado) y
`test_deepseek.py`, sin tocar Docker real ni el hub real en el
selftest — la consulta a Beszel se simula con `patch.object`.

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007-013.

**Project Type**: Extensión de `src/diagnostico/` ya existente —
ningún paquete nuevo.

**Performance Goals**: Sin cambios — herramienta manual. La consulta
`docker run` contra el hub tarda unos segundos (arranque de un
contenedor `python:3.11-alpine` ya cacheado, mismo coste que ya paga
`beszel_hosts_monitor.py` cada 5 min en producción) — aceptable para
una invocación manual y esporádica.

**Constraints**: La evidencia en diferido nunca afirma que un host
estaba caído solo por ausencia de muestras — se resume como densidad
(recuento, primera/última, por tipo de resolución), nunca como un
booleano (spec.md FR-006a, research.md §5) — decisión de diseño que
evita desde el principio el mismo riesgo de listas sin acotar que
011/012/013 tuvieron que corregir con límites defensivos: aquí se
resume en vez de listar, no hay nada que acotar después.

**Scale/Scope**: Igual que 007-013 — un usuario, uso manual y
esporádico. Línea base real desde el arranque, con causa raíz ya
conocida de forma independiente (spec.md SC-005, research.md §6) — el
routing de contenedores roto del 2026-07-30 al 2026-08-07, ya
documentado en el `CLAUDE.md` general del homelab.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que `app.py::get_external_hosts()` (Frente 1) ya calcula. |
| II. Salud por Resultado | Sí, por diseño | En vivo reutiliza el veredicto ya calculado (arriba/caído/sin evidencia), nunca lo recalcula con otra lógica — mismo criterio que `ha_check_status` de 010. |
| III. Estado Esperado Declarado | No aplica | El estado esperado de cada host (qué significa "arriba") ya lo declara `beszel_hosts_monitor.py`/`app.py`, este feature solo lo lee. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007-013. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre hosts, Beszel ni el hub en este feature — solo lectura de solo lectura. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca actúa sobre un host ni sobre Beszel — solo `SELECT` contra su base de datos y lectura de ficheros ya escritos por otro proceso. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007-013, ahora también para episodios de host externo. |
| IX. Mejora Medida Contra la Línea Base | **Sí, con línea base real y causa conocida** | Primera vez en el proyecto con causa raíz externa ya documentada (spec.md SC-005), no solo con el hecho de que el episodio existió (007, 012, 013) ni con una limitación aceptada (009, 010, 011). |
| X. Local por Defecto | Sí, sin categoría de dato nueva | research.md §7: `system_stats` son métricas de rendimiento (CPU/memoria/disco/red/temperatura) y un nombre de interfaz de red, sin IPs — misma naturaleza ya aceptada para métricas de contenedor/disco desde 007. La consulta al hub nunca sale de la máquina (`docker run` local contra un volumen local). |
| XI. Reproducibilidad Diferida | Sí | Las tablas de Beszel (`systems`, `system_stats`) son un histórico ya escrito — la misma `NOMBRE@MOMENTO_ISO` produce siempre la misma ventana consultada. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí, con un límite explícito | FR-010 es una restricción nueva de este principio: el feature diagnostica los 2 hosts que `app.py::EXTERNAL_HOSTS` ya vigila, y explícitamente NO diagnostica el propio hub de Beszel (si deja de reportar sobre *todos* sus sistemas) — ese es el origen #8, con su propia investigación pendiente. |

**Resultado**: PASS. Sin riesgos de Principio IX (línea base real con
causa raíz conocida, la más fuerte de todo el proyecto hasta ahora).
Sin categoría de dato nueva para Principio X. El riesgo nuevo real
(ejecutar `docker run` en vez de solo `docker inspect`/`logs`) se
mitiga con parámetros SQL y sin interpolación de texto (research.md
§3), mismo nivel de disciplina que ya exige `_run_ro()` para los
subprocesos de Docker existentes.

## Project Structure

### Documentation (this feature)

```text
specs/014-diagnostico-hosts-externos/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md             # Contrato del CLI generalizado — supersede
│                            # la parte de `congelar` de
│                            # specs/013-diagnostico-inventario/contracts/cli.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado por 009-013 y ahora por 014 — mismo paquete
├── __init__.py
├── cli.py                # + flags --host-externo-vivo/--host-externo-historico
├── model.py                # SIN CAMBIOS de esquema — `origen` ya admite 'host_externo' (TEXT libre desde 009);
│                             # solo se actualiza el docstring de Episodio
├── evidencia.py             # + congelar_host_externo_vivo/congelar_host_externo_historico,
│                              # + _host_externo_actual (lee beszel_hosts.json + latido),
│                              # + _consultar_beszel_hub (docker run parametrizado),
│                              # + _resumen_system_stats, + _a_utc_madrid
├── deepseek.py                # prompt generalizado una séptima vez, + cláusula FR-006a
├── gasto.py                    # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                     # SIN CAMBIOS — sin migración de esquema
└── _homelab_bridge.py            # SIN CAMBIOS — este feature no puentea ningún script

tests/selftest/
├── test_evidencia.py       # + casos de _host_externo_actual, _consultar_beszel_hub (simulado),
│                             # _resumen_system_stats, _a_utc_madrid,
│                             # congelar_host_externo_vivo/historico
├── test_deepseek.py         # + caso de prompt para origen="host_externo" + cláusula FR-006a
└── (test_store.py, test_gasto.py — SIN CAMBIOS)
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — mismo razonamiento que 009-013. Las dos piezas
de infraestructura nuevas son: leer un latido de
`data/heartbeats/beszel-hosts.json` (mismo patrón `os.environ.get`
configurable que ya usan `BACKUP_LOG_DIR`/`HOMELAB_DB_PATH`) y ejecutar
`docker run` contra un volumen ajeno (nueva función dedicada, no una
ampliación de la lista blanca de `_run_ro()`, porque `docker run`
arranca un contenedor nuevo, no introspecciona uno existente — research.md §3).

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
