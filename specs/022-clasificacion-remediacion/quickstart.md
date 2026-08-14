# Quickstart — Clasificación de Remediación en Inventario

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que la clasificación es correcta y de que
un contenedor crítico nunca se ejecuta sin aprobación — **sin tocar
ningún contenedor real del homelab**, crítico o no, en ningún
escenario de este documento. Todos usan un contenedor de prueba
desechable, marcado como "crítico" únicamente para la prueba vía
`REMEDIACION_TEST_FORZAR_CRITICO` (research.md §1b) — nunca uno de los
12 reales.

## Prerrequisitos

```bash
docker run -d --name remediacion-quickstart-critico alpine:latest sleep 3600
export REMEDIACION_TEST_CONTENEDOR=remediacion-quickstart-critico
export REMEDIACION_TEST_FORZAR_CRITICO=remediacion-quickstart-critico
```

Todos los escenarios usan `REMEDIACION_DEEPSEEK_MOCK` — ninguno gasta
presupuesto real ni depende de que DeepSeek esté disponible.

## Escenario 1 — Clasificación pura, sin tocar nada (User Story 1, FR-001 a FR-007)

```bash
PYTHONPATH=src python3 - <<'EOF'
from remediacion import clasificacion

criticos = {"remediacion-quickstart-critico", "homeassistant"}
never_restart = {"frigate"}

print(clasificacion.clasificar_contenedor("beszel", criticos, never_restart, "automatico"))               # ia
print(clasificacion.clasificar_contenedor("beszel", criticos, never_restart, "manual"))                    # ia (FR-004: el modo no cambia la etiqueta)
print(clasificacion.clasificar_contenedor("remediacion-quickstart-critico", criticos, never_restart, None)) # manual
print(clasificacion.clasificar_contenedor("frigate", criticos, never_restart, None))                        # manual
print(clasificacion.clasificar_log("automatico"))                                                            # automatica
print(clasificacion.clasificar_log("manual"))                                                                # manual
EOF
```

**Resultado esperado**: las seis líneas impresas coinciden con el
comentario — ninguna requiere una conexión a `remediacion.db` ni a
Docker.

## Escenario 2 — Un contenedor "crítico" caído genera una propuesta, nunca una ejecución (User Story 2, FR-008/FR-009/FR-010)

```bash
docker stop "$REMEDIACION_TEST_CONTENEDOR"

PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba: crítico caído sin motivo aparente"}' \
  python3 -m remediacion.cli comprobar-contenedores

python3 -m remediacion.cli pendientes
docker ps --filter name=remediacion-quickstart-critico
```

**Resultado esperado**: un intento `pendiente` para
`remediacion-quickstart-critico`, con `modo_en_deteccion="manual"` —
el contenedor sigue `Exited`. Repetir `comprobar-contenedores` varias
veces no crea un segundo intento (mismo criterio de "no duplicar" que
019/021) ni lo ejecuta por sí solo, por más veces que se repita.

## Escenario 3 — Fijar modo automático sobre un crítico se rechaza (FR-008, guarda de escritura)

```bash
PYTHONPATH=src python3 -m remediacion.cli modo-contenedor remediacion-quickstart-critico --automatico; echo "exit=$?"
```

**Resultado esperado**: el comando falla (código de salida distinto de
cero), con un mensaje explícito de que ese contenedor es crítico y no
admite modo automático — `configuracion_contenedor` no gana ninguna
fila con `modo="automatico"` para él (comprobable con
`contenedores --incluir-criticos`, que debe seguir mostrando
`modo: null` para este contenedor).

## Escenario 4 — Aprobar la propuesta ejecuta, con verificación real (User Story 2, cierre del ciclo)

```bash
python3 -m remediacion.cli aprobar <INTENTO_ID>
docker ps --filter name=remediacion-quickstart-critico
```

**Resultado esperado**: el contenedor de prueba está `Up` — la única
forma en que llegó a ejecutarse fue esta llamada explícita, nunca
`comprobar-contenedores` por sí solo (Escenario 2).

## Escenario 5 — El snapshot refleja la clasificación y el intento vigente (User Story 1 y 3, FR-011)

```bash
python3 -m remediacion.cli comprobar   # regenera remediacion_estado.json
cat "${REMEDIACION_SNAPSHOT_PATH:-/Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json}" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print([c for c in d["contenedores"] if c["nombre"]=="remediacion-quickstart-critico"])'
```

**Resultado esperado**: una entrada con `"critico": true`,
`"clasificacion": "manual"`, `"modo": null`, y (si se ejecuta justo
tras el Escenario 4, dentro de la ventana de "vigente") un
`intento_vigente` con `"estado": "ejecutado"`.

```bash
docker rm -f remediacion-quickstart-critico
unset REMEDIACION_TEST_CONTENEDOR REMEDIACION_TEST_FORZAR_CRITICO
```

## Autocomprobación (sin tocar Docker real en ningún caso)

```bash
python3 -m remediacion.cli --selftest
```

Añade a la cobertura ya existente de 021: `clasificar_contenedor()`/
`clasificar_log()` (casos de tabla puros, sin mocks), `comprobar_reiniciar_contenedor()`
con un crítico simulado vía `REMEDIACION_TEST_FORZAR_CRITICO` (crea
`pendiente`, nunca `ejecutado`/`fallido` directamente), `set_modo_contenedor()`
rechazando `"automatico"` para un crítico, y `escribir_snapshot()` con
el bloque `contenedores[]` completo, críticos y no críticos mezclados.
