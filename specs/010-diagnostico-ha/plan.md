# Implementation Plan: Generalizar el Diagnóstico a Home Assistant

**Branch**: `010-diagnostico-ha` | **Date**: 2026-08-12 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-diagnostico-ha/spec.md`

## Summary

Generalizar `src/diagnostico/` (feature 007, ya generalizado a discos en
009) para que un `Episodio` pueda ser también de Home Assistant: tercer
valor de `origen` (`"ha"`, sin migración de esquema — `origen` ya es
TEXT libre desde 009). `componente` pasa a ser el `check_id` de
`ha_monitor.CHECKS` (mismo criterio que el `label` de disco). Dos
funciones nuevas de evidencia en `evidencia.py`
(`congelar_ha_vivo`/`congelar_ha_historico`), que reúnen evidencia
distinta según el `type` del check leído en vivo de `ha_monitor.CHECKS`
(vía `_homelab_bridge`, nunca copiado): historial de entidad (API REST
de HA) para los cuatro tipos `entity_*`, ficheros de corrupción + logs
del contenedor `homeassistant` para `recorder_corrupto`, y logs de ese
mismo contenedor para `api_ping` (`ha_api` — gap encontrado en
`/speckit-clarify`, Clarifications 2026-08-12). Bloqueo explícito y
duro de los 3 checks de cerradura (FR-010). Dos flags nuevos en
`cli.py` (`congelar --ha-vivo`/`--ha-historico`), mismo patrón
mutuamente excluyente que ya tienen `--disco-vivo`/`--disco-historico`.
El prompt de DeepSeek se generaliza una tercera vez. El gasto diario
sigue siendo un único acumulado compartido (FR-007) — `gasto.py` no
cambia. `store.py` tampoco cambia — a diferencia de 009, no hace falta
ninguna migración de esquema.

## Technical Context

**Language/Version**: Python 3.11 (sin cambios respecto a 007/009)

**Primary Dependencies**: Ninguna nueva — mismo criterio de cero
dependencias que 007/009. Reutiliza `urllib` (ya usado por
`deepseek.py`) indirectamente, a través de `ha_monitor.ha_get_detallado`
— este feature no vuelve a implementar la llamada HTTP a la API de HA.

**Storage**: `diagnostico.db` existente, **sin migración de esquema**
(a diferencia de 009): `episodios.origen` ya es `TEXT` libre desde la
migración de 009 (sin `CHECK` de valores permitidos), así que un tercer
valor `'ha'` no requiere `ALTER TABLE`. Lectura adicional de dos fuentes
nuevas, ninguna de ellas `homelab.db`: la API REST de Home Assistant
(vía `ha_monitor.ha_get_detallado`, credenciales ya resueltas por ese
módulo) y `docker logs`/`docker exec` sobre el contenedor
`homeassistant` (vía `ha_monitor._recorder_corrupt_files` y
`evidencia.docker_logs_tail`, ya existente) — nunca escritura sobre HA
ni sobre el contenedor.

**Testing**: `tests/selftest/`, mismo runner sin pytest ya usado por
007/009 — nuevos casos en `test_evidencia.py` (`congelar_ha_vivo`/
`congelar_ha_historico`, resolución de `check_id` a tipo de evidencia,
bloqueo de los 3 checks de cerradura) y `test_deepseek.py` (prompt
generalizado a HA), sin llamada real a DeepSeek ni a la API de HA en el
selftest (igual que 007/009).

**Target Platform**: macOS (Mac Mini M4 Pro), ejecución local bajo
demanda — sin cambios respecto a 007/009 (FR-015 de 007 sigue vigente:
nada se dispara solo).

**Project Type**: Extensión de `src/diagnostico/` ya existente — ningún
paquete nuevo.

**Performance Goals**: Sin cambios respecto a 007/009 — herramienta
manual, no un monitor periódico. El timeout de red hacia la API de HA
hereda el de `ha_get_detallado` (8 s), sin cambio propio de este feature.

**Constraints**: NO DEBE ejecutar ninguna acción sobre HA ni sobre
ningún dispositivo físico (FR-008); NO DEBE mostrarse en el dashboard
(FR-009); NO DEBE diagnosticar los 3 checks de cerradura
(`cerradura_up`, `bateria_cerradura`, `bateria_critica_cerradura`) —
bloqueo explícito con error claro al intentar `congelar`, no un
silencio ni una evidencia vacía (FR-010, distinto del caso "check
inexistente", que sí produce una evidencia vacía y un
`no_diagnosticable` honesto). El check `ha_recorder_corrupto`/`ha_api`
en modo `--ha-historico` no tiene ninguna fuente de evidencia
verdaderamente histórica (no existe un registro persistido de
"ficheros de corrupción pasados" ni de "logs de un momento pasado") —
se documenta como limitación aceptada (research.md §6), coherente con
spec.md Assumptions.

**Scale/Scope**: Igual que 007/009 — un usuario, uso manual y
esporádico. Sin corpus histórico real de incidentes de HA (spec.md
Assumptions) — la validación se apoya en `--ha-vivo` contra el estado
sano actual de cada tipo de check.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio | Aplica | Cómo lo cumple este plan |
|---|---|---|
| I. Alerta Persistente (NO NEGOCIABLE) | No directamente | No calcula ninguna alerta nueva — sigue diagnosticando bajo demanda lo que `ha_monitor.py` (feature 004) ya calcula. |
| II. Salud por Resultado | No aplica | Sin cambios respecto a 007/009. |
| III. Estado Esperado Declarado | No aplica | Sin cambios respecto a 007/009 — el estado esperado de cada check ya lo declara `ha_monitor.CHECKS` (`ok_state`, umbrales), este feature solo lo lee. |
| IV. Diagnóstico Previo a la Acción | Sí, por diseño | Sigue sin ejecutar ninguna acción (FR-008) — mismo cumplimiento por ausencia que 007/009. |
| V. Lista Cerrada de Acciones Reversibles (NO NEGOCIABLE) | Sí, por ausencia | Sin ninguna acción sobre HA en este feature. |
| VI. Reversibilidad Escrita | No aplica | Sin acciones, nada que revertir. |
| VII. Un Actor por Acción | Sí | Este feature nunca actúa sobre HA (reiniciar el contenedor, tocar el recorder, cambiar un estado) — solo lectura vía API REST y `docker logs`/`docker exec` de solo lectura. |
| VIII. Registro de Acciones e Hipótesis | Sí, reutilizado | Mismo esquema de `diagnosticos`/`hipotesis` que 007/009, ahora también para episodios de HA. |
| IX. Mejora Medida Contra la Línea Base | Parcial, limitación reconocida | No existe línea base real de incidentes de HA (spec.md Assumptions) — la validación es contra el estado sano actual, mismo criterio ya aceptado por 009 para discos. |
| X. Local por Defecto | Sí, misma justificación que 007/009 | La evidencia de HA que sale hacia DeepSeek es historial de entidad (valores/estados), ficheros de corrupción y logs del contenedor — nunca `HA_TOKEN` ni ninguna credencial. Mismo criterio ya aceptado para métricas y logs de contenedor. |
| XI. Reproducibilidad Diferida | Sí, con una excepción documentada | FR-002: mismo mecanismo de snapshot congelado. Para checks de entidad, `--ha-historico` lee la API de historial de HA para una ventana fija en el pasado — estable entre llamadas repetidas, igual que `disk_metrics`. Para `ha_recorder_corrupto`/`ha_api`, no existe una fuente de evidencia verdaderamente histórica (research.md §6) — `--ha-historico` para estos dos tipos lee el estado *actual* del contenedor bajo una etiqueta de momento pasado, limitación aceptada explícitamente y ya anticipada en spec.md Assumptions. La reproducibilidad de FR-002 en sí (diagnosticar dos veces el mismo snapshot ya congelado) no depende de esto — se cumple siempre, porque `diagnosticar` nunca vuelve a tocar HA. |
| XII. Precisión del Dashboard (NO NEGOCIABLE) | No aplica | FR-009: este feature no toca el dashboard en absoluto. |
| XIII. Cobertura Sistemática, No Anecdótica | Sí, y motivó una corrección real | FR-011 acota el alcance a contenedores + discos (ya cubiertos) + HA — generalizar a los otros 6 orígenes queda para features posteriores, decisión explícita en `BRIEFING.md`. Dentro de HA, este mismo principio es lo que hizo aflorar en `/speckit-clarify` que el check `ha_api` (tipo `api_ping`) no encajaba en ninguna de las dos categorías de evidencia previstas originalmente — quedaba fuera por descuido, exactamente el patrón que este principio existe para evitar. Corregido antes de planificar (spec.md Clarifications 2026-08-12). |

**Resultado**: PASS. El único riesgo real es el Principio IX (sin línea
base histórica, igual que 009) más la excepción documentada del
Principio XI para `ha_recorder_corrupto`/`ha_api` en modo histórico —
ambos aceptados explícitamente como limitaciones conocidas, no lagunas
sin analizar.

## Project Structure

### Documentation (this feature)

```text
specs/010-diagnostico-ha/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── cli.md             # Contrato del CLI generalizado — supersede
│                            # la parte de `congelar` de
│                            # specs/009-diagnostico-discos/contracts/cli.md
└── tasks.md               # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/diagnostico/          # feature 007, generalizado por 009 y ahora por 010 — mismo paquete
├── __init__.py
├── cli.py                # + flags --ha-vivo/--ha-historico
├── model.py                # SIN CAMBIOS de esquema — `origen` ya admite 'ha' (TEXT libre desde 009);
│                             # solo se actualiza el docstring de Episodio
├── evidencia.py             # + congelar_ha_vivo/congelar_ha_historico,
│                              # + ha_check_by_id/ha_history_window,
│                              # + CHECKS_HA_EXCLUIDOS_CERRADURA (FR-010)
├── deepseek.py                # prompt generalizado una tercera vez (ya no asume solo "contenedor o disco")
├── gasto.py                    # SIN CAMBIOS — el gasto ya es agnóstico al origen
├── store.py                     # SIN CAMBIOS — sin migración de esquema esta vez (research.md §1)
└── _homelab_bridge.py            # + ha_checks/ha_history/ha_recorder_corrupt_files
                                    # (mismo patrón que src/inventory/_homelab_bridge.py ya usa)

tests/selftest/
├── test_evidencia.py       # + casos de congelar_ha_vivo/historico, resolución por tipo de check,
│                             # bloqueo de los 3 checks de cerradura
├── test_deepseek.py         # + caso de prompt para origen="ha"
└── (test_store.py, test_gasto.py — SIN CAMBIOS)
```

**Structure Decision**: se generaliza el paquete `src/diagnostico/`
existente en el sitio — no se crea un paquete hermano nuevo, mismo
razonamiento que ya fijó 009 (research.md/plan.md de 009): contenedor,
disco y HA son el mismo concepto (un episodio, cualquiera que sea su
origen); separarlos duplicaría el motor de hipótesis, el gasto diario y
la persistencia sin ninguna ganancia real. La única pieza nueva de
infraestructura es la ampliación de `_homelab_bridge.py` para leer
`ha_monitor.py` en vivo — mismo patrón que `src/inventory/_homelab_bridge.py`
ya usa para ese mismo módulo (research.md §3), no una integración nueva.

## Complexity Tracking

*Sin violaciones que justificar — tabla omitida (Constitution Check: PASS).*
