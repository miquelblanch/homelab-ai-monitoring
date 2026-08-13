# Quickstart — Remediación Automática, Primera Pieza (Rotación de Logs)

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`). Los Escenarios
1-5 redirigen `REMEDIACION_LOGS_DIR` a un directorio de prueba con un
fichero del mismo nombre que uno real (`health-docker.log`), así que
nunca tocan los logs reales; el Escenario 6 es la única validación
contra `~/Library/Logs/` de verdad, deliberada y con la propiedad de
"nunca destruye nada" ya comprobada antes de llegar ahí.

## Prerrequisitos

```bash
export REMEDIACION_LOGS_DIR=/tmp/remediacion-quickstart
mkdir -p "$REMEDIACION_LOGS_DIR"
```

(el resto de los comandos de los Escenarios 1-5 asumen esta variable
exportada en la misma sesión de shell)

## Escenario 1 — Detectar y proponer en modo manual (User Story 1)

```bash
dd if=/dev/zero of="$REMEDIACION_LOGS_DIR/health-docker.log" bs=1m count=11 2>/dev/null  # 11 MB > umbral 10 MB

PYTHONPATH=src python3 -m remediacion.cli comprobar
PYTHONPATH=src python3 -m remediacion.cli pendientes
```

**Resultado esperado**: un intento `pendiente` para `health-docker`,
con su tamaño real y el umbral. El fichero sigue existiendo, sin
tocar (11 MB). `health-ha.log` no existe en este directorio de
prueba, así que se ignora sin lanzar (Edge Cases de spec.md).

## Escenario 2 — Aprobar: rota sin perder contenido (User Story 2, SC-003)

```bash
PYTHONPATH=src python3 -m remediacion.cli aprobar <INTENTO_ID>
ls -la "$REMEDIACION_LOGS_DIR"
```

**Resultado esperado**: `health-docker.log` ahora vacío (0 bytes);
`health-docker.log.rotado-<ISO>` con los 11 MB originales íntegros. El
intento pasa a `ejecutado`.

## Escenario 3 — Rechazar: el fichero no cambia (User Story 2)

```bash
dd if=/dev/zero of="$REMEDIACION_LOGS_DIR/health-docker.log" bs=1m count=11 2>/dev/null
PYTHONPATH=src python3 -m remediacion.cli comprobar
PYTHONPATH=src python3 -m remediacion.cli rechazar <INTENTO_ID>
```

**Resultado esperado**: el fichero sigue exactamente igual que antes
de rechazar (11 MB, sin rotar). El intento pasa a `rechazado`.

## Escenario 4 — Modo automático: ejecuta directo (User Story 3 y 4)

```bash
PYTHONPATH=src python3 -m remediacion.cli historial rotar_log
PYTHONPATH=src python3 -m remediacion.cli modo rotar_log --automatico

dd if=/dev/zero of="$REMEDIACION_LOGS_DIR/health-docker.log" bs=1m count=11 2>/dev/null
PYTHONPATH=src python3 -m remediacion.cli comprobar
PYTHONPATH=src python3 -m remediacion.cli pendientes
```

**Resultado esperado**: `historial` muestra el recuento antes del
cambio. Tras pasar a automático, `comprobar` rota `health-docker.log`
directamente — `pendientes` no muestra nada nuevo, el intento ya nace
en `ejecutado`.

```bash
PYTHONPATH=src python3 -m remediacion.cli modo rotar_log --manual  # vuelve a manual, limpieza
```

## Escenario 5 — Deshacer sin perder lo escrito después (User Story 5, SC-004)

```bash
echo "línea escrita después de la rotación" > "$REMEDIACION_LOGS_DIR/health-docker.log"
PYTHONPATH=src python3 -m remediacion.cli deshacer <INTENTO_ID_EJECUTADO_DEL_ESCENARIO_4>
cat "$REMEDIACION_LOGS_DIR/health-docker.log"
ls "$REMEDIACION_LOGS_DIR"
```

**Resultado esperado**: `health-docker.log` vuelve a contener los
11 MB originales de antes de esa rotación. La línea escrita después
de la rotación **no se pierde** — sigue existiendo en un fichero
aparte (`health-docker.log.tras-deshacer-<ISO>`).

```bash
rm -rf "$REMEDIACION_LOGS_DIR"
unset REMEDIACION_LOGS_DIR  # vuelve a apuntar a ~/Library/Logs real
```

## Escenario 6 — Validación real, contra los logs reales (única vez que se tocan)

Antes de este escenario, confirmar que `rotar_log` sigue en modo
`manual` (Escenario 4 ya lo devolvió) y que `REMEDIACION_LOGS_DIR` ya
no está exportada (apunta a `~/Library/Logs` real por defecto).

```bash
ls -la ~/Library/Logs/health-docker.log ~/Library/Logs/health-ha.log  # confirmar que siguen por encima de 10 MB

PYTHONPATH=src python3 -m remediacion.cli comprobar
PYTHONPATH=src python3 -m remediacion.cli pendientes
```

**Resultado esperado**: dos `pendiente` reales, uno por cada log.
Miquel decide si aprobar cada uno (rota de verdad, sin pérdida —
mismo procedimiento ya verificado en el Escenario 2) o dejarlos
pendientes. Ningún log se toca solo con `comprobar` — hace falta
`aprobar` explícito.

## Autocomprobación (sin tocar ningún log real)

```bash
python3 -m remediacion.cli --selftest
```

Cubre, contra logs de prueba en un directorio temporal propio (aislado
también de `REMEDIACION_LOGS_DIR` del shell, vía monkeypatch en
Python): `comprobar_rotar_log()` (por encima/por debajo del umbral, ya
`pendiente` no duplica, fichero ausente se ignora), `ejecutar_rotar_log()`
(rota sin perder contenido), `deshacer_rotar_log()` (incluido el caso
de contenido escrito después de la rotación), y las transiciones de
estado inválidas (aprobar/rechazar/deshacer sobre el estado equivocado
se rechazan).
