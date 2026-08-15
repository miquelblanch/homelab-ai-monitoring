# Contrato: fachada `diagnostico.evidencia`

Este refactor no expone una API externa (HTTP, CLI pública) nueva. El único
contrato real es interno: los tres consumidores listados en `data-model.md`
deben poder seguir escribiendo `from diagnostico import evidencia;
evidencia.<función>(...)` exactamente como hoy, con la misma firma y el
mismo tipo de retorno. Este documento fija ese contrato para que
`speckit-tasks` pueda derivar una tarea de verificación por función.

## Firmas que la fachada DEBE preservar

| Función | Firma (sin cambios) | Retorno |
|---|---|---|
| `congelar_historico` | `(conn: sqlite3.Connection, restart_history_id: int) -> Episodio` | `Episodio` con `origen="contenedor"` |
| `congelar_vivo` | `(conn: sqlite3.Connection, contenedor: str) -> Episodio` | ídem |
| `congelar_disco_vivo` | `(conn: sqlite3.Connection, label: str) -> Episodio` | `Episodio` con `origen="disco"` |
| `congelar_disco_historico` | `(conn: sqlite3.Connection, label: str, momento: datetime) -> Episodio` | ídem |
| `congelar_ha_vivo` | `(conn: sqlite3.Connection, check_id: str) -> Episodio` | `Episodio` con `origen="ha"` |
| `congelar_ha_historico` | `(conn: sqlite3.Connection, check_id: str, momento: datetime) -> Episodio` | ídem |
| `congelar_backup_vivo` | `(conn: sqlite3.Connection) -> Episodio` | `Episodio` con `origen="backup"` |
| `congelar_backup_historico` | `(conn: sqlite3.Connection, momento: datetime) -> Episodio` | ídem |
| `congelar_relay_vivo` | `(conn: sqlite3.Connection, nombre: str) -> Episodio` | `Episodio` con `origen="relay"` |
| `congelar_relay_historico` | `(conn: sqlite3.Connection, momento: datetime) -> Episodio` | ídem |
| `listar_nombres_relay` | `() -> set[str]` | catálogo completo de relays conocidos |
| `nombres_relay_evidenciados` | `(agregado: list[dict] \| None) -> set[str]` | subconjunto con evidencia real en la ventana |
| `congelar_inventario_vivo` | `(conn: sqlite3.Connection, nombre: str) -> Episodio` | `Episodio` con `origen="inventario"` |
| `congelar_inventario_historico` | `(conn: sqlite3.Connection, nombre: str, ejecucion_id: int) -> Episodio` | ídem |
| `congelar_host_externo_vivo` | `(conn: sqlite3.Connection, nombre: str) -> Episodio` | `Episodio` con `origen="host_externo"` |
| `congelar_host_externo_historico` | `(conn: sqlite3.Connection, nombre: str, momento: datetime) -> Episodio` | ídem |
| `congelar_hub_beszel_vivo` | `(conn: sqlite3.Connection) -> Episodio` | `Episodio` con `origen="hub_beszel"` |
| `congelar_hub_beszel_historico` | `(conn: sqlite3.Connection, momento: datetime) -> Episodio` | ídem |
| `congelar_agente_vivo` | `(conn: sqlite3.Connection, label: str) -> Episodio` | `Episodio` con `origen="agente"` — sin variante histórica, spec Edge Cases |
| `congelar_latido_vivo` | `(conn: sqlite3.Connection, job: str) -> Episodio` | `Episodio` con `origen="latido"` — sin variante histórica |

Todas las firmas de esta tabla están copiadas literalmente de
`src/diagnostico/evidencia.py` (comprobado línea a línea, no reconstruido de
memoria) — este contrato fija que no cambien al moverlas, nada más.

## Cómo se verifica el contrato (para `tasks.md`)

1. **Import**: `from diagnostico import evidencia` sigue funcionando tras el
   cambio, y `evidencia.<nombre>` resuelve a la misma función (verificable
   con `inspect.signature` antes/después, o simplemente con que
   `test_evidencia_<origen>.py` importe y llame vía la fachada, no solo vía
   el submódulo).
2. **Comportamiento**: `test_evidencia_<origen>.py` reproduce, para cada
   función pública, al menos un caso ya existente en el
   `test_evidencia.py` actual — no casos nuevos, los mismos, movidos.
3. **Consumidores reales**: tras completar el split, ejecutar
   `PYTHONPATH=src python3 -m diagnostico.cli --selftest` y
   `PYTHONPATH=src python3 -m remediacion.cli --selftest` (ambos disparan la
   suite completa, incluida `test_evidencia_relay.py` que cubre el camino
   de `deepseek.py`) — deben terminar exactamente igual que antes del
   cambio (mismo recuento de aserciones, cero fallos nuevos).
