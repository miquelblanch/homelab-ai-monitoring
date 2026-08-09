# Quickstart — Validar la Central de Alarmas

**Feature**: [spec.md](./spec.md) · **Contrato**: [contracts/api-alarms.md](./contracts/api-alarms.md)

Cómo Miquel se convence de que este feature funciona de extremo a
extremo — no es el plan de implementación (`tasks.md`).

## Prerrequisitos

- Dashboard (`homelab-dashboard`) reconstruido con los cambios de este
  feature (`docker compose up -d --build dashboard`, mismo
  procedimiento que cualquier cambio en `app.py`).
- Los 10 orígenes en su estado normal (0 brechas, todo `ok`) para poder
  ver primero el caso vacío, y provocar al menos un fallo real para ver
  el caso con alarmas.

## 1 — Ver de un vistazo (User Story 1)

```bash
curl -s http://homelab.amsterdam9.home/api/data | python3 -m json.tool | grep -A5 '"alarms"'
```

**Esperado, con el homelab sano**: `"total": 0, "items": []`. Abrir la
pestaña "Alarmas" del dashboard y comprobar que muestra un mensaje
explícito de que no hay alarmas activas (escenario 2, US1) — no una
tabla vacía sin texto.

**Provocar una alarma real** (reversible, de bajo riesgo — no un
contenedor crítico): `docker stop qbittorrent`. Recargar la pestaña
Alarmas y comprobar que aparece una entrada con `origen: "contenedores"`,
`tipo: "contenedor_caido"` (escenario 1, US1). `docker start qbittorrent`
para restaurar.

**Dos orígenes a la vez, entradas independientes** (escenario 3, US1):
con `qbittorrent` parado (origen `contenedores`) y, a la vez, el
fichero `ha_monitor_state.json` renombrado temporalmente (origen `ha`,
ver §6), comprobar que `alarms.items` trae **dos** entradas separadas
— una `origen: "contenedores"`, otra `origen: "ha"` con
`tipo: "origen_sin_datos"` — nunca fusionadas en una sola. Restaurar
ambas cosas al terminar.

## 2 — Entender qué significa (User Story 2)

Con la alarma del paso 1 activa, comprobar en la propia fila de la
pestaña que aparece el texto de `ALARM_TYPES["contenedor_caido"].explicacion`
tal cual — no solo `Exited (0)` en bruto (escenario 1, US2).

Para el escenario 2 (tipo sin texto documentado): añadir temporalmente
una alarma sintética con un `tipo` que no exista en `ALARM_TYPES` (o
provocar una condición de un tipo aún no cubierto) y comprobar que se
muestra igual, con el aviso fijo de "sin explicación documentada
todavía" — nunca oculta ni en blanco.

## 3 — Remediación sugerida, nada se ejecuta solo (User Story 3)

Con la misma alarma activa, comprobar que la fila trae el texto de
`remediacion` y que ningún elemento de la pestaña Alarmas lanza una
petición de escritura — inspeccionar la pestaña Network del navegador
mientras se interactúa con la fila: solo debe haber peticiones `GET` a
`/api/data`, ninguna `POST`/`PUT`/`DELETE` (escenario 3, US3).

**Contenedor crítico**: parar un contenedor no crítico no basta para
probar FR-007. Verificar por inspección de código que
`ALARM_TYPES["contenedor_caido_critico"].remediacion` contiene la
advertencia de "no reiniciar sin aprobación" — no se debe parar un
contenedor crítico de verdad solo para esta prueba (regla del homelab).

## 4 — Cascada agrupada (FR-013, Clarifications)

No es seguro provocar una caída real de la API de HA solo para probar
esto. Validar por inspección de código + dato sintético: construir una
lista de más de 5 alarmas con el mismo `(origen, tipo)` contra
`get_active_alarms()` en un entorno de prueba, y comprobar que el
resultado colapsa en una sola entrada con `agrupada: true` y `cantidad`
igual al número real — nunca contra el dashboard en producción.

## 5 — Orden por gravedad (FR-004)

Con al menos dos alarmas activas de niveles distintos a la vez (por
ejemplo, un contenedor no crítico caído = Aviso, y un disco por encima
del 90% simulado = Crítico), comprobar que la de nivel Crítico aparece
primero en la lista, independientemente de cuál se activó antes.

## 6 — El resto del dashboard sigue vivo si algo falla (SC-004, contrato §6)

Renombrar temporalmente `ha_monitor_state.json`, recargar el
dashboard, y restaurar el nombre original.

**Esperado**: el resto de pestañas se cargan con normalidad; la
pestaña Alarmas muestra una entrada `origen_sin_datos` para `ha` en vez
de fallar o quedar en blanco — mismo criterio que features 002/003 ya
establecieron para otros ficheros ausentes.

## 7 — El recuento coincide con la realidad (SC-005)

```bash
curl -s http://homelab.amsterdam9.home/api/data > /tmp/dash.json
python3 -c "
import json
d = json.load(open('/tmp/dash.json'))
print('Alarmas mostradas:', sum(a.get('cantidad', 1) for a in d['alarms']['items']))
print('Contenedores caídos (no intencionados):', sum(1 for c in d['containers'] if c['state'] != 'running' and c['name'] not in ('frigate',)))
"
```

**Esperado**: el número de alarmas de `origen: "contenedores"` que
suma `alarms` coincide con lo que la pestaña Docker ya muestra como
caído — sin duplicados ni ausencias, comparando contra al menos 2 de
los 10 orígenes a mano.

## 8 — Lo intencionado no es una alarma real (FR-011)

`frigate` está parado a propósito (`NEVER_RESTART`, `CLAUDE.md`) — es
el caso real más a mano para esta comprobación, sin tener que inventar
uno.

```bash
curl -s http://homelab.amsterdam9.home/api/data | python3 -c "
import json, sys
d = json.load(sys.stdin)
print([a for a in d['alarms']['items'] if a['componente'] == 'frigate'])
"
```

**Esperado**: lista vacía — `frigate` parado no genera ninguna alarma
de tipo `contenedor_caido`, pese a que su `state` no es `running`.

## 9 — Antigüedad ausente en orígenes de lectura instantánea (FR-014)

Con un disco por encima del umbral de aviso (75%) — o, si ninguno lo
está ahora mismo, por inspección de código de `get_active_alarms()` —
comprobar que la alarma de `origen: "discos"` trae
`"antiguedad_s": null`, nunca un número inventado.

```bash
curl -s http://homelab.amsterdam9.home/api/data | python3 -c "
import json, sys
d = json.load(sys.stdin)
discos = [a for a in d['alarms']['items'] if a['origen'] == 'discos']
print(discos or 'sin discos en aviso ahora mismo — revisar por código')
"
```
