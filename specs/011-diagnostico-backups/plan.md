# Implementation Plan: Generalizar el Diagnóstico a los Backups

**Branch**: `011-diagnostico-backups` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-diagnostico-backups/spec.md`

## Summary

Generalizar `src/diagnostico/` (007, generalizado a discos en 009 y a
HA en 010) para que un `Episodio` pueda ser también de backup: un
cuarto valor de `origen` (`"backup"`, sin migración de esquema — igual
que con HA, `origen` ya es TEXT libre desde 009). A diferencia de los
tres orígenes anteriores, aquí no hay tabla ni API: la evidencia es el
log de texto que `backup_diario_nvme.sh` escribe por cada ejecución
(`/Volumes/FastData/homelab/logs/backup_*.log`), con solo 7 días de
retención. Investigado en vivo antes de planificar: el log más grande
real (955 KB, 9.878 líneas) es casi todo lista de ficheros de rsync
(`--itemize-changes`) sin valor diagnóstico — enviarlo entero
reproduciría el mismo problema real que ya costó 280K tokens en 010
(research.md §13 de 010, caso `sal_nivel`). Por eso este plan, desde el
diseño y no como corrección posterior, extrae solo piezas acotadas del
log: estado de cada dump de BD, el bloque fijo de estadísticas de
rsync (`--stats`), la línea `RESUMEN FINAL`, y un máximo de líneas de
anomalía. `congelar_backup_vivo`/`congelar_backup_historico` nuevas en
`evidencia.py`. Dos flags nuevos en `cli.py`
(`congelar --backup-vivo`/`--backup-historico`) — `--backup-vivo` no
lleva argumento (a diferencia de `--disco-vivo LABEL`/`--ha-vivo
CHECK_ID`, aquí solo existe una serie, la del rsync nocturno, no varias
entre las que elegir). El gasto diario sigue siendo un único acumulado
compartido (FR-007) — `gasto.py` no cambia. `store.py` tampoco cambia
— sin migración de esquema, igual que 010.

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a 007/009/010)

**Primary Dependencies**: Ninguna nueva — mismo criterio de cero
dependencias. Solo lectura de ficheros de texto ya existentes
(`pathlib`/`re`, de la librería estándar).

**Storage**: `diagnostico.db` existente, **sin migración de esquema**
(research.md §1 de 010 ya dejó `origen` como TEXT libre). Lectura
adicional de una fuente nueva, ninguna de ellas `homelab.db`: los
ficheros `/Volumes/FastData/homelab/logs/backup_*.log`, de solo
lectura — nunca escritura, nunca se toca `backup_diario_nvme.sh` ni
`/Volumes/Storage/backup/`.

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
007/009/010 — nuevos casos en `test_evidencia.py` (parseo del log,
`congelar_backup_vivo`/`congelar_backup_historico`, el límite de líneas
de anomalía) y `test_deepseek.py`, sin llamada real a DeepSeek ni tocar
logs reales en el selftest.

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007/009/010.

**Project Type**: Extensión de `src/diagnostico/` ya existente — ningún
paquete nuevo.

**Performance Goals**: Sin cambios — herramienta manual, no un monitor
periódico. El parseo de un log de hasta ~1 MB es una operación local
instantánea, sin llamada de red.

**Constraints**: El log completo de una noche **NUNCA** se envía tal
cual a DeepSeek — investigado en vivo (research.md §2): el log más
grande real de los 8 retenidos tiene 9.878 líneas, casi todas de la
lista de ficheros cambiados de rsync, sin valor diagnóstico y con
riesgo real de repetir el mismo reventón de prompt que ya ocurrió en
010. Solo se extraen piezas acotadas (research.md §3). Retención real
de 7 días (`RETENTION_DAYS` en `backup_diario_nvme.sh`) limita el
alcance de `--backup-historico`. Verificado explícitamente para el
Principio X (research.md §4): `rsync --itemize-changes` solo lista
rutas y banderas de cambio, nunca contenido de fichero — ninguna
credencial real aparece en ningún log comprobado, ni siquiera cuando
`.secrets/` se itemiza como directorio.

**Scale/Scope**: Igual que 007/009/010 — un usuario, uso manual y
esporádico. Sin corpus histórico real de fallos de backup (spec.md
Assumptions) — la validación se apoya en `--backup-vivo` contra el
estado sano actual y contra cualquier fallo real que aparezca mientras
se desarrolla.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que la Central de Alarmas (006) ya calcula sobre el heartbeat de backup. |
| II. Salud por Resultado | No aplica | Sin cambios respecto a 007/009/010. |
| III. Estado Esperado Declarado | No aplica | El estado esperado de un backup sano ya lo declara `backup_diario_nvme.sh`/`verify_backups.py` (códigos de rsync, tamaños mínimos), este feature solo lo lee. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007/009/010. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre backups en este feature. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca actúa sobre el backup (no lo repite, no borra huérfanos, no toca `/Volumes/Storage/backup/`) — solo lectura de logs ya escritos. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007/009/010, ahora también para episodios de backup. |
| IX. Mejora Medida Contra la Línea Base | Parcial, limitación reconocida | No existe línea base real de fallos de backup dentro de los 7 días retenidos (spec.md Assumptions) — validación contra el estado sano actual, mismo criterio ya aceptado por 009/010. |
| X. Local por Defecto | Sí, verificado explícitamente | research.md §4: comprobado en los logs reales que `rsync --itemize-changes` nunca expone contenido de fichero, solo rutas y banderas — ninguna credencial sale hacia DeepSeek. Lo que sale es evidencia real acotada (estado de dumps, estadísticas de rsync), mismo criterio ya aceptado para métricas/logs de contenedor y HA. |
| XI. Reproducibilidad Diferida | Sí, con límite real documentado | Un log ya escrito no cambia — `--backup-historico` sobre el mismo momento resuelve siempre al mismo fichero y produce el mismo snapshot. El límite real es la ventana de 7 días de retención, no un límite de diseño de este feature. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí | FR-010 acota el alcance a contenedores + discos + HA (ya cubiertos) + backups — generalizar a los 5 orígenes restantes (relays, hosts externos, hub de Beszel, agentes, inventario) queda para features posteriores, uno a uno, decisión explícita en `BRIEFING.md`. |

**Resultado**: PASS. El único riesgo real es el Principio IX (sin línea
base histórica dentro de la ventana de retención, igual que 009/010) —
aceptado explícitamente como limitación conocida, no una laguna sin
analizar. El riesgo de reventar el prompt con el log crudo (que sí fue
un hallazgo real no anticipado en 010) queda resuelto por diseño desde
este mismo plan, no aplazado a la implementación.

## Project Structure

### Documentation (this feature)

```text
specs/011-diagnostico-backups/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md             # Contrato del CLI generalizado — supersede
│                            # la parte de `congelar` de
│                            # specs/010-diagnostico-ha/contracts/cli.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado por 009/010 y ahora por 011 — mismo paquete
├── __init__.py
├── cli.py                # + flags --backup-vivo/--backup-historico
├── model.py                # SIN CAMBIOS de esquema — `origen` ya admite 'backup' (TEXT libre desde 009);
│                             # solo se actualiza el docstring de Episodio
├── evidencia.py             # + congelar_backup_vivo/congelar_backup_historico,
│                              # + _log_backup_mas_reciente/_log_backup_cercano,
│                              # + _parsear_log_backup (extracción acotada, research.md §3)
├── deepseek.py                # prompt generalizado una cuarta vez
├── gasto.py                    # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                     # SIN CAMBIOS — sin migración de esquema (research.md §1)
└── _homelab_bridge.py            # SIN CAMBIOS — este feature lee ficheros de logs directamente
                                    # (pathlib), no necesita ningún puente a un script del homelab

tests/selftest/
├── test_evidencia.py       # + casos de parseo de log, congelar_backup_vivo/historico,
│                             # límite de líneas de anomalía
├── test_deepseek.py         # + caso de prompt para origen="backup"
└── (test_store.py, test_gasto.py — SIN CAMBIOS)
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — mismo razonamiento que 009/010: un episodio de
backup es el mismo concepto que uno de contenedor, disco o HA,
separarlo duplicaría el motor de hipótesis, el gasto diario y la
persistencia sin ninguna ganancia real. La única pieza que **no** se
generaliza esta vez es `_homelab_bridge.py`: los tres orígenes
anteriores necesitaban leer un módulo Python externo (`docker_monitor`,
`ha_monitor`) en vivo; este feature solo necesita leer ficheros de
texto ya escritos en disco, con `pathlib` de la librería estándar — no
hay ningún script cuyo estado en memoria haga falta puentear.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
