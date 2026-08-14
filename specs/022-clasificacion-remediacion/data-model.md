# Data Model — Clasificación de Remediación en Inventario

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Sin tablas nuevas en `remediacion.db` — reutiliza íntegramente el
esquema de 019/021 (`configuracion_accion`, `configuracion_contenedor`,
`intentos_remediacion`, `intentos_reinicio`). Este documento describe
únicamente lo que cambia: dos funciones puras nuevas y una guarda de
escritura.

## Entidades derivadas (sin persistencia propia)

### `Clasificación de remediación`

Valor calculado, nunca guardado — spec.md, Key Entities.

| Entrada | Cálculo | Salida |
|---|---|---|
| Contenedor en `docker_critical()` o `docker_never_restart()` | — (modo se ignora) | `"manual"` |
| Contenedor no crítico | — (modo se ignora, FR-004) | `"ia"` |
| Log de `LOGS_VIGILADOS`, `configuracion_accion.modo == "automatico"` | — | `"automatica"` |
| Log de `LOGS_VIGILADOS`, `configuracion_accion.modo == "manual"` | — | `"manual"` |
| Cualquier otro componente del inventario | — | `"manual"` (aplicado por el dashboard, no por este paquete — research.md §4) |

### `Propuesta de remediación para contenedor crítico`

No es una entidad con tabla propia — es una `IntentoReinicio` (021)
como cualquier otra, con dos invariantes nuevos que este feature
añade y que valen solo cuando `contenedor` es crítico:

- `modo_en_deteccion` DEBE ser siempre `"manual"` — nunca se persiste
  `"automatico"` para un intento de un contenedor crítico (invariante
  de escritura, verificado en `evaluar_contenedor`, research.md §1).
- `estado` nunca llega a `"cortacircuito"` para un crítico — ese
  estado depende del contador de reinicios automáticos
  (`recent_restart_attempts`/`breaker_decision`), que solo se consulta
  en la rama `modo == "automatico"` de `evaluar_contenedor`; un
  crítico nunca entra en esa rama.

## Cambios de esquema

**Ninguno.** `ESTADOS_INTENTO_REINICIO` (model.py) y las tablas de
`store.py` no ganan ningún valor ni columna nueva — un intento sobre
un contenedor crítico es, en base de datos, indistinguible en forma de
uno sobre un no crítico; la única diferencia es *qué valores puede
tomar* (`modo_en_deteccion` siempre `"manual"`, `estado` nunca
`"cortacircuito"`), reforzada en código (research.md §1/§2), no en el
esquema.

## Funciones nuevas

### `clasificacion.py` (módulo nuevo, sin I/O — research.md §4)

```python
def clasificar_contenedor(
    nombre: str,
    criticos: set[str],
    never_restart: set[str],
    modo: str | None,
) -> str:
    """"manual" | "ia" — ver tabla de arriba. `modo` se acepta por
    firma pero no se usa (FR-004: la clasificación no depende del modo
    de ejecución) — se mantiene como parámetro explícito y no se
    elimina para que la firma documente, sin comentario aparte, que
    esta función lo consideró y lo descartó a propósito."""

def clasificar_log(modo: str) -> str:
    """"automatica" | "manual" — ver tabla de arriba."""
```

### `acciones.py` (extensión)

| Función | Cambio |
|---|---|
| `evaluar_contenedor(conn_remediacion, conn_diagnostico, contenedor, modo_forzado=None)` | Nuevo parámetro opcional `modo_forzado`. Si se pasa, se usa en vez de `get_modo_contenedor()` — nunca se consulta la tabla para ese contenedor. Sin cambios de comportamiento cuando `modo_forzado` es `None` (no críticos, sin cambios respecto a 021). |
| `comprobar_reiniciar_contenedor(conn_remediacion, conn_diagnostico)` | Ya no excluye `criticos` de la lista a recorrer — solo excluye `never_restart`. Para un contenedor de `criticos`, llama a `evaluar_contenedor(..., modo_forzado="manual")`. |
| `escribir_snapshot(conn)` | + construye y añade la clave `contenedores` (research.md §3), usando `clasificacion.clasificar_contenedor()` y el intento vigente de cada uno (`store.intento_reinicio_vigente(conn, nombre)`, función de lectura nueva, solo `SELECT`, sin efectos). |

### `store.py` (extensión)

| Función | Cambio |
|---|---|
| `set_modo_contenedor(conn, contenedor, modo)` | + guarda al inicio: si `modo == "automatico"` y `contenedor in bridge.docker_critical()`, `raise ValueError(f"{contenedor} es crítico — no admite modo automático")` sin escribir nada (research.md §2). |
| `intento_reinicio_vigente(conn, contenedor) -> IntentoReinicio \| None` | Nueva, solo lectura: el intento más reciente en estado `pendiente`/`sin_evaluar`/`sin_accion`, o el `ejecutado`/`fallido`/`rechazado` más reciente si su `resuelto_en` está dentro de `REMEDIACION_INTENTO_VIGENTE_MINUTOS` (constante nueva, default `5`, mismo patrón que `REMEDIACION_CB_VENTANA_HORAS`/`REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS` — nombrada y configurable por variable de entorno, no un literal suelto, corregido tras `/speckit-analyze` hallazgo C1) — si no hay ninguno, `None`. Usada por `escribir_snapshot` (arriba) y reutilizable después por cualquier otro consumidor que necesite "el estado de ahora mismo" de un contenedor. La constante nombrada, además, es lo que permite a `test_remediacion_store.py` probar la rama "ya no vigente" fabricando un `resuelto_en` fuera de ventana, sin dormir minutos reales. |

## Validación derivada de los requisitos

- FR-002 → ninguna de las funciones nuevas persiste una clasificación;
  todas la recalculan a partir de `configuracion_*`/`docker_critical()`
  en cada llamada.
- FR-004/FR-005/FR-006/FR-007 → cubiertos íntegramente por la tabla de
  "Clasificación de remediación" de arriba, sin rama adicional no
  contemplada.
- FR-008 → `set_modo_contenedor` (guarda de escritura) +
  `evaluar_contenedor` con `modo_forzado="manual"` para críticos
  (guarda de evaluación) — dos puntos de aplicación independientes,
  ninguno delega en el otro.
- FR-010 → un intento sobre un crítico solo puede llegar a
  `"pendiente"` (esperando aprobación) o `"sin_accion"`/`"sin_evaluar"`
  (sin ejecución posible); nunca `"ejecutado"`/`"fallido"` salvo a
  través de `resolver_aprobacion_reinicio`, que exige una llamada
  explícita del CLI (Miquel) — nunca la crea `comprobar_reiniciar_contenedor`
  por sí sola.
- FR-011 → `intento_reinicio_vigente` es la función que alimenta el
  campo `intento_vigente` del snapshot que el dashboard privado
  consume para pintar el estado real en Alarmas.
