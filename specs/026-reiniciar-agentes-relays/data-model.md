# Data Model — Reinicio de Agentes y Relays

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md)

Extiende `remediacion.db` (ya existente desde 019) con **una tabla
nueva**, `intentos_agente` — sin tocar `configuracion_accion`
(019, reutilizada tal cual, research.md §6 de 021) ni
`configuracion_contenedor`/`intentos_reinicio` (021, sin cambios).

## `intentos_agente`

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Mismo espacio de `id` compartido con `intentos_remediacion`/`intentos_reinicio` (research.md §1) — **no** autoincremental independiente. |
| `label` | TEXT | Label real de `launchd` (`amsterdam9.*` o `com.homeassistant.*`). |
| `modo_en_deteccion` | TEXT | `"manual"` o `"automatico"` vigente de `reiniciar_agente` (`configuracion_accion`) al crear el intento. |
| `episodio_id` | INTEGER, NULL | FK lógica al `Episodio` de `diagnostico.db` (`origen="agente"`, `congelar_agente_vivo()`) — NULL si nunca se llegó a reunir evidencia. |
| `accion_recomendada` | TEXT, NULL | `"reiniciar_agente"` o `NULL` si DeepSeek concluyó que ninguna acción aplica. |
| `razonamiento_deepseek` | TEXT, NULL | Texto libre de DeepSeek — NULL si `estado = "sin_evaluar"`. |
| `coste_eur` | REAL, NULL | Coste real de la llamada que originó este intento — NULL si `sin_evaluar` por falta de presupuesto. |
| `estado` | TEXT | `"pendiente"` / `"rechazado"` / `"ejecutado"` / `"fallido"` / `"cortacircuito"` / `"sin_accion"` / `"sin_evaluar"` — mismo conjunto que `intentos_reinicio` (`ESTADOS_INTENTO_REINICIO`, reutilizado tal cual). Sin `"deshecho"` (FR-007: sin rollback). |
| `detalle` | TEXT | Texto legible — motivo del fallo, cortacircuito, o sin_evaluar. |
| `creado_en` | TEXT (ISO 8601) | Momento de la evaluación. |
| `resuelto_en` | TEXT (ISO 8601), NULL | Momento de aprobar/rechazar/ejecutar. |

Índice `idx_intentos_agente_label_estado` sobre `(label, estado)` —
mismo patrón que `idx_intentos_reinicio_contenedor_estado`.

### Transiciones de estado válidas

```
(DeepSeek recomienda reiniciar, modo manual)     → pendiente → ejecutado   (aprobar, verificado corriendo)
(DeepSeek recomienda reiniciar, modo manual)     → pendiente → fallido     (aprobar, sigue sin proceso activo)
(DeepSeek recomienda reiniciar, modo manual)     → pendiente → rechazado   (Miquel rechaza — final)
(DeepSeek recomienda reiniciar, modo automático) → ejecutado directamente  (sin pasar por pendiente)
(DeepSeek recomienda reiniciar, modo automático) → fallido directamente
(DeepSeek recomienda reiniciar, cortacircuito abierto) → cortacircuito     (nunca se ejecuta)
(com.homeassistant.* sin sudoers instalado, modo automático) → fallido    (sudo -n falla, detalle = "permiso denegado")
(DeepSeek concluye que ninguna acción aplica)    → sin_accion              (final — avisa por Telegram)
(fallo/timeout de DeepSeek, o sin presupuesto)   → sin_evaluar             (final — no es conclusión de DeepSeek)
```

Idéntico a `intentos_reinicio` salvo una transición nueva: un
`com.homeassistant.*` en modo automático sin `sudoers` instalado
**sí llega a intentar el reinicio** (a diferencia de la comprobación
de `sudoers_permitido()` que alimenta el snapshot, research.md §3) —
`sudo -n` falla en el momento y el intento queda `fallido` con el
motivo real, nunca `sin_evaluar` (el fallo es de ejecución, no de
evaluación — DeepSeek sí pudo decidir).

## Reutilizado sin cambios

