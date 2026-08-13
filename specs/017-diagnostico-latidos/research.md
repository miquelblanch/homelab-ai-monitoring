# Research — Generalizar el Diagnóstico a los Latidos de Monitores

**Feature**: [spec.md](./spec.md)

## §1 — Sin migración de esquema: `origen` ya es TEXT libre

**Decisión**: `episodios.origen` gana un décimo valor real, `'latido'`,
sin ningún `ALTER TABLE` — misma situación que 010 §1/011 §1/012
§1/013 §1/014 §1/015 §1/016 §1.

## §2 — Sin ningún modo diferido: comprobado, no asumido

**Hallazgo real**, comprobado explícitamente antes de escribir el
spec (`BRIEFING.md`, "Feature 017 — material de partida"):

1. `heartbeat.py::write()` escribe `<job>.json` en
   `MONITOR_HEARTBEATS_DIR` en cada ciclo de la tarea — el fichero se
   **sobreescribe entero** cada vez, sin ningún historial (comprobado
   leyendo `heartbeat.py`, líneas 209-244 del repo privado del
   homelab).
2. Ninguna base de datos del homelab tiene una tabla histórica de
   latidos — ni `homelab.db` (que solo tiene `restart_history` de
   contenedores Docker) ni ningún otro fichero.
3. Uptime Kuma sí guarda historial para los jobs que le llegan con
   `push=True` (`metrics-retention` por el manifiesto, `telegram-monitor`
   por un `push=True` explícito en su llamada) — pero corre en una
   máquina externa (`192.168.4.25`) sin ruta directa desde los
   contenedores de este Mac (mismo problema de red ya documentado para
   el hub de Beszel en 014/015). De los 8 jobs de `MONITOR_JOBS` (la
   lista elegida para este origen, ver Assumptions de spec.md), solo
   `telegram-monitor` pushea — no merece la pena construir un mecanismo
   de consulta a Kuma para un único job de ocho, y menos aún cuando ni
   siquiera es alcanzable desde aquí de la misma forma que sí lo es el
   propio `data.db` de Beszel (que corre en Docker local, 014/015).

**Decisión**: no se construye ningún mecanismo diferido, ni se empieza
a archivar histórico en `heartbeat.py` — eso sería ampliar la
vigilancia (Frente 1), no diagnosticar lo que ya existe (Frente 2),
mismo criterio que ya excluyó ampliar vigilancia de relays en 012
(FR-010 de esa feature) y de agentes en 016 (research.md §2 de 016).
`congelar` no expone ningún flag `--latido-historico` — el contrato
del CLI no debe sugerir una capacidad sin datos reales que la
respalden (FR-011).

## §3 — Evidencia en vivo: replica `app.py::get_monitor_heartbeats()` para un `job` concreto

**Decisión**: `_latido_actual(job)` busca `job` en una constante nueva,
`MONITOR_JOBS` (lista de `(job, label, max_age_s)`, copiada literal de
`app.py::MONITOR_JOBS`, fuera de este repo — 8 entradas). Si `job` no
está entre los 8, devuelve `None` — mismo criterio que un `label`
inexistente en 016. Si está, lee `MONITOR_HEARTBEATS_DIR / f"{job}.json"`
y calcula:

```python
age_s = datetime.now().timestamp() - data.get("epoch", 0)
ok = age_s <= max_age_s
```

**Hallazgo real no obvio, comprobado leyendo el código exacto de
`get_monitor_heartbeats()` (líneas 714-732 del repo privado) antes de
implementar**: el cálculo de `ok` depende **únicamente** de la edad del
latido — **nunca** del campo `status` que también guarda cada
`<job>.json` (`"ok"` o `"error"`). Un job que late a tiempo pero cuyo
último ciclo terminó en `status: "error"` se muestra `ok: true` en el
dashboard hoy. Esto es *distinto* del propio `heartbeat.py::report()`
(el que usa `heartbeat.py --report` y el informe de Telegram), que sí
combina `fresco and status == "ok"` — una **tercera** inconsistencia
real entre los dos mecanismos, además de la de §2 de `BRIEFING.md`
("Feature 017 — material de partida"). Se replica aquí el cálculo
exacto de `get_monitor_heartbeats()` (Principio II: reutilizar el
veredicto ya calculado, el del dashboard, que es el elegido en
Assumptions) — `status` se incluye en el snapshot como campo
informativo adicional, nunca como parte del cálculo de `ok`, y el
prompt se lo advierte explícitamente al modelo (research.md §4) para
que no "corrija" el veredicto combinando ambos campos por su cuenta.

## §4 — Prompt de DeepSeek: generalizado una décima y última vez, con una cláusula nueva

**Decisión**: `_PROMPT_INSTRUCCIONES` añade "...o el latido de un
monitor del propio homelab (feature 017:
specs/017-diagnostico-latidos/) — si ha latido, hace cuánto, y su
último detalle" a la lista ya existente.

**Cláusula nueva, `_PROMPT_CLAUSULA_LATIDO_ESTADO`** — mismo patrón que
`_PROMPT_CLAUSULA_HA_ESTADO` (010): el campo `latido_actual.ok` es el
veredicto YA CALCULADO de si este latido está a tiempo (mismo cálculo
que ya hace `app.py::get_monitor_heartbeats()`), no se recalcula a
partir de `status` ni de ningún otro campo — necesaria precisamente por
el hallazgo de §3 (`ok` y `status` pueden discrepar, y el modelo no
debe "corregir" el veredicto combinándolos).

**`es_critico` para latido — siempre `False`**: igual que todos los
orígenes anteriores.

## §5 — CLI: un único flag, sin par diferido

**Decisión**:

```
python3 -m diagnostico.cli congelar --latido-vivo JOB
```

`JOB` es un identificador simple sin espacios (`docker-monitor`,
`bautista-calendar`) — no necesita entrecomillado especial. **No
existe `--latido-historico`** — segundo origen del proyecto sin su
flag `--ORIGEN-historico` (el primero fue `agente` en 016,
research.md §2, FR-011).
