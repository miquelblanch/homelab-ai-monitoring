# Quickstart — Visor de Diagnósticos en Alarmas

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/api-diagnostico.md](./contracts/api-diagnostico.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- El contenedor `homelab-dashboard` reconstruido con el cambio de este
  feature (`docker compose build dashboard && docker compose up -d
  dashboard`, mismo patrón que cualquier cambio de `app.py`).
- Un contenedor real caído ahora mismo, o forzable (`docker stop
  <nombre>` sobre uno no crítico) para provocar una alarma real en la
  pestaña Alarmas.

## Escenario 1 — Diagnosticar en vivo y verlo en Alarmas (User Story 1)

```bash
docker stop qbittorrent   # o cualquier contenedor no crítico
```

Esperar a que `docker_monitor.py` lo detecte (hasta 5 min, o forzar un
ciclo manual) y aparezca en la pestaña Alarmas. Anotar el nombre.

```bash
PYTHONPATH=/Volumes/FastData/homelab/homelab-ai-monitoring/src \
  python3 -m diagnostico.cli congelar --vivo qbittorrent
PYTHONPATH=/Volumes/FastData/homelab/homelab-ai-monitoring/src \
  python3 -m diagnostico.cli diagnosticar <EPISODIO_ID>
```

Recargar la pestaña Alarmas.

**Resultado esperado**: la alarma de `qbittorrent` muestra la
conclusión del diagnóstico (causa probable con su texto, o "no se pudo
diagnosticar" con el motivo) y la fecha del episodio, sin haber
ejecutado `diagnostico.cli mostrar`.

```bash
docker start qbittorrent  # limpieza
```

## Escenario 2 — El detalle de hipótesis coincide con la CLI (User Story 2, SC-002)

```bash
PYTHONPATH=/Volumes/FastData/homelab/homelab-ai-monitoring/src \
  python3 -m diagnostico.cli mostrar <EPISODIO_ID>
```

Comparar el número de hipótesis, su descripción, comprobación y
desenlace con lo que se ve al expandir el detalle de esa misma alarma
en el dashboard.

**Resultado esperado**: coinciden exactamente — ninguna hipótesis ni
desenlace que la CLI muestre falta en el dashboard.

## Escenario 3 — El gasto diario coincide (User Story 3, SC-003)

```bash
docker exec homelab-dashboard sqlite3 /data/diagnostico.db \
  "SELECT * FROM gasto_diario WHERE dia = date('now')"
```

**Resultado esperado**: el valor de `coste_eur_acumulado` coincide con
el que se ve en la pestaña Alarmas. Si no hay fila para hoy, el
dashboard muestra `0` (no un hueco vacío).

## Escenario 4 — Una alarma sin diagnóstico no cambia (User Story 1, SC-004, regresión)

Provocar o esperar una alarma de un contenedor que no se haya
diagnosticado por CLI para esta caída.

**Resultado esperado**: esa alarma se ve exactamente igual que antes
de este feature — sin ninguna sección de diagnóstico, vacía ni rota.

## Escenario 5 — Una caída anterior ya resuelta no contamina la caída nueva (Edge Case, Clarifications Q2, SC-006)

Con `beszel` (que ya tiene varios episodios diagnosticados en
`diagnostico.db` de caídas anteriores, todas ya resueltas):

```bash
docker stop beszel   # provoca una caída NUEVA, sin diagnosticar todavía
```

**Resultado esperado**: la alarma nueva de `beszel` **no** muestra
ninguno de los diagnósticos antiguos — se ve como si no tuviera
diagnóstico asociado, hasta que se diagnostique esta caída en concreto
(Escenario 1). Confirmar con:

```bash
docker exec homelab-dashboard python3 -c "
from app import get_diagnostico_para_alarma
print(get_diagnostico_para_alarma('beszel', '<down_since real de docker_monitor_state.json>'))
"
```

debe devolver `None` hasta que se congele/diagnostique un episodio
nuevo con `ventana_inicio` cercana a ese `down_since`.

```bash
docker start beszel  # limpieza
```

## Autocomprobación del emparejamiento (sin levantar el dashboard completo)

```bash
docker exec homelab-dashboard python3 -c "
from app import get_diagnostico_para_alarma
r = get_diagnostico_para_alarma('beszel', '2026-08-11T18:50:00')
print(r)
"
```

**Resultado esperado**: o bien un dict con `episodio_fecha`,
`diagnostico_fecha`, `conclusion_tipo`, `conclusion_texto`, `hipotesis`
(research.md §3, coincide con un episodio real de `beszel` cuya
`ventana_inicio` esté dentro de 30 minutos de ese `down_since`), o
`None` si ninguno cae dentro de la tolerancia.
