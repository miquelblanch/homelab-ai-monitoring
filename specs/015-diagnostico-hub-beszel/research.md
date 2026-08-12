# Research — Generalizar el Diagnóstico al Hub de Beszel

**Feature**: [spec.md](./spec.md)

## §1 — Sin migración de esquema: `origen` ya es TEXT libre

**Decisión**: `episodios.origen` gana un octavo valor real,
`'hub_beszel'`, sin ningún `ALTER TABLE` — misma situación que
010 §1/011 §1/012 §1/013 §1/014 §1.

## §2 — Sin identificador de componente, igual que backup (011)

**Decisión**: `componente = momento.isoformat()` en ambos modos —
mismo patrón exacto que `_congelar_backup()` de 011: no hay ningún
componente que nombrar, solo existe un hub. El CLI no lleva ningún
`NOMBRE` (`--hub-beszel-vivo` es un flag booleano, mismo tipo que
`--backup-vivo`).

## §3 — Evidencia en vivo: replica `app.py::get_beszel_hub_status()`, reutilizando las constantes de 014

**Decisión**: `_hub_beszel_actual()` lee `hub_systems` de
`BESZEL_HOSTS_JSON` (constante ya definida en 014, sin duplicar) y
calcula, para cada sistema, `age_s`/`stale` contra
`BESZEL_HOSTS_MAX_AGE_S` (900s, misma constante exacta de 014) — mismo
cálculo, campo a campo, que `get_beszel_hub_status()`:

```python
sano = bool(systems) and not all(s["stale"] for s in systems)
```

Devuelve `{"systems": [...], "sano": bool}`. Si `hub_systems` está
vacío o el fichero no existe, `systems == []` y `sano = False`
(ausencia total de datos no es "sano", Principio II) — mismo criterio
que ya documenta `get_beszel_hub_status()` en su propio docstring.

**Por qué no hace falta comprobar el latido aparte**: a diferencia de
`_host_externo_actual()` (014 §3, que sí exige latido fresco además
del dato), `get_beszel_hub_status()` nunca lo comprueba — y no hace
falta: si `beszel_hosts_monitor.py` deja de ejecutarse, los `updated`
capturados quedan congelados en el valor de la última pasada, así que
`age_s` sigue creciendo igual y acaba superando el umbral. El mismo
mecanismo ya detecta "Beszel realmente colgado" y "nuestro propio
lector sin ejecutarse" sin necesitar dos comprobaciones — replicado
aquí tal cual, no reinventado.

## §4 — Evidencia en diferido: todos los sistemas a la vez, generalizando `_consultar_beszel_hub()` de 014

**Decisión**: `_consultar_beszel_hub_todos_sistemas(inicio_utc,
fin_utc)` generaliza la función de 014 — mismo patrón de `docker run`
parametrizado, pero la consulta ya no filtra por `system`:

```sql
SELECT s.name, ss.created, ss.type
FROM systems s
LEFT JOIN system_stats ss
  ON ss.system = s.id AND ss.created BETWEEN ? AND ?
ORDER BY s.name, ss.created
```

El `LEFT JOIN` es deliberado: un sistema sin ninguna muestra en la
ventana aparece igual (con `created`/`type` a `NULL`), en vez de
desaparecer de los resultados — así se conoce la lista completa de
sistemas registrados aunque alguno no tenga datos, sin una segunda
consulta.

`_resumen_por_sistema(filas)` agrupa por nombre de sistema y reutiliza
`_resumen_system_stats()` de 014 tal cual (agnóstica al sistema desde
el principio) para cada uno:

```python
def _resumen_por_sistema(filas):
    por_sistema: dict[str, list] = {}
    for nombre, created, tipo in filas:
        por_sistema.setdefault(nombre, [])
        if created is not None:
            por_sistema[nombre].append((created, tipo))
    resumen = {n: _resumen_system_stats(m) for n, m in por_sistema.items()}
    todos_sin_muestras = bool(resumen) and all(
        r["total_muestras"] == 0 for r in resumen.values()
    )
    return {"por_sistema": resumen, "todos_sin_muestras": todos_sin_muestras}
```

## §5 — `todos_sin_muestras`: el único campo que puede sugerir un fallo total, calculado explícitamente

**Decisión**: `todos_sin_muestras` se calcula en código, nunca se deja
que el modelo lo infiera contando entradas de `por_sistema` él mismo
— mismo espíritu que el resto del motor: los veredictos ya calculables
determinísticamente se calculan en código (Principio II), no se le
pide al modelo que los recalcule. FR-006a exige además que ni siquiera
`todos_sin_muestras=true` se presente sola como "hub caído
confirmado" — sigue siendo ausencia de datos, con las mismas causas
alternativas ya identificadas en 014 §8 (fallo del agente, problema de
red, o el propio hub sin registrar) más una nueva propia de este
origen: el propio `docker run` de esta consulta pudo fallar de forma
silenciosa para *todos* los sistemas a la vez sin que sea un fallo
real de Beszel — aunque ese caso concreto ya se distingue en código
(§7, `None` vs. lista con `todos_sin_muestras=true`).

