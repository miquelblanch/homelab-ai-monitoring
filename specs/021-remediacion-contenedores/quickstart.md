# Quickstart — Remediación Asistida por DeepSeek: Contenedores

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/cli.md](./contracts/cli.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que esto funciona de extremo a extremo,
**sin tocar ningún contenedor real del homelab** en ningún escenario
de este documento. A diferencia de 019 (que sí terminaba rotando los
logs reales, con la propiedad de "nunca pierde nada" ya demostrada),
aquí ni siquiera el escenario final toca un contenedor de producción
— reiniciar algo real es una decisión operativa aparte, deliberada,
posterior a que todo esto pase, no un paso de validación guionizado.

## Prerrequisitos

Un contenedor de prueba, desechable, que no es ninguno de los 39 del
homelab:

```bash
docker run -d --name remediacion-quickstart-test alpine:latest sleep 3600
export REMEDIACION_TEST_CONTENEDOR=remediacion-quickstart-test
```

Todos los escenarios 1-5 usan la llamada real a DeepSeek **mockeada**
(`llamar_deepseek` sustituida por una respuesta de prueba controlada)
— nunca gastan presupuesto real ni dependen de que DeepSeek esté
disponible. El Escenario 6 es la única llamada real a la API.

## Escenario 1 — DeepSeek recomienda reiniciar, modo manual propone (User Story 1 y 2)

```bash
docker stop "$REMEDIACION_TEST_CONTENEDOR"

PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba: contenedor detenido sin motivo aparente"}' \
  python3 -m remediacion.cli comprobar-contenedores
python3 -m remediacion.cli pendientes
```

**Resultado esperado**: un intento `pendiente` para
`remediacion-quickstart-test`, con la recomendación y el razonamiento
de la respuesta simulada. El contenedor sigue parado — nada se
ejecuta todavía.

## Escenario 2 — Aprobar: reinicia y verifica de verdad (User Story 2, SC-005)

```bash
python3 -m remediacion.cli aprobar <INTENTO_ID>
docker ps --filter name=remediacion-quickstart-test
```

**Resultado esperado**: el contenedor de prueba está `Up`. El intento
pasa a `ejecutado`, con verificación real (no solo el código de salida
del comando de reinicio) — mismo criterio que ya usa `docker_monitor.py`.

## Escenario 3 — DeepSeek concluye que ninguna acción aplica (User Story 4)

```bash
docker stop "$REMEDIACION_TEST_CONTENEDOR"

PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": null, "razonamiento": "prueba: el log indica un problema externo que reiniciar no resolvería"}' \
  python3 -m remediacion.cli comprobar-contenedores
python3 -m remediacion.cli pendientes
```

**Resultado esperado**: ningún intento `pendiente` nuevo — el intento
se crea directamente en `sin_accion`, sin reiniciar el contenedor. Un
aviso por Telegram se dispara (verificar en el canal de pruebas, o
mockear `_notificar_*` para solo comprobar que se llamó).

## Escenario 4 — Modo automático: ejecuta sin aprobación (User Story 3)

```bash
docker start "$REMEDIACION_TEST_CONTENEDOR"
python3 -m remediacion.cli modo-contenedor remediacion-quickstart-test --automatico

docker stop "$REMEDIACION_TEST_CONTENEDOR"
PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba"}' \
  python3 -m remediacion.cli comprobar-contenedores
docker ps --filter name=remediacion-quickstart-test
```

**Resultado esperado**: el contenedor vuelve a `Up` sin ningún paso de
aprobación intermedio — `pendientes` no muestra nada nuevo, el intento
ya nace `ejecutado`.

## Escenario 5 — Cortacircuito: 3 fallos en la ventana lo detienen (User Story 4, SC-006)

```bash
export REMEDIACION_CB_VENTANA_HORAS=1  # ventana corta para poder probarlo sin esperar 6h reales

# simular 3 intentos fallidos seguidos (contenedor que no llega a levantar)
for i in 1 2 3; do
  PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba"}' \
    REMEDIACION_TEST_FORZAR_FALLO=1 \
    python3 -m remediacion.cli comprobar-contenedores
done

PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_contenedor", "razonamiento": "prueba"}' \
  python3 -m remediacion.cli comprobar-contenedores
python3 -m remediacion.cli pendientes
```

**Resultado esperado**: el cuarto intento no se ejecuta — pasa
directo a `cortacircuito`, con aviso por Telegram. `docker ps` confirma
que no hubo un cuarto intento real de `docker restart`.

```bash
docker rm -f remediacion-quickstart-test
unset REMEDIACION_TEST_CONTENEDOR REMEDIACION_CB_VENTANA_HORAS
```

## Escenario 6 — Una llamada real a DeepSeek, sin ejecutar nada (validación de integración, no de producción)

Única vez que se llama a la API real — sobre el mismo contenedor de
prueba ya recreado, nunca sobre uno de los 39 reales, y en modo
manual (nunca ejecuta sin que Miquel lo revise primero):

```bash
docker run -d --name remediacion-quickstart-test alpine:latest sleep 3600
docker stop remediacion-quickstart-test

PYTHONPATH=src python3 -m remediacion.cli comprobar-contenedores  # sin REMEDIACION_DEEPSEEK_MOCK — llamada real
python3 -m remediacion.cli pendientes
```

**Resultado esperado**: una propuesta real, con un razonamiento
generado de verdad por DeepSeek sobre la evidencia real del
contenedor de prueba (poco interesante, pero real). Confirma que
`llamar_deepseek`, el presupuesto compartido, y el parseo de la
respuesta funcionan de extremo a extremo antes de considerar el corte
real sobre `docker_monitor.py`.

```bash
docker rm -f remediacion-quickstart-test
```

**El corte real** (26 contenedores de producción pasando de
`docker_monitor.py` a `remediacion`, con su modo inicial en
`automatico`) es un paso de despliegue de `tasks.md`, ejecutado y
verificado contenedor a contenedor con ventana de mantenimiento
activa — no un escenario de este documento.

## Autocomprobación (sin tocar Docker real en ningún caso)

```bash
python3 -m remediacion.cli --selftest
```

Cubre, con `llamar_deepseek`, `docker_monitor.restart_container()` y
`docker_monitor.breaker_decision()` siempre sustituidos por dobles de
prueba (nunca Docker real, nunca la API real): `comprobar_reiniciar_contenedor()`
(excluye críticos/`NEVER_RESTART`, no duplica intentos), `evaluar_contenedor()`
(las tres conclusiones — acción recomendada, ninguna aplica, no se
pudo evaluar), el cortacircuito, y que ningún camino permite que un
contenedor crítico llegue a `_homelab_bridge.restart_container()`.
