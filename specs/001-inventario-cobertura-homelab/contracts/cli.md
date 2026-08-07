# Contrato — CLI del inventario

**Feature**: [../spec.md](../spec.md)

No hay API HTTP ni biblioteca pública en este feature (`FR-018`: nada de
interfaz nueva). El contrato externo es la línea de comandos: lo que
Miquel (o un LaunchAgent futuro) puede invocar y qué garantiza cada forma
de invocación.

## Invocación

```
python3 -m inventory.cli [--gaps] [--since RUN_ID] [--no-telegram] [--no-dashboard] [--selftest]
```

| Flag | Efecto | Requisito de origen |
|---|---|---|
| *(ninguno)* | Ejecuta el inventario completo, persiste la ejecución, entrega por Telegram y dashboard | FR-013, FR-014, FR-018 |
| `--gaps` | Igual que el modo por defecto, pero solo imprime/entrega el listado filtrado de brechas | FR-011 |
| `--since RUN_ID` | Compara la ejecución actual contra una ejecución pasada concreta en vez de la inmediatamente anterior | FR-015, FR-017 (retención total) |
| `--no-telegram` | No envía a Telegram; sigue persistiendo y escribiendo el JSON del dashboard | Útil para pruebas — no forma parte de un requisito, es higiene operativa |
| `--no-dashboard` | No escribe el JSON del dashboard; sigue persistiendo y enviando Telegram | Igual que arriba |
| `--selftest` | Corre las autocomprobaciones de lógica pura (sin tocar Docker/HA/Telegram reales), patrón `metrics_db.py --selftest` | Higiene operativa, mismo patrón que el resto del homelab |

## Garantías (independientemente de los flags)

1. **Nunca modifica el homelab.** Ninguna combinación de flags ejecuta una
   acción correctiva sobre un componente (FR-016). Esto no es una opción
   desactivable.
2. **Nunca deja un componente sin las tres respuestas.** Si una fuente no
   responde, el componente entra con `sin_evidencia` en lugar de omitirse
   (FR-010, ver Edge Cases del spec).
3. **Código de salida 0** solo si la ejecución completó y logró persistir
   el resultado — un fallo de entrega (Telegram o dashboard) **no** hace
   fallar el proceso completo si la persistencia en SQLite tuvo éxito
   (mismo principio "a prueba de fallos" que `metrics_db.py`), pero sí se
   registra el fallo de entrega en el propio `hallazgo`/log, y el latido
   (`heartbeat.py`, ver `research.md` §7) solo se marca `ok` si **ambas**
   cosas — persistencia y entrega — tuvieron éxito. Es la vía de detección
   de respaldo para el riesgo de Telegram (Edge Case, FR-006).

## Salida por stdout

Texto plano legible, mismo estilo que `docker_list.py`: una línea por
componente en modo completo, una línea por brecha en modo `--gaps`. No es
un contrato formal (no hay otro programa que lo consuma), pero debe ser
suficiente para pegarlo directamente en un mensaje de Telegram sin
reformatear — mismo patrón que el resto de monitores del homelab.