## §6 — Sin línea base real disponible: comprobado activamente, no una omisión

**Hallazgo real**: se esperaba reutilizar la misma avería que validó
014 (routing de contenedores roto, 2026-07-30 a 2026-08-07).
Comprobado en vivo contra `system_stats`: `Mac Mini Server` —el tercer
sistema que vigila Beszel, el propio Mac donde vive el hub— **no tiene
ningún hueco en todo el mes de retención** (90 muestras de `480m`
seguidas desde el 2026-07-13, sin ninguna interrupción mayor de 10h).
Tiene sentido: el agente de Beszel en el propio Mac se comunica con el
hub en local (mismo host), sin pasar por el routing de contenedores
que se rompió — la avería solo alcanzó a los 2 hosts remotos (Kuma,
AdGuard), nunca a los 3 sistemas a la vez. Es decir: durante toda esa
avería, `get_beszel_hub_status()` habría devuelto `sano=True` en todo
momento — no es un episodio válido para este origen.

**Decisión**: no se inventa un caso sintético ni se fuerza una
ventana que no refleje la realidad. spec.md SC-005 y Assumptions lo
documentan explícitamente como limitación aceptada — mismo tipo de
situación que 009/010/011 al arrancar, distinto de 012/013/014, que sí
tuvieron línea base real desde el principio.

## §7 — Consulta fallida vs. sin sistemas: misma distinción `None`/`[]` que 014 §10

**Decisión**: `_consultar_beszel_hub_todos_sistemas()` devuelve `None`
si el `docker run` falla (Docker no disponible, timeout, código de
salida distinto de 0) — nunca se le pasa `None` a
`_resumen_por_sistema()`. Si la consulta tiene éxito pero la tabla
`systems` está vacía (sin ningún sistema registrado en el hub),
devuelve `[]`, y `_resumen_por_sistema([])` produce `{"por_sistema":
{}, "todos_sin_muestras": False}` — `bool(resumen)` es `False` con
`resumen={}`, así que `todos_sin_muestras` queda `False`
deliberadamente (cero sistemas no es "todos caídos", es ausencia de
inventario — mismo tipo de matiz que ya distingue
`get_beszel_hub_status()` para el caso en vivo, §3).

## §8 — Prompt de DeepSeek: generalizado una octava vez, con cláusula FR-006a propia

**Decisión**: `_PROMPT_INSTRUCCIONES` añade "...o el propio hub de
Beszel, si deja de vigilar todos sus sistemas a la vez (feature 015:
specs/015-diagnostico-hub-beszel/)" a la lista ya existente. Cláusula
nueva (aplicable cuando `snapshot["hub_beszel_stats"]` no es `null`):
el modelo NUNCA debe presentar una ausencia parcial (algunos sistemas
sin muestras, otros con muestras) como si el hub entero estuviera
caído, y tampoco debe tratar `todos_sin_muestras=true` como prueba
concluyente sin considerar otras causas — mismo espíritu que la
cláusula de 014, adaptada a que aquí la unidad de análisis es un
conjunto de sistemas, no uno solo.

**`es_critico` para el hub — siempre `False`**: igual que todos los
orígenes anteriores.

## §9 — CLI: sin identificador, mismo patrón que backup

**Decisión**:

```
python3 -m diagnostico.cli congelar --hub-beszel-vivo
python3 -m diagnostico.cli congelar --hub-beszel-historico MOMENTO_ISO
```

`MOMENTO_ISO` sigue la misma convención que discos/HA/backups/relays/
hosts externos: hora local de Madrid, convertida a UTC internamente
(reutiliza `_a_utc_madrid()` de 014) antes de consultar el hub.

## §10 — Ventana: misma constante conceptual que 014, reutilizada con nombre propio

**Decisión**: `VENTANA_HUB_BESZEL_MINUTOS = 1440` (±24h) — mismo valor
y misma justificación que `VENTANA_HOST_EXTERNO_MINUTOS` de 014
(research.md §6 de 014: cubre 2-3 muestras `480m` esperadas en
operación sana) — constante propia, no una reutilización directa de la
de 014, para que cada origen documente su propio valor de forma
autocontenida, mismo criterio ya seguido entre `VENTANA_METRICAS_MINUTOS`
(contenedor/disco) y `VENTANA_RELAY_MINUTOS`/`VENTANA_HOST_EXTERNO_MINUTOS`
pese a compartir razonamiento.
