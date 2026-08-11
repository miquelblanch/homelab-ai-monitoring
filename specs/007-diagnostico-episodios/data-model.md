# Data Model — Diagnóstico de Episodios

**Feature**: [spec.md](./spec.md) · Persistencia: `diagnostico.db` (research.md §4)

## Episodio

Unidad de trabajo del agente (spec.md, Key Entities). Se crea al
**congelar** — nunca se actualiza después salvo por el propio proceso de
congelado; es la base de la reproducibilidad de FR-002.

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | Identificador estable del episodio — esto es "lo mismo" a lo que se refiere FR-002/SC-001 cuando se repite un diagnóstico. |
| `contenedor` | TEXT | Nombre del contenedor afectado. |
| `es_critico` | INTEGER (bool) | Resultado de `docker_critical()` en el momento de congelar (research.md §7). Se congela junto al resto — si la lista crítica cambiara después, el episodio ya congelado no se re-evalúa. |
| `en_vivo` | INTEGER (bool) | `1` si se congeló desde una alarma activa; `0` si viene de `restart_history`. |
| `restart_history_id` | INTEGER, NULL | Referencia informativa al `id` de `homelab.db.restart_history` cuando `en_vivo=0`. `NULL` en vivo. No es una FK real (bases distintas). |
| `ventana_inicio` / `ventana_fin` | TEXT (ISO 8601) | Rango de tiempo de la evidencia reunida. |
| `snapshot_evidencia` | TEXT (JSON) | Evidencia congelada completa: fila de `restart_history` (si aplica), muestras de `container_metrics`, muestras de `disk_metrics`, salida de `docker inspect`/`docker logs` (si en vivo). Ver "Forma del snapshot" más abajo. |
| `creado_en` | TEXT (ISO 8601) | Momento de congelado. |

**Invariante**: una vez escrito, `snapshot_evidencia` de un episodio no se
vuelve a tocar. `diagnosticar` siempre lee de aquí, nunca vuelve a
consultar `homelab.db` ni Docker en vivo (FR-002).

### Forma del snapshot (`snapshot_evidencia`, JSON)

```json
{
  "restart_history": {"id": 16, "container_name": "beszel", "timestamp": 1775075365,
                       "result": "success", "reason": "Container beszel restarted successfully",
                       "triggered_by": "healer"},
  "container_metrics": [
    {"timestamp": "...", "status": "...", "health": "...", "cpu_percent": 0.0,
     "memory_mb": 0.0, "memory_percent": 0.0}
  ],
  "container_metrics_hourly": [
    {"hour": "...", "samples": 0, "cpu_avg": 0.0, "cpu_max": 0.0,
     "memory_avg_mb": 0.0, "memory_max_mb": 0.0, "healthy_ratio": 0.0}
  ],
  "disk_metrics": [
    {"timestamp": "...", "path": "...", "label": "...", "used_percent": 0.0, "free_gb": 0.0}
  ],
  "docker_inspect": null,
  "docker_logs_tail": null
}
```

`restart_history` es `null` cuando `en_vivo=1`; `docker_inspect`/
`docker_logs_tail` son `null` cuando `en_vivo=0` (research.md §5).

## Hipótesis

Una causa probable propuesta para un episodio, con su contraste (spec.md,
Key Entities). Pertenece a un intento de diagnóstico concreto (tabla
`diagnosticos`), no directamente al episodio — así conviven varios
intentos sobre el mismo episodio sin mezclar sus hipótesis (US1,
reproducibilidad; US2, registro).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `diagnostico_id` | INTEGER FK → `diagnosticos.id` | |
| `orden` | INTEGER | Orden en que DeepSeek la propuso, para reconstruir la respuesta tal cual (Principio VIII). |
| `descripcion` | TEXT | La causa probable, en prosa. |
| `comprobacion` | TEXT | Cómo se contrastó contra la evidencia del snapshot — no solo el veredicto, el razonamiento (FR-006, US2 escenario 2: "no solo que se descartó, por qué"). |
| `desenlace` | TEXT | Uno de `confirmada` / `descartada` / `sin_evidencia_suficiente`. |

## Diagnóstico

