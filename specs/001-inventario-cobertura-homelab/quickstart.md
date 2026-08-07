# Quickstart — Validar el inventario

**Feature**: [spec.md](./spec.md) · **Contratos**: [contracts/cli.md](./contracts/cli.md), [contracts/entrega.md](./contracts/entrega.md)

Guía para comprobar, de extremo a extremo, que el inventario cumple lo que
pide el spec — no es el plan de implementación (eso vive en `tasks.md`),
es cómo Miquel se convence de que funciona.

## Prerrequisitos

- Python 3.11 disponible (`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`).
- Acceso local a `docker ps`/`docker inspect` (mismo entorno que
  `docker_monitor.py`, con `DOCKER_HOST` apuntando al socket de OrbStack).
- Credenciales ya presentes en `.secrets/` (`ha.env`, `telegram.env`) —
  este feature no introduce ningún fichero de secretos nuevo (Regla 1 del
  `CLAUDE.md` del homelab general).
- Lectura del volumen de configuración de Home Assistant, para el registro
  de entidades (`research.md` §3).

## 1 — Primera ejecución (User Story 1)

```bash
python3 -m inventory.cli --no-telegram --no-dashboard
```

**Esperado**: una lista donde cada componente conocido del homelab —
contenedores, integraciones, entidades de HA, los dos hosts externos
(Uptime Kuma, AdGuard Home), Hermes/Bautista, el canal de Telegram, y la
propia infraestructura de monitorización — aparece con las tres respuestas
rellenas. Ninguna fila en blanco (`FR-001` a `FR-010`). Corresponde al
escenario de aceptación 1 de `User Story 1`.

## 2 — Solo las brechas (User Story 2)

```bash
python3 -m inventory.cli --gaps --no-telegram --no-dashboard
```

**Esperado**: lista más corta que la del paso 1, cada línea con componente,
qué pregunta falla y contexto — sin tener que abrir ningún otro documento
para entenderla (`SC-003`). Comparar a mano contra
`BARRIDO-2026-08-01.md` y `BARRIDO-2026-08-07.md`: las brechas ya conocidas
por esos barridos deben aparecer marcadas como conocidas, no como
hallazgo nuevo (`User Story 2`, escenario 2).

## 3 — Comprobar el criterio de la línea base (`SC-002`)

Contar las líneas del paso 2. **Esperado**: igual o más de 11 — el número
de problemas reales que encontró el barrido manual del 2026-08-01
(Principio IX).

## 4 — Repetir sin cambios (User Story 3, escenario 3)

```bash
python3 -m inventory.cli --no-telegram --no-dashboard
```

**Esperado**: una segunda ejecución completa, aunque nada haya cambiado en
el homelab desde la primera — no debe negarse a correr ni limitarse a un
diff vacío. Confirmar con `--since <run_id_del_paso_1>` que el diff sale
vacío (cero brechas nuevas, cero componentes nuevos).

## 5 — Añadir un componente y repetir (User Story 3, escenarios 1-2)

Parar y arrancar de nuevo un contenedor no crítico cualquiera con un nombre
temporal distinto, o (más simple) usar un contenedor de prueba desechable.

```bash
docker run -d --name inventario-prueba-temporal alpine sleep 300
python3 -m inventory.cli --since <run_id_del_paso_4>
docker rm -f inventario-prueba-temporal
```

**Esperado**: el diff muestra el contenedor nuevo con sus tres respuestas
(probablemente "brecha: sin declaración, sin vigilancia" — es intencionado,
es un contenedor de prueba). Confirma `FR-013` (repetible ante cambios) sin
haber tocado ninguna lista a mano.

## 6 — Comprobar la vía de respaldo del riesgo de Telegram (Edge Case, `FR-006`)

> Nota descubierta durante `/speckit-implement`: `--no-telegram` es un
> *skip* deliberado (higiene de pruebas, `contracts/cli.md`), no un fallo
> — con esa flag el latido sigue saliendo `ok`, correctamente, porque no
> se intentó nada que pudiera fallar. Para probar la vía de respaldo de
> verdad hay que forzar un fallo real de entrega, no saltársela.

```bash
TELEGRAM_BOT_TOKEN="" TELEGRAM_CHAT_ID="" python3 -m inventory.cli --no-dashboard
python3 /Volumes/FastData/homelab/scripts/heartbeat.py --report | grep inventario-cobertura
```

**Esperado**: con credenciales vacías, el envío a Telegram falla de
verdad (sin llegar a tocar la red) y el latido se marca `fail` — no `ok`
(según el contrato de `cli.md`: el latido solo es `ok` si persistencia y
entrega tuvieron éxito) — así, si Telegram fallara de verdad en
producción, `amsterdam9.health` lo detectaría por esta vía independiente.
Verificado en la implementación real (2026-08-08): `{"status": "fail",
"detail": "entrega falló"}`.

## 7 — Autocomprobación de lógica pura

```bash
python3 -m inventory.cli --selftest
```

**Esperado**: mismo patrón que `test_docker_monitor.py` — comprueba reglas
puras (caducidad a 90 días, emparejamiento por identificador estable,
clasificación de brechas) contra una base de datos temporal, sin tocar
Docker, HA ni Telegram reales.
