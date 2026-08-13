# Data Model — Remediación Asistida por DeepSeek: Contenedores

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Extiende `remediacion.db` (ya existente desde 019) con dos tablas
nuevas — sin tocar `configuracion_accion`/`intentos_remediacion`, que
siguen siendo exclusivas de `rotar_log` (research.md §6).

## `configuracion_contenedor`

| Campo | Tipo | Notas |
|---|---|---|
| `contenedor` | TEXT PK | Nombre real del contenedor Docker. |
| `modo` | TEXT | `"manual"` o `"automatico"` — nunca otro valor. |
| `actualizado_en` | TEXT (ISO 8601) | Momento del último cambio de modo. |

A diferencia de `configuracion_accion` (019), la clave es el
componente individual, no un tipo de acción entero (research.md §6).
Los 26 contenedores no críticos se insertan en `automatico` como parte
del despliegue de esta feature (research.md §7) — no como
comportamiento por defecto del código.

## `intentos_reinicio`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Autoincremental. |
| `contenedor` | TEXT | Nombre del contenedor. |
| `modo_en_deteccion` | TEXT | `"manual"` o `"automatico"` vigente al crear el intento — igual que `modo_en_deteccion` de 019. |
| `episodio_id` | INTEGER, NULL | FK lógica al `Episodio` de `diagnostico.db` creado por `congelar_vivo()` (research.md §1) — NULL si nunca se llegó a reunir evidencia (p. ej. sin presupuesto). |
| `accion_recomendada` | TEXT, NULL | `"reiniciar_contenedor"` o `NULL` si DeepSeek concluyó que ninguna acción aplica. |
| `razonamiento_deepseek` | TEXT, NULL | Texto libre devuelto por DeepSeek — NULL si `estado = "sin_evaluar"`. |
| `coste_eur` | REAL, NULL | Coste real de la llamada a DeepSeek que originó este intento — NULL si `estado = "sin_evaluar"` por falta de presupuesto (nunca se llegó a llamar). |
| `estado` | TEXT | `"pendiente"` / `"rechazado"` / `"ejecutado"` / `"fallido"` / `"cortacircuito"` / `"sin_accion"` / `"sin_evaluar"` — ver transiciones abajo. Sin `"deshecho"` (FR-016: sin rollback para esta acción). |
| `detalle` | TEXT | Texto legible — motivo del fallo, o de "cortacircuito", o de "sin_evaluar". |
| `creado_en` | TEXT (ISO 8601) | Momento de la evaluación. |
| `resuelto_en` | TEXT (ISO 8601), NULL | Momento de aprobar/rechazar/ejecutar. |

### Transiciones de estado válidas

```
(DeepSeek recomienda reiniciar, modo manual)     → pendiente → ejecutado   (aprobar, éxito)
(DeepSeek recomienda reiniciar, modo manual)     → pendiente → fallido     (aprobar, falla la verificación)
(DeepSeek recomienda reiniciar, modo manual)     → pendiente → rechazado   (Miquel rechaza — final)
(DeepSeek recomienda reiniciar, modo automático) → ejecutado directamente  (sin pasar por pendiente)
(DeepSeek recomienda reiniciar, modo automático) → fallido directamente
(DeepSeek recomienda reiniciar, cortacircuito abierto) → cortacircuito     (nunca se ejecuta el reinicio)
(DeepSeek concluye que ninguna acción aplica)    → sin_accion              (final — US4, avisa por Telegram)
(fallo/timeout de la llamada a DeepSeek, o sin presupuesto) → sin_evaluar  (final — no es una conclusión de DeepSeek)
```

Sin ningún estado `"deshecho"` — FR-016 no promete una operación de
deshacer para esta acción; `"ejecutado"` y `"fallido"` son finales
igual que en 019, pero sin la vía de reversión que sí tiene
`rotar_log`.

## Nuevas constantes y funciones

| Elemento | Módulo | Uso |
|---|---|---|
| `TIPO_ACCION_REINICIAR_CONTENEDOR = "reiniciar_contenedor"` | `acciones.py` | Se añade a `TIPOS_ACCION` (research.md §6 de 019 — el registro ya existente, ahora con dos valores). |
| `construir_prompt_remediacion(episodio, acciones_candidatas)` | `deepseek_contenedores.py` | Prompt específico "¿qué acción de esta lista aplica?" (research.md §3) — no reutiliza `construir_prompt` de `diagnostico`. |
| `parsear_respuesta_remediacion(respuesta)` | `deepseek_contenedores.py` | Valida que `accion_aplica` sea `null` o un valor de `TIPOS_ACCION` conocido — nunca confía en texto libre del modelo (research.md §3). |
| `evaluar_contenedor(conn_remediacion, conn_diagnostico, contenedor)` | `acciones.py` | Orquesta: `congelar_vivo` → `hay_presupuesto` → `llamar_deepseek` (con el prompt nuevo) → `parsear_respuesta_remediacion` → crea el `intento_reinicio` en el estado que corresponda. |
| `comprobar_reiniciar_contenedor(conn_remediacion, conn_diagnostico)` | `acciones.py` | Recorre los contenedores no `running and healthy` que no sean críticos ni `NEVER_RESTART` (vía `_homelab_bridge.docker_critical()`/`docker_never_restart()`), sin ya un intento `pendiente`/`sin_evaluar` reciente, y llama a `evaluar_contenedor` para cada uno. |

## Funciones ampliadas en `_homelab_bridge.py`

| Función | Uso |
|---|---|
| `docker_critical() -> set[str]` | Ya existe en `inventory._homelab_bridge` — se replica aquí (research.md §2 de 019: paquetes independientes, sin importar entre `inventory` y `remediacion`). |
| `docker_never_restart() -> set[str]` | Igual que arriba. |
| `restart_container(name, reason) -> bool` | Bridge nuevo hacia `docker_monitor.restart_container()` — reutiliza la verificación real post-reinicio ya corregida (research.md §4). |
| `breaker_decision(attempts, max_attempts=3) -> tuple[bool, str]` | Bridge nuevo hacia `docker_monitor.breaker_decision()` — función pura, sin efectos secundarios que mockear de forma distinta a como ya se mockea en los tests de `docker_monitor.py`. |
| `recent_restart_attempts(contenedor, window_hours=6) -> int` | Nueva — cuenta los intentos de `remediacion.db` (no `restart_history`, research.md §5) en la ventana, para alimentar `breaker_decision()`. |

## Esquema SQLite (`remediacion.db`, tablas nuevas)

```sql
CREATE TABLE configuracion_contenedor (
    contenedor TEXT PRIMARY KEY,
    modo TEXT NOT NULL DEFAULT 'manual',
    actualizado_en TEXT NOT NULL
);

CREATE TABLE intentos_reinicio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contenedor TEXT NOT NULL,
    modo_en_deteccion TEXT NOT NULL,
    episodio_id INTEGER,
    accion_recomendada TEXT,
    razonamiento_deepseek TEXT,
    coste_eur REAL,
    estado TEXT NOT NULL,
    detalle TEXT NOT NULL,
    creado_en TEXT NOT NULL,
    resuelto_en TEXT
);
CREATE INDEX idx_intentos_reinicio_contenedor_estado
    ON intentos_reinicio(contenedor, estado);
```
