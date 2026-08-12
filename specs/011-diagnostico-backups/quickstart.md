# Quickstart — Generalizar el Diagnóstico a los Backups

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- `.secrets/deepseek.env` con `DEEPSEEK_API_KEY` ya configurada.
- Al menos un log real en `/Volumes/FastData/homelab/logs/backup_*.log`
  — lo escribe `backup_diario_nvme.sh` cada noche a las 02:00; si hace
  más de 7 días que no corre, no habrá ninguno dentro de la retención.

## Escenario 1 — Ningún episodio existente cambia (sin migración de esquema)

```bash
cd /Volumes/FastData/homelab/homelab-ai-monitoring
PYTHONPATH=src python3 -m diagnostico.cli mostrar 6
# → debe seguir imprimiendo el episodio 6 (de 007) exactamente igual
#   que antes de este feature — sin migración de esquema (research.md §1)
```

## Escenario 2 — Diagnosticar en vivo el backup más reciente, sano (US1, SC-004)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --backup-vivo
# → "episodio N congelado (2026-08-12T02-00-00, en vivo, crítico=no)"

PYTHONPATH=src python3 -m diagnostico.cli mostrar N
# → backup_rsync_estado: "ok", backup_anomalias: [] si de verdad no hubo
#   ningún error esa noche

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → conclusión: no_diagnosticable (el backup de anoche fue limpio)
```

**Resultado esperado**: el motor reúne evidencia real de esa ejecución
concreta (no un texto genérico) y concluye honestamente que no hay
nada que diagnosticar.

## Escenario 3 — El log grande real no revienta el prompt (SC-002, research.md §3)

```bash
PYTHONPATH=src python3 -c "
from diagnostico import evidencia
snap = evidencia._parsear_log_backup(
    open('/Volumes/FastData/homelab/logs/backup_2026-08-07_02-00-02.log').read()
)
print('dumps:', len(snap['dumps']))
print('anomalias:', len(snap['backup_anomalias']))
print('rsync_estado:', snap['backup_rsync_estado'])
"
# → anomalias nunca por encima de BACKUP_ANOMALIA_MAX_LINEAS (30),
#   independientemente de que el log de origen tenga 9.878 líneas
```

**Resultado esperado**: confirma en el propio log real más grande
retenido que la extracción acotada funciona tal como se diseñó en
`research.md` §3 — no hace falta esperar a un fallo real para
comprobarlo.

## Escenario 4 — Diagnosticar en diferido dentro de la ventana de 7 días (US2, SC-001)

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --backup-historico "$(date -v-2d +%Y-%m-%dT02:00:00)"
# → episodio M congelado con el log de hace 2 días (dentro de la
#   ventana de tolerancia de ±12h, research.md §5)

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
PYTHONPATH=src python3 -m diagnostico.cli diagnosticar M
```

**Resultado esperado**: los dos `diagnosticar` de arriba concuerdan en
`conclusion_tipo` (mismo criterio que SC-001 de 007/009/010) — el log
ya escrito no cambia entre una llamada y otra.

## Escenario 5 — El gasto de backup cuenta contra el mismo límite (FR-007)

```bash
DIAGNOSTICO_LIMITE_EUR_DIA=0.0 PYTHONPATH=src python3 -m diagnostico.cli diagnosticar N
# → "no_diagnosticable: límite de gasto diario alcanzado" — el límite
#   ya consumido por diagnósticos de contenedor/disco/HA (si los hubo
#   hoy) también bloquea uno de backup
```

## Escenario 6 — Sin ningún log dentro de la ventana

```bash
PYTHONPATH=src python3 -m diagnostico.cli congelar --backup-historico "2020-01-01T02:00:00"
# → episodio congelado igual, con backup_log_path=null y evidencia vacía
#   — no es un error (contracts/cli.md)

PYTHONPATH=src python3 -m diagnostico.cli diagnosticar <ese_episodio_id>
# → no_diagnosticable, honesto
```

## Autocomprobaciones (sin tocar DeepSeek ni logs reales)

```bash
python3 -m diagnostico.cli --selftest
```

Cubre, además de lo que ya cubría 007/009/010: el parseo de un log de
backup simulado (con y sin fallos), el límite de líneas de anomalía
contra un log simulado artificialmente grande, `congelar_backup_vivo`/
`congelar_backup_historico` contra un directorio de logs de prueba en
un fichero temporal, y que el prompt generalizado sigue incluyendo
correctamente la evidencia de backup en el JSON enviado — sin ninguna
llamada real a DeepSeek ni lectura de los logs reales de producción.