| Elemento | Origen | Uso en esta feature |
|---|---|---|
| `configuracion_accion` | 019 | `reiniciar_agente` es un tipo de acción más — `get_modo`/`set_modo` sin ningún cambio de código. |
| `REMEDIACION_CB_MAX_INTENTOS` / `REMEDIACION_CB_VENTANA_HORAS` | 021 | Cortacircuito compartido (Clarifications, sesión 2026-08-16) — contado sobre `intentos_agente`, mismas constantes. |
| `REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS` | 021 (FR-019) | Aviso por fallo persistente al decidir — mismo umbral. |
| `diagnostico.evidencia.agente.congelar_agente_vivo()` | 016 | Única fuente de evidencia — sin modo diferido (FR-003). |
| `_extraer_contenido_y_tokens` | `diagnostico.deepseek`, consolidado en 025 | Parseo de la respuesta de DeepSeek, reutilizado por `deepseek_agentes.py`. |
| `_notificar_sin_accion(contenedor, razonamiento)` / `_notificar_cortacircuito(contenedor, detalle)` / `_notificar_sin_evaluar_persistente(contenedor, racha)` | 021 (`acciones.py`) | Los tres avisos de Telegram (FR-002/FR-009/FR-014) se reutilizan tal cual — se llaman con `label` como argumento posicional (el nombre del parámetro sigue siendo `contenedor` en el código actual; es solo el texto del mensaje, no importa para la llamada). Sin variante `_agente` de ninguno de los tres: **conexión explícita añadida tras `/speckit-analyze` (hallazgo E1)** — antes solo se citaba `_notificar_sin_accion` en la documentación, con riesgo real de que cortacircuito/sin_evaluar-persistente quedaran sin aviso. |

## Nuevas constantes y funciones

| Elemento | Módulo | Uso |
|---|---|---|
| `TIPO_ACCION_REINICIAR_AGENTE = "reiniciar_agente"` | `acciones.py` | Tercer valor de `TIPOS_ACCION`. |
| `ejecutar_reiniciar_agente(label, requiere_sudo)` | `acciones.py` | `launchctl kickstart`, directo (research.md §2) — sin bridge. Timeout `REMEDIACION_AGENTE_TIMEOUT_KICKSTART_SEGUNDOS = 30` (no 15 — corregido tras medir ~18s reales en producción, T031). |
| `evaluar_agente(conn_remediacion, conn_diagnostico, label)` | `acciones.py` | Mismo esqueleto que `evaluar_contenedor()`, sin `modo_forzado` (no hay eje crítico para agentes). |
| `_crear_intento_agente(conn, label, modo, episodio_id, estado, detalle, ...)` | `acciones.py` | **Añadida tras `/speckit-analyze` (hallazgo E1, 2026-08-16)** — punto único de escritura de `intentos_agente`, mismo rol que `_crear_intento_reinicio()` (021): comprueba `store.sin_evaluar_consecutivos_agente()` en cada creación y dispara `_notificar_sin_evaluar_persistente(label, racha)` si supera `REMEDIACION_SIN_EVALUAR_MAX_CONSECUTIVOS` (FR-014) — sin este punto único, la contrapartida no negociable del Principio VII enmendado podía quedar sin implementar si cada rama de `evaluar_agente()` la comprobaba (o no) por su cuenta. |
| `comprobar_reiniciar_agente(conn_remediacion, conn_diagnostico)` | `acciones.py` | Recorre `bridge.listar_agentes_conocidos()`, evalúa los sin proceso activo. |
| `clasificar_agente(label, modo)` | `clasificacion.py` | Función pura — mismo criterio que `clasificar_log()`. |
| `sudoers_permitido(label)` | `_homelab_bridge.py` | `sudo -n -l`, solo lectura (research.md §3). |
| `listar_agentes_conocidos()` | `_homelab_bridge.py` | Lee `LAUNCHAGENTS_RAW`, filtra por prefijo (research.md §4). |
| `recent_agent_restart_attempts(conn, label, window_hours)` | `_homelab_bridge.py` | Mismo cálculo que `recent_restart_attempts()`, sobre `intentos_agente`. |
| `IntentoAgente` | `model.py` | Dataclass — mismos campos que `IntentoReinicio`, `label` en vez de `contenedor`. |
| `insert_intento_agente` / `get_intento_agente` / `update_intento_agente_estado` / `listar_pendientes_agente` / `intento_agente_vigente` / `intentos_recientes_agente` / `sin_evaluar_consecutivos_agente` / `intento_reciente_pendiente_o_sin_evaluar_agente` | `store.py` | Simétricas a sus equivalentes de `intentos_reinicio`. |
| `intento_vigente(conn, tipo_accion, componente)` | `store.py` | **Añadida verificando T028** — mismo criterio que `intento_reinicio_vigente`/`intento_agente_vigente`, pero para `intentos_remediacion` (`rotar_log`). No existía antes de esta feature; sin ella, `logs[]` del snapshot no podía exponer `intento_vigente` y FR-020 quedaba incumplido para logs. |
