# Data Model — Remediación Automática, Primera Pieza (Rotación de Logs)

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Modelo nuevo, sin relación de esquema con `specs/007-.../data-model.md`
(paquete independiente, research.md §2).

## `configuracion_accion`

| Campo | Tipo | Notas |
|---|---|---|
| `tipo_accion` | TEXT PK | `"rotar_log"` en v1 — único valor real hoy, pero el campo es TEXT libre para futuros tipos. |
| `modo` | TEXT | `"manual"` (por defecto) o `"automatico"` — nunca otro valor (FR-001). |
| `actualizado_en` | TEXT (ISO 8601) | Momento del último cambio de modo. |

Fila creada automáticamente en `manual` la primera vez que se
menciona un `tipo_accion` (por ejemplo, al ejecutar `comprobar` por
primera vez) — nunca hace falta un paso de "alta" manual previo.

## `intentos_remediacion`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Autoincremental. |
| `tipo_accion` | TEXT | `"rotar_log"`. |
| `componente` | TEXT | Nombre corto del log (`"health-docker"`, `"health-ha"`) — de `LOGS_VIGILADOS` (research.md §3). |
| `ruta` | TEXT | Ruta absoluta real del fichero en el momento de la detección. |
| `modo_en_deteccion` | TEXT | `"manual"` o `"automatico"` — el modo vigente cuando se creó este intento, para que el historial (FR-004) sea fiel aunque el modo cambie después. |
| `estado` | TEXT | `"pendiente"` / `"rechazado"` / `"ejecutado"` / `"fallido"` / `"deshecho"` — sin estado intermedio "aprobado": `aprobar` ejecuta la rotación en la misma llamada (User Story 2). |
| `detalle` | TEXT | Texto legible: tamaño real, umbral, y (tras ejecutar) el nombre del fichero rotado o el motivo del fallo. |
| `fichero_rotado` | TEXT, NULL | Ruta del fichero tras rotar (`foo.log.rotado-<ISO>`) — solo con `estado="ejecutado"` o `"deshecho"`. |
| `creado_en` | TEXT (ISO 8601) | Momento de detección. |
| `resuelto_en` | TEXT (ISO 8601), NULL | Momento de aprobar/rechazar/ejecutar/deshacer. |

### Transiciones de estado válidas

```
pendiente → ejecutado → deshecho      (aprobar tiene éxito; deshacer después)
pendiente → fallido                    (aprobar, pero el fichero ya no existe u otro fallo)
pendiente → rechazado                  (rechazar — estado final)
(automático) → ejecutado directamente, sin pasar por pendiente
(automático) → fallido directamente, sin pasar por pendiente
```

En modo automático, la detección crea el intento directamente en
`estado="ejecutado"` (si la rotación tuvo éxito) o `"fallido"` (si no)
— nunca pasa por `"pendiente"` (FR-007). En modo manual, la detección
crea `"pendiente"`; `aprobar` ejecuta la rotación en la misma llamada
y lo mueve a `"ejecutado"` o `"fallido"` según el resultado real —sin
ningún estado intermedio "aprobado" que persista—; `rechazar` lo mueve
a `"rechazado"`, estado final sin ejecutar nada. Solo `"ejecutado"`
admite `deshacer` (FR-010) — pasa a `"deshecho"`, también final.

## Constantes (`acciones.py`)

| Constante | Valor | Uso |
|---|---|---|
| `REMEDIACION_LOGS_DIR` | `~/Library/Logs`, configurable por variable de entorno | Directorio donde viven los logs vigilados — configurable para poder probar por CLI sin tocar los reales (research.md §3). |
| `UMBRAL_ROTACION_BYTES_DEFAULT` | `10 * 1024 * 1024` (10 MB), configurable por `REMEDIACION_UMBRAL_ROTACION_BYTES` | Umbral de la condición determinista (research.md §3). |
| `LOGS_VIGILADOS` | Lista cerrada de 17 `(nombre, nombre_fichero, umbral_bytes)` (ampliada 2026-08-13, research.md §7) | Universo cerrado de nombres de fichero — uno fuera de esta lista nunca se evalúa (FR-005); la ruta real se arma con `REMEDIACION_LOGS_DIR`. |

## Funciones (`acciones.py`)

| Función | Uso |
|---|---|
| `comprobar_rotar_log(conn)` | Recorre `LOGS_VIGILADOS`; para cada uno por encima de su umbral y sin ya una `pendiente` (FR-008), crea un intento — en `pendiente` si el modo es manual, ejecutando directo si es automático. |
| `ejecutar_rotar_log(intento)` | Renombra el fichero real (research.md §4) — nunca trunca ni borra. |
| `deshacer_rotar_log(intento)` | Procedimiento de dos pasos de research.md §4 — nunca sobreescribe lo escrito después de la rotación. |

## Esquema SQLite (`remediacion.db`)

```sql
CREATE TABLE configuracion_accion (
    tipo_accion TEXT PRIMARY KEY,
    modo TEXT NOT NULL DEFAULT 'manual',
    actualizado_en TEXT NOT NULL
);

CREATE TABLE intentos_remediacion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_accion TEXT NOT NULL,
    componente TEXT NOT NULL,
    ruta TEXT NOT NULL,
    modo_en_deteccion TEXT NOT NULL,
    estado TEXT NOT NULL,
    detalle TEXT NOT NULL,
    fichero_rotado TEXT,
    creado_en TEXT NOT NULL,
    resuelto_en TEXT
);
```