El resultado de un intento de procesar un episodio (spec.md, Key
Entities). Un mismo `episodio_id` puede tener varios `diagnosticos` —
cada ejecución de `diagnosticar <episodio_id>` crea uno nuevo, nunca
sobrescribe uno anterior (Principio VIII: nada se pierde; comparar dos
intentos es precisamente cómo se comprueba SC-001).

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `episodio_id` | INTEGER FK → `episodios.id` | |
| `conclusion_tipo` | TEXT | `causa_probable` o `no_diagnosticable` (FR-007 — exactamente uno de los dos). |
| `conclusion_texto` | TEXT | Prosa de la causa probable, o la razón concreta de "no se puede diagnosticar" (evidencia insuficiente / límite de gasto alcanzado / fallo de DeepSeek — Edge Cases). |
| `modelo` | TEXT | Identificador de modelo DeepSeek usado (por si cambia entre intentos). |
| `tokens_entrada` / `tokens_salida` | INTEGER | Tal cual reportados por la respuesta de la API — nunca estimados (FR-009). |
| `coste_eur` | REAL | Calculado de los tokens de arriba contra `PRECIOS_EUR_POR_MILLON_TOKENS` (research.md §6). `0.0` si no llegó a llamar (límite ya alcanzado). |
| `creado_en` | TEXT (ISO 8601) | |

**Invariante (FR-007)**: si `conclusion_tipo = 'causa_probable'`, debe
existir **exactamente una** fila en `hipotesis` con
`desenlace = 'confirmada'` para ese `diagnostico_id` — ni cero ni dos o
más (corregido el 2026-08-11, hallazgo I2 de `/speckit-analyze`: antes
de esta fecha `parsear_respuesta` solo rechazaba el caso vacío,
aceptando en silencio una respuesta con varias hipótesis `confirmada`
a la vez, pese a que el propio prompt en `deepseek.py` ya le pide al
modelo "exactamente una"). Si `conclusion_tipo = 'no_diagnosticable'`,
ninguna hipótesis del intento tiene `desenlace = 'confirmada'` (pueden
existir hipótesis `descartada`/`sin_evidencia_suficiente`, o ninguna en
absoluto si el límite de gasto cortó la llamada antes de proponer nada).

## Gasto diario de DeepSeek

Acumulado de coste real por día natural (spec.md, Key Entities).

| Campo | Tipo | Notas |
|---|---|---|
| `dia` | TEXT (`YYYY-MM-DD`) PK | Día natural, hora local del Mac Mini. |
| `coste_eur_acumulado` | REAL | Suma de `diagnosticos.coste_eur` de ese día. |
| `limite_eur` | REAL | Valor de `DIAGNOSTICO_LIMITE_EUR_DIA` vigente en el momento — se congela por día para que cambiar el límite hoy no reescriba el histórico de ayer. |

## Esquema SQLite (resumen)

```sql
CREATE TABLE episodios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contenedor TEXT NOT NULL,
    es_critico INTEGER NOT NULL,
    en_vivo INTEGER NOT NULL,
    restart_history_id INTEGER,
    ventana_inicio TEXT NOT NULL,
    ventana_fin TEXT NOT NULL,
    snapshot_evidencia TEXT NOT NULL,
    creado_en TEXT NOT NULL
);

CREATE TABLE diagnosticos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episodio_id INTEGER NOT NULL REFERENCES episodios(id),
    conclusion_tipo TEXT NOT NULL,
    conclusion_texto TEXT NOT NULL,
    modelo TEXT,
    tokens_entrada INTEGER NOT NULL DEFAULT 0,
    tokens_salida INTEGER NOT NULL DEFAULT 0,
    coste_eur REAL NOT NULL DEFAULT 0.0,
    creado_en TEXT NOT NULL
);
CREATE INDEX idx_diagnosticos_episodio ON diagnosticos(episodio_id);

CREATE TABLE hipotesis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    diagnostico_id INTEGER NOT NULL REFERENCES diagnosticos(id),
    orden INTEGER NOT NULL,
    descripcion TEXT NOT NULL,
    comprobacion TEXT NOT NULL,
    desenlace TEXT NOT NULL
);
CREATE INDEX idx_hipotesis_diagnostico ON hipotesis(diagnostico_id);

CREATE TABLE gasto_diario (
    dia TEXT PRIMARY KEY,
    coste_eur_acumulado REAL NOT NULL DEFAULT 0.0,
    limite_eur REAL NOT NULL
);
```

## Relación con `homelab.db` (lectura, no FK real)

`episodios.restart_history_id` referencia `homelab.db.restart_history.id`
solo a título informativo — son bases de datos distintas (research.md §4),
así que no hay integridad referencial real entre ellas. Toda la
información que hiciera falta de esa fila ya está copiada dentro de
`snapshot_evidencia` en el momento de congelar; `restart_history_id` es
solo para poder localizar la fila original al inspeccionar manualmente
`homelab.db`, no una dependencia funcional del feature.
