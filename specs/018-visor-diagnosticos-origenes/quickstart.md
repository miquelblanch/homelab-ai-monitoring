# Quickstart — Generalizar el Visor de Diagnósticos a los 9 Orígenes Restantes

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/api-diagnostico.md](./contracts/api-diagnostico.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- Copia de seguridad de `app.py` hecha antes de editar (research.md
  §5).
- El contenedor `homelab-dashboard` reconstruido con el cambio de este
  feature: `cd /Volumes/FastData/homelab/docker/homelab-dashboard &&
  docker compose up -d --build`.
- `diagnostico.db` con al menos un episodio real por origen —
  `episodios` ya tiene, al escribir este quickstart, contenedor
  (`beszel`), disco (`FastData`) y latido (`docker-monitor`); el resto
  se congela/diagnostica en el propio escenario si hace falta.

## Escenario 1 — El emparejamiento de contenedor vuelve a funcionar (User Story 1, SC-001)

```bash
docker exec homelab-dashboard python3 -c "
from app import get_diagnostico_para_origen
print(get_diagnostico_para_origen('contenedor', 'beszel'))
"
```

**Resultado esperado**: un dict con `conclusion_tipo` — no una
excepción `no such column: contenedor`. Abrir la pestaña Alarmas (si
`beszel` está caído ahora mismo) y comprobar que la sección de
diagnóstico aparece — mismo resultado visual que ya validó 008 en su
momento, ahora recuperado.

## Escenario 2 — Un origen con identidad estable y sin ventana (User Story 2)

```bash
docker exec homelab-dashboard python3 -c "
from app import get_diagnostico_para_origen
print(get_diagnostico_para_origen('disco', 'FastData'))
"
```

**Resultado esperado**: el diagnóstico más reciente de `disco`/
`FastData` (episodio 15 o 18 al escribir esto), aunque su fecha no
coincida exactamente con "ahora" — sin ventana que aplicar (research.md
§3). Repetir con `latido`/`docker-monitor` (episodio 58, feature 017)
para confirmar el mismo patrón con un origen sin modo diferido.

## Escenario 3 — HA usa `cid`, no la etiqueta de pantalla (User Story 2)

```bash
PYTHONPATH=/Volumes/FastData/homelab/homelab-ai-monitoring/src \
  python3 -m diagnostico.cli congelar --ha-vivo bateria_cerradura
# anotar EPISODIO_ID, diagnosticarlo
PYTHONPATH=/Volumes/FastData/homelab/homelab-ai-monitoring/src \
  python3 -m diagnostico.cli diagnosticar <EPISODIO_ID>

docker exec homelab-dashboard python3 -c "
from app import get_diagnostico_para_origen
print(get_diagnostico_para_origen('ha', 'bateria_cerradura'))
"
```

**Resultado esperado**: encuentra el episodio recién diagnosticado —
prueba de que el emparejamiento usa el `cid` real, no `label`
("Batería cerradura" o como se muestre en pantalla).

## Escenario 4 — Un origen singleton sin identidad (User Story 3)

```bash
PYTHONPATH=/Volumes/FastData/homelab/homelab-ai-monitoring/src \
  python3 -m diagnostico.cli congelar --backup-vivo
PYTHONPATH=/Volumes/FastData/homelab/homelab-ai-monitoring/src \
  python3 -m diagnostico.cli diagnosticar <EPISODIO_ID>

docker exec homelab-dashboard python3 -c "
from app import get_diagnostico_para_origen
print(get_diagnostico_para_origen('backup', None))
"
```

**Resultado esperado**: encuentra el episodio recién diagnosticado —
sin pasar ningún nombre, el más reciente de ese origen. Repetir con
`hub_beszel`/`None` (`congelar --hub-beszel-vivo`).

## Escenario 5 — Crons de Hermes nunca llevan diagnóstico (Edge Case, SC-005)

```bash
curl -s http://192.168.4.87:8888/api/data | \
  python3 -c "
import json, sys
d = json.load(sys.stdin)
crons = [a for a in d['alarms']['items'] if a['tipo'] == 'cron_con_error']
print(all(a['diagnostico'] is None for a in crons), len(crons))
"
```

**Resultado esperado**: `True` — ninguna alarma de cron lleva
diagnóstico, sin importar cuántas haya.

## Escenario 6 — Relay solo empareja si se diagnosticó en vivo por nombre (Edge Case)

```bash
PYTHONPATH=/Volumes/FastData/homelab/homelab-ai-monitoring/src \
  python3 -m diagnostico.cli congelar --relay-historico "2026-08-01T12:00:00"
# diagnosticar ese episodio en diferido

docker exec homelab-dashboard python3 -c "
from app import get_diagnostico_para_origen
print(get_diagnostico_para_origen('relay', 'algun-relay-concreto'))
"
```

**Resultado esperado**: `None` — un episodio en diferido nunca tiene un
nombre de relay concreto en `componente` (el diferido de relay se
congela por `MOMENTO_ISO`, no por nombre), así que nunca empareja con
una alarma de un relay nombrado. Repetir con `--relay-vivo NOMBRE`
sobre el mismo nombre de la alarma real: ese sí debe emparejar.

## Escenario 7 — Una alarma sin diagnóstico no cambia (regresión, SC-006)

Cualquier alarma activa de un origen/componente sin ningún episodio
diagnosticado real. **Resultado esperado**: se ve exactamente igual que
antes de este feature — sin sección de diagnóstico, vacía ni rota.

## Verificación de salud del contenedor tras el cambio

```bash
docker ps --filter name=homelab-dashboard --format "{{.Names}}: {{.Status}}"
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.4.87:8888/api/data
```

**Resultado esperado**: `Up ... (healthy)` y `200` — el fichero editado
sin control de versiones no ha roto el arranque del contenedor.
