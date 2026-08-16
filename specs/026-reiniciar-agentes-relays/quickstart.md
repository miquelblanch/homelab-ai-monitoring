# Quickstart — Reinicio de Agentes y Relays

**Feature**: [spec.md](./spec.md) · **Contratos**: [contracts/cli.md](./contracts/cli.md), [contracts/snapshot-json.md](./contracts/snapshot-json.md) ·
**Modelo de datos**: [data-model.md](./data-model.md)

Cómo Miquel se convence de que esto funciona de extremo a extremo,
**sin tocar ningún LaunchAgent/LaunchDaemon real del homelab** en
ningún escenario de este documento salvo el 6 (kickstart real, sobre
un LaunchAgent de usuario desechable, nunca uno de los 43 reales) y el
8 (solo lectura). Mismo principio que 021: reiniciar algo real es una
decisión operativa aparte, posterior a que todo esto pase.

## Prerrequisitos

```bash
export LAUNCHAGENTS_RAW=/tmp/quickstart-launchagents-raw.txt
printf 'pid\texit\tlabel\n-\t1\tamsterdam9.remediacion-quickstart-test\n' > "$LAUNCHAGENTS_RAW"
```

Todos los escenarios 1-5 usan la llamada real a DeepSeek **mockeada**
(`REMEDIACION_DEEPSEEK_MOCK`) — nunca gastan presupuesto real. El
Escenario 6 es el único que ejecuta un `launchctl kickstart` real (con
un LaunchAgent de usuario desechable, cargado a propósito para esta
prueba). El Escenario 7 es la única llamada real a la API de DeepSeek.

## Escenario 1 — DeepSeek recomienda reiniciar, modo manual propone (User Story 1)

```bash
PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_agente", "razonamiento": "prueba: sin proceso activo"}' \
  python3 -m remediacion.cli comprobar-agentes
python3 -m remediacion.cli pendientes
```

**Resultado esperado**: un intento `pendiente` para
`amsterdam9.remediacion-quickstart-test`, con la recomendación y el
razonamiento simulados. Nada se ejecuta todavía.

## Escenario 2 — DeepSeek concluye que ninguna acción aplica (FR-002 reforzado)

```bash
PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": null, "razonamiento": "prueba: el problema no es del proceso en sí"}' \
  python3 -m remediacion.cli comprobar-agentes
```

**Resultado esperado**: intento `sin_accion`, aviso por Telegram con
el razonamiento (si hay credenciales configuradas) — nunca un
reinicio "porque sí" solo por estar caído.

## Escenario 3 — Modo automático: ejecuta directo, con el kickstart forzado a fallar

```bash
python3 -m remediacion.cli modo reiniciar_agente --automatico

PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_agente", "razonamiento": "prueba"}' \
  REMEDIACION_TEST_FORZAR_FALLO_AGENTE=1 \
  python3 -m remediacion.cli comprobar-agentes
```

**Resultado esperado**: intento `fallido` directamente (sin pasar por
`pendiente`), detalle indicando que el reinicio no tuvo efecto —
`launchctl` nunca se invoca de verdad (hook de pruebas, research.md §2).

## Escenario 4 — Cortacircuito, compartido con contenedores (Clarifications, sesión 2026-08-16)

```bash
for i in 1 2 3; do
  PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_agente", "razonamiento": "prueba"}' \
    REMEDIACION_TEST_FORZAR_FALLO_AGENTE=1 \
    python3 -m remediacion.cli comprobar-agentes
done
```

**Resultado esperado**: los primeros 3 intentos son `fallido`; el
4º queda en `cortacircuito` (mismo umbral 3/6h que contenedores,
contado solo sobre `intentos_agente` — garantía 26 de contracts/cli.md).
Aviso por Telegram en el momento de abrir el cortacircuito.

## Escenario 5 — `com.homeassistant.*` sin `sudoers` instalado (FR-005/FR-023)

```bash
printf 'pid\texit\tlabel\n-\t1\tcom.homeassistant.quickstart-test-relay\n' >> "$LAUNCHAGENTS_RAW"

PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_agente", "razonamiento": "prueba"}' \
  python3 -m remediacion.cli comprobar-agentes
python3 -m remediacion.cli agentes
```

