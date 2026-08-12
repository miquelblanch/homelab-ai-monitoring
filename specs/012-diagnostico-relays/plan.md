# Implementation Plan: Generalizar el Diagnóstico a los Relays

**Branch**: `012-diagnostico-relays` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-diagnostico-relays/spec.md`

## Summary

Generalizar `src/diagnostico/` (007, generalizado a discos en 009, a HA
en 010 y a backups en 011) para que un `Episodio` pueda ser también de
relay: un quinto valor de `origen` (`"relay"`, sin migración de
esquema). A diferencia de los cuatro orígenes anteriores, aquí la
evidencia es **asimétrica por diseño** (decidido con Miquel,
2026-08-12): en vivo, `congelar_relay_vivo(conn, nombre)` lee el estado
actual con detalle real por relay de `socat_relays.json`; en diferido,
`congelar_relay_historico(conn, momento)` no recibe ningún nombre de
relay — parsea una ventana de `dashboard-socat.log` (sin rotación,
histórico real desde el 2026-04-29) y solo puede dar el recuento
agregado ("N de M caídos"), nunca cuál en concreto, porque ese detalle
nunca se archivó. Es el primer origen del proyecto con una línea base
real de fallos ya disponible desde el arranque (17 episodios, 2026-04-29
en adelante) — SC-005 lo mide explícitamente. Es también el primer
origen cuya evidencia contiene IPs privadas de la LAN — justificado
explícitamente para el Principio X (research.md §4), decisión tomada
con Miquel antes de diseñar el snapshot. Dos flags nuevos en `cli.py`
(`congelar --relay-vivo NOMBRE`/`--relay-historico MOMENTO_ISO`) — sin
prefijo `NOMBRE@` en el histórico, mismo criterio que 011 tuvo con
`--backup-historico`. El gasto diario sigue siendo un único acumulado
compartido (FR-007) — `gasto.py` no cambia. `store.py` tampoco cambia.

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a 007/009/010/011)

**Primary Dependencies**: Ninguna nueva — mismo criterio de cero
dependencias. Solo lectura de un fichero JSON y un fichero de texto ya
existentes (`json`/`re` de la librería estándar).

**Storage**: `diagnostico.db` existente, **sin migración de esquema**
(research.md §1 de 010). Lectura de dos fuentes nuevas, ninguna de
ellas `homelab.db`: `socat_relays.json`
(`/Volumes/FastData/homelab/docker/homelab-orchestrator/data/`, estado
actual, sobreescrito cada 5 min) y `dashboard-socat.log`
(`~/Library/Logs/`, **fuera del árbol `/Volumes/FastData/homelab/`**,
primera vez para este motor — research.md §5) — nunca escritura en
ninguna de las dos, nunca se toca `dump_socat_status.py` ni ningún
LaunchAgent de relay.

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
007/009/010/011 — nuevos casos en `test_evidencia.py` (parseo de
`socat_relays.json` y de líneas de `dashboard-socat.log`,
`congelar_relay_vivo`/`congelar_relay_historico`) y `test_deepseek.py`,
sin tocar los ficheros reales de producción en el selftest.

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007/009/010/011.

**Project Type**: Extensión de `src/diagnostico/` ya existente — ningún
paquete nuevo.

**Performance Goals**: Sin cambios — herramienta manual. Parsear
`dashboard-socat.log` (~1.8 MB, ~30.000 líneas) es una operación local
instantánea; la ventana de ±180 min alrededor de un momento acota la
evidencia a un puñado de líneas, no al fichero completo.

**Constraints**: La evidencia agregada en diferido nunca afirma qué
relay concreto falló — esa información no existe (spec.md FR-006,
Assumptions). Las IPs privadas de la LAN presentes en `desc` salen
hacia DeepSeek con justificación explícita (research.md §4, decisión
tomada con Miquel antes de diseñar el snapshot) — primera vez que este
motor envía direcciones de red, distinto de métricas/logs/estados ya
aceptados en features anteriores.

**Scale/Scope**: Igual que 007/009/010/011 — un usuario, uso manual y
esporádico. A diferencia de los cuatro orígenes anteriores, **sí** hay
línea base real desde el arranque (17 episodios reales, spec.md
SC-005) — la validación no depende solo de `--relay-vivo` contra el
estado sano actual.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que `dump_socat_status.py` (Frente 1) ya calcula. |
| II. Salud por Resultado | No aplica | Sin cambios respecto a 007/009/010/011. |
| III. Estado Esperado Declarado | No aplica | El estado esperado de cada relay (qué puerto, qué destino) ya lo declara `dump_socat_status.py::SOCAT_RELAYS`, este feature solo lo lee. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007/009/010/011. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre relays ni LaunchAgents en este feature. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca actúa sobre un relay (no reinicia su LaunchAgent, no lo reconfigura) — solo lectura de `socat_relays.json`/`dashboard-socat.log`. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007/009/010/011, ahora también para episodios de relay. |
| IX. Mejora Medida Contra la Línea Base | **Sí, con línea base real** | Primera vez en el proyecto: 17 episodios reales desde el 2026-04-29 (spec.md SC-005), no una limitación aceptada como en 009/010/011. |
| X. Local por Defecto | Sí, con justificación nueva explícita | research.md §4: la evidencia de relay incluye IPs privadas RFC1918 de la LAN — decisión tomada con Miquel antes de diseñar el snapshot (no son secretas como una credencial, sin sentido fuera de la LAN, y son justo el dato que explica si un relay apunta al destino correcto). Primera vez que este motor envía direcciones de red, distinto de las métricas/logs/estados ya aceptados. |
| XI. Reproducibilidad Diferida | Sí | `dashboard-socat.log` ya escrito no cambia — `--relay-historico` sobre el mismo momento produce siempre la misma ventana de evidencia agregada. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí, con un límite explícito | FR-010 es una restricción nueva de este principio: el feature diagnostica exactamente los 10 relays que `dump_socat_status.py` ya vigila, y explícitamente NO amplía esa vigilancia a los relays de HA descubiertos sin cubrir durante la investigación previa (HEOS, Marantz, ESPHome, Android TV, Tapo) — ese hueco es Frente 1, no este feature; anotado en `BRIEFING.md` para no perderlo. |

**Resultado**: PASS. Sin riesgos de Principio IX esta vez (línea base
real disponible). El riesgo nuevo (IPs de la LAN saliendo hacia
DeepSeek) se resolvió explícitamente con Miquel antes de diseñar el
snapshot, no como una justificación a posteriori.

## Project Structure

### Documentation (this feature)

```text
specs/012-diagnostico-relays/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md             # Contrato del CLI generalizado — supersede
│                            # la parte de `congelar` de
│                            # specs/011-diagnostico-backups/contracts/cli.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado por 009/010/011 y ahora por 012 — mismo paquete
├── __init__.py
├── cli.py                # + flags --relay-vivo/--relay-historico
├── model.py                # SIN CAMBIOS de esquema — `origen` ya admite 'relay' (TEXT libre desde 009);
│                             # solo se actualiza el docstring de Episodio
├── evidencia.py             # + congelar_relay_vivo/congelar_relay_historico,
│                              # + _relay_actual (lee socat_relays.json),
│                              # + _agregado_relays_ventana (parsea dashboard-socat.log)
├── deepseek.py                # prompt generalizado una quinta vez
├── gasto.py                    # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                     # SIN CAMBIOS — sin migración de esquema
└── _homelab_bridge.py            # SIN CAMBIOS — este feature lee ficheros directamente
                                    # (json/pathlib), no necesita ningún puente a un script

tests/selftest/
├── test_evidencia.py       # + casos de _relay_actual, _agregado_relays_ventana,
│                             # congelar_relay_vivo/historico
├── test_deepseek.py         # + caso de prompt para origen="relay"
└── (test_store.py, test_gasto.py — SIN CAMBIOS)
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — mismo razonamiento que 009/010/011. La única
pieza de infraestructura nueva es leer un fichero fuera del árbol
`/Volumes/FastData/homelab/` (`~/Library/Logs/dashboard-socat.log`) —
documentado explícitamente en Technical Context, sin que esto exija
ningún cambio de paquete ni de arquitectura, solo una ruta configurable
más (mismo patrón `os.environ.get(..., default)` que ya usan
`BACKUP_LOG_DIR`/`HOMELAB_DB_PATH`).

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
