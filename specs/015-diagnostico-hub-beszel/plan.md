# Implementation Plan: Generalizar el Diagnóstico al Hub de Beszel

**Branch**: `015-diagnostico-hub-beszel` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-diagnostico-hub-beszel/spec.md`

## Summary

Generalizar `src/diagnostico/` (007, generalizado a discos en 009, HA
en 010, backups en 011, relays en 012, inventario en 013 y hosts
externos en 014) para que un `Episodio` pueda ser también del propio
hub de Beszel: un octavo valor de `origen` (`"hub_beszel"`, sin
migración de esquema). **Sin identificador de componente**, igual que
backup (011): solo existe un hub, así que `congelar
--hub-beszel-vivo`/`--hub-beszel-historico MOMENTO_ISO` no llevan
ningún nombre — `componente=momento.isoformat()` en ambos modos, mismo
patrón exacto que `_congelar_backup()`. Reutiliza casi toda la
infraestructura ya construida en 014: `BESZEL_HOSTS_JSON`/
`BESZEL_HOSTS_MAX_AGE_S` para la evidencia en vivo (replica
`app.py::get_beszel_hub_status()` — sano solo si **no todos** los
sistemas registrados están caducados a la vez), y el mismo patrón de
`docker run` parametrizado + `_resumen_system_stats()` para la
evidencia en diferido, ahora consultando **todos** los sistemas del
hub en vez de uno solo. Hallazgo real de la investigación previa: la
avería que validó 014 (routing de contenedores roto, 30 jul-7 ago)
nunca afectó a los 3 sistemas a la vez (`Mac Mini Server` no tuvo
ningún hueco, su agente es local) — este feature arranca **sin** línea
base real de "hub caído" (research.md §6), a diferencia de 012/013/014.
El gasto diario sigue siendo un único acumulado compartido (FR-007) —
`gasto.py` no cambia. `store.py` tampoco cambia.

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a
007-014)

**Primary Dependencies**: Ninguna nueva — reutiliza `zoneinfo` (ya
añadida en 014) y el mismo patrón `docker run` parametrizado ya
construido en 014, generalizado a consultar todos los sistemas en vez
de uno.

**Storage**: `diagnostico.db` existente, **sin migración de esquema**
(research.md §1). Lectura de las mismas dos fuentes que 014
(`beszel_hosts.json` para vivo, el hub de Beszel vía `docker run` para
diferido) — ninguna fuente nueva, solo una forma distinta de leerlas
(todos los sistemas, no uno filtrado).

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
007-014 — nuevos casos en `test_evidencia.py` (`_hub_beszel_actual()`
contra un `beszel_hosts.json` de prueba con varias combinaciones de
antigüedad, `_resumen_por_sistema()` contra filas simuladas) y
`test_deepseek.py`, sin tocar Docker real ni el hub real en el
selftest.

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007-014.

**Project Type**: Extensión de `src/diagnostico/` ya existente —
ningún paquete nuevo.

**Performance Goals**: Sin cambios respecto a 014 — mismo coste de
`docker run` (contenedor `python:3.11-alpine` ya cacheado), ahora sin
filtro de `system` en la consulta (todos los sistemas registrados, hoy
3, un volumen de datos comparable al de un solo sistema en 014).

**Constraints**: La evidencia en diferido nunca afirma que el hub
entero está caído solo porque algunos sistemas no tengan muestras —
se resume por sistema, y `todos_sin_muestras` es el único campo que
puede sugerir un fallo total, calculado explícitamente (nunca
inferido por el modelo a partir de una lista parcial) — spec.md
FR-006a, research.md §5.

**Scale/Scope**: Igual que 007-014 — un usuario, uso manual y
esporádico. **Sin línea base real de un "hub caído" disponible desde
el arranque** (spec.md SC-005, research.md §6) — a diferencia de
012/013/014, este feature vuelve a la situación de 009/010/011: la
validación depende de `--vivo` contra el estado sano actual, con la
ausencia de línea base documentada explícitamente, no oculta.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que `app.py::get_beszel_hub_status()` (Frente 1, feature 003) ya calcula. |
| II. Salud por Resultado | Sí, por diseño | En vivo reutiliza el mismo cálculo de `sano` que ya usa el dashboard (antigüedad de cada sistema, nunca recalculado con otra lógica) — mismo criterio que `ha_check_status`/`host_externo_actual`. |
| III. Estado Esperado Declarado | No aplica | El estado esperado (qué significa "el hub sigue vigilando algo") ya lo declara `get_beszel_hub_status()`, este feature solo lo lee. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007-014. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre Beszel en este feature — solo lectura de solo lectura. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca actúa sobre Beszel — solo `SELECT` parametrizado y lectura de un fichero ya escrito por otro proceso. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007-014, ahora también para episodios del hub. |
| IX. Mejora Medida Contra la Línea Base | Sí, con la limitación documentada explícitamente | Sin línea base real de "hub caído" (research.md §6) — comprobado activamente que la avería de 014 no aplica aquí, no una omisión; mismo tratamiento honesto que 009/010/011 tuvieron al arrancar. |
| X. Local por Defecto | Sí, sin categoría de dato nueva | Misma naturaleza de datos que 014 (métricas de rendimiento, nombres de sistema) — sin IPs ni topología nueva. |
| XI. Reproducibilidad Diferida | Sí | `system_stats` es un histórico ya escrito — la misma `MOMENTO_ISO` produce siempre la misma ventana consultada. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí, con un límite explícito | FR-010 es una restricción nueva: el feature diagnostica el hub como conjunto, nunca un host individual (eso es 014, ya cerrado) — evita duplicar el origen anterior. |

**Resultado**: PASS. Único riesgo real — Principio IX sin línea base
real— se documenta explícitamente en spec.md/research.md, no se
esconde ni se inventa un caso sintético para evitarlo.

## Project Structure

### Documentation (this feature)

```text
specs/015-diagnostico-hub-beszel/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md             # Contrato del CLI generalizado — supersede
│                            # la parte de `congelar` de
│                            # specs/014-diagnostico-hosts-externos/contracts/cli.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado por 009-014 y ahora por 015 — mismo paquete
├── __init__.py
├── cli.py                # + flags --hub-beszel-vivo/--hub-beszel-historico
├── model.py                # SIN CAMBIOS de esquema — `origen` ya admite 'hub_beszel' (TEXT libre desde 009);
│                             # solo se actualiza el docstring de Episodio
├── evidencia.py             # + congelar_hub_beszel_vivo/congelar_hub_beszel_historico,
│                              # + _hub_beszel_actual (reutiliza BESZEL_HOSTS_JSON/BESZEL_HOSTS_MAX_AGE_S de 014),
│                              # + _consultar_beszel_hub_todos_sistemas (generaliza _consultar_beszel_hub de 014),
│                              # + _resumen_por_sistema (reutiliza _resumen_system_stats de 014)
├── deepseek.py                # prompt generalizado una octava vez, + cláusula FR-006a propia
├── gasto.py                    # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                     # SIN CAMBIOS — sin migración de esquema
└── _homelab_bridge.py            # SIN CAMBIOS — este feature no puentea ningún script nuevo

tests/selftest/
├── test_evidencia.py       # + casos de _hub_beszel_actual, _consultar_beszel_hub_todos_sistemas (simulado),
│                             # _resumen_por_sistema, congelar_hub_beszel_vivo/historico
├── test_deepseek.py         # + caso de prompt para origen="hub_beszel" + cláusula FR-006a
└── (test_store.py, test_gasto.py — SIN CAMBIOS)
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — mismo razonamiento que 009-014. Es el feature
con menos infraestructura nueva de toda la serie: reutiliza
`BESZEL_HOSTS_JSON`, `BESZEL_HOSTS_MAX_AGE_S`, `BESZEL_HUB_VOLUME`,
`_docker_bin()`, `_a_utc_madrid()` y `_resumen_system_stats()` tal
cual de 014 — solo generaliza `_consultar_beszel_hub()` para no
filtrar por sistema y añade `_hub_beszel_actual()`/
`_resumen_por_sistema()` como las dos piezas genuinamente nuevas.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
