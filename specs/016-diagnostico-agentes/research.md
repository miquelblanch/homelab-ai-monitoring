# Research — Generalizar el Diagnóstico a los Agentes (LaunchAgents)

**Feature**: [spec.md](./spec.md)

## §1 — Sin migración de esquema: `origen` ya es TEXT libre

**Decisión**: `episodios.origen` gana un noveno y último valor real,
`'agente'`, sin ningún `ALTER TABLE` — misma situación que
010 §1/011 §1/012 §1/013 §1/014 §1/015 §1.

## §2 — Sin ningún modo diferido: comprobado, no asumido

**Hallazgo real**, comprobado explícitamente antes de escribir el
spec (`BRIEFING.md`, "Feature 016 — material de partida"):

1. `launchagents_raw.txt` (`/Volumes/FastData/homelab/docker/
   homelab-orchestrator/data/launchagents_raw.txt`, la fuente que ya
   lee `app.py::get_launchagents()`) lo escribe
   `dump_launchagents.sh` (`launchctl list > fichero`) cada 5 min vía
   el LaunchAgent `amsterdam9.dashboard.launchagents` — **se
   sobreescribe entero en cada ciclo**, sin ningún historial.
2. Su log (`/tmp/dump_launchagents.log`, el `StandardOutPath` del
   propio LaunchAgent) tiene 9.392 líneas — comprobado: **todas
   vacías**. `launchctl list > fichero` no produce nada en `stdout`
   por sí solo (la redirección ocurre dentro del propio comando), así
   que el log no contiene ni un solo dato real aprovechable — a
   diferencia de `dashboard-socat.log`/`beszel-hosts-reader.log`, que
   sí registraban algo (aunque fuera poco) en cada ciclo.
3. Ninguna base de datos del homelab tiene una tabla equivalente a
   `restart_history` para LaunchAgents — `docker_monitor.py` (la única
   fuente de `restart_history`) solo vigila contenedores Docker.

**Decisión**: no se construye ningún mecanismo diferido, ni se
modifica `dump_launchagents.sh` para empezar a archivar histórico —
eso sería ampliar la vigilancia (Frente 1), no diagnosticar lo que ya
existe (Frente 2), mismo criterio que ya excluyó ampliar vigilancia de
relays en 012 (FR-010 de esa feature). `congelar` no expone ningún
flag `--agente-historico` — el contrato del CLI no debe sugerir una
capacidad sin datos reales que la respalden (FR-011).

## §3 — Evidencia en vivo: replica `app.py::get_launchagents()` para un `label` concreto

**Decisión**: `_agente_actual(label)` lee `LAUNCHAGENTS_RAW`
(constante nueva, configurable), busca la línea cuyo tercer campo
(separado por tabulador) coincide exactamente con `label`, y calcula:

```python
running = pid != "-"
ok = exit_code in ("0", "-")
status = "running" if running else ("idle" if ok else "error")
```

Mismo cálculo exacto que `get_launchagents()`/`_parse_launchagents_file()`
— no se recalcula con otra lógica (Principio II). Un `label` que no
aparece en el fichero no es un error — mismo criterio ya establecido
para un identificador inexistente en cualquier otro origen: `None`, el
episodio se congela igual con evidencia vacía.

**Por qué no hace falta filtrar por `AGENT_PATTERN`** (a diferencia de
`get_launchagents()`, que sí filtra a `amsterdam9.*`/
`com.homeassistant.*`/`ai.hermes.*` para no saturar el panel del
dashboard con procesos del sistema): aquí Miquel ya pide un `label`
concreto — no hay ningún listado que filtrar, solo una búsqueda
puntual.

## §4 — Prompt de DeepSeek: generalizado una novena y última vez, sin cláusula de contenido nueva

**Decisión**: `_PROMPT_INSTRUCCIONES` añade "...o un LaunchAgent del
propio homelab (feature 016: specs/016-diagnostico-agentes/) — si
tiene un proceso activo, y su último código de salida" a la lista ya
existente. **Sin cláusula nueva de restricción de contenido**: a
diferencia de relays (012) u hosts externos/hub (014/015), aquí no hay
ninguna ambigüedad de causalidad que restringir — el estado de un
agente (`pid`/`exit_code`) es un hecho directo, no una inferencia
sobre ausencia de datos.

**`es_critico` para agente — siempre `False`**: igual que todos los
orígenes anteriores.

## §5 — CLI: un único flag, sin par diferido

**Decisión**:

```
python3 -m diagnostico.cli congelar --agente-vivo LABEL
```

`LABEL` puede contener puntos (`"amsterdam9.morning-report"`) sin
necesitar entrecomillado especial (no tiene espacios, a diferencia de
`--relay-vivo`/`--host-externo-vivo`) — aunque se acepta entrecomillado
igual, por consistencia. **No existe `--agente-historico`** —
único origen de los 9 sin su flag `--ORIGEN-historico` (research.md
§2, FR-011).