**Resultado esperado**: el intento sobre
`com.homeassistant.quickstart-test-relay` queda `fallido` con detalle
"permiso denegado" (`sudo -n` real, sin `sudoers` instalado en la
máquina de pruebas — comportamiento correcto, no un mock). El comando
`agentes` muestra `sudoers_instalado: false` para ese label.

## Escenario 6 — Aprobar en modo manual: kickstart real, sobre un LaunchAgent desechable

```bash
cat > ~/Library/LaunchAgents/amsterdam9.remediacion-quickstart-test.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>amsterdam9.remediacion-quickstart-test</string>
  <key>ProgramArguments</key><array><string>/bin/sleep</string><string>3600</string></array>
  <key>RunAtLoad</key><true/>
</dict></plist>
EOF
launchctl load ~/Library/LaunchAgents/amsterdam9.remediacion-quickstart-test.plist
sleep 1
# RunAtLoad lo arranca solo al cargar — hay que matarlo para simular
# que está caído, si no comprobar-agentes no encuentra nada que evaluar
# (corrección tras validar T031, faltaba en el borrador original)
kill "$(launchctl list | grep amsterdam9.remediacion-quickstart-test | awk '{print $1}')"
sleep 1

python3 -m remediacion.cli modo reiniciar_agente --manual
PYTHONPATH=src REMEDIACION_DEEPSEEK_MOCK='{"accion_aplica": "reiniciar_agente", "razonamiento": "prueba"}' \
  python3 -m remediacion.cli comprobar-agentes
python3 -m remediacion.cli aprobar <INTENTO_ID>
launchctl list | grep amsterdam9.remediacion-quickstart-test

# limpieza
launchctl unload ~/Library/LaunchAgents/amsterdam9.remediacion-quickstart-test.plist
rm ~/Library/LaunchAgents/amsterdam9.remediacion-quickstart-test.plist
```

**Resultado esperado**: intento `ejecutado`, verificado corriendo de
verdad tras el `kickstart` (FR-006) — el único escenario de este
documento que toca `launchctl` real, y solo sobre un LaunchAgent creado
y destruido en la propia prueba.

**Hallazgo real, resuelto (T031, 2026-08-16)**: el primer intento
agotaba un timeout de 15s tanto dentro de Claude Code como en una
Terminal normal (Miquel lo confirmó con `probar-kickstart-real.sh`) —
no era cosa del entorno de sesión. Aislado después: `launchctl
kickstart` tarda ~18s en devolver el control en esta máquina de verdad
(medido dos veces, 18.0s exactos), no se cuelga. La propiedad de
seguridad se sostuvo durante la investigación (el timeout corto llevó
a `fallido`, nunca a un `ejecutado` falso). Corregido a 30s
(`REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS`, research.md §2b) —
reconfirmado con un `ejecutado — reiniciado y verificado` real sobre
el LaunchAgent desechable, ~21s totales.

## Escenario 7 — Snapshot ampliado (User Stories 3, 4, 5)

```bash
python3 -m remediacion.cli comprobar-agentes
cat /Volumes/FastData/homelab/docker/homelab-orchestrator/data/remediacion_estado.json | python3 -m json.tool
```

**Resultado esperado**: el JSON incluye el bloque `agentes[]`
(contracts/snapshot-json.md) junto a `logs[]`/`contenedores[]` sin
cambios — `beszel` sigue presente en `contenedores[]` con su
clasificación (User Story 3, sin cambio de código). Verificación
manual de que un dashboard privado podría pintar "Remediaciones" y
ampliar "Correcciones" con estos tres bloques, sin montar
`remediacion.db` directamente.

## Escenario 8 — Llamada real a DeepSeek (única, opcional)

```bash
unset REMEDIACION_DEEPSEEK_MOCK REMEDIACION_TEST_FORZAR_FALLO_AGENTE
python3 -m remediacion.cli comprobar-agentes
```

**Resultado esperado**: gasta presupuesto real (visible en
`diagnostico.gasto`) — correr solo si hace falta validar la
integración real con la API, no como parte del flujo habitual de
pruebas.
