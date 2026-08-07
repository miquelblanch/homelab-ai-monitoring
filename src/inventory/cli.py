"""cli — Punto de entrada del inventario. Contrato: contracts/cli.md.

Uso:
    python3 -m inventory.cli [--gaps] [--since RUN_ID] [--no-telegram] [--no-dashboard] [--selftest]

Garantías (contracts/cli.md), válidas para cualquier combinación de flags:
1. Nunca modifica el homelab (FR-016).
2. Nunca deja un componente sin las tres respuestas (FR-010).
3. Código de salida 0 solo si la ejecución completó y persistió el
   resultado — un fallo de entrega no hace fallar el proceso si la
   persistencia tuvo éxito, pero si degrada el latido (ver deliver.py).
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m inventory.cli",
        description="Inventario sistemático de cobertura del homelab.",
    )
    parser.add_argument(
        "--gaps",
        action="store_true",
        help="Solo el listado filtrado de brechas (FR-011).",
    )
    parser.add_argument(
        "--since",
        metavar="RUN_ID",
        type=int,
        default=None,
        help="Comparar contra una ejecución pasada concreta en vez de la anterior (FR-015).",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="No enviar por Telegram (sí persiste y escribe el JSON del dashboard).",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="No escribir el JSON del dashboard (sí persiste y envía Telegram).",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Autocomprobación de lógica pura, sin tocar Docker/HA/Telegram reales.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selftest:
        return _run_selftest()

    return _run_default(
        gaps_only=args.gaps,
        since_run_id=args.since,
        send_telegram=not args.no_telegram,
        write_dashboard=not args.no_dashboard,
    )


def _run_selftest() -> int:
    """T037 — orquesta test_evaluate/test_identity/test_diff/test_no_mutation."""
    from tests.selftest import run_all

    return run_all()


def _run_default(
    *,
    gaps_only: bool,
    since_run_id: int | None,
    send_telegram: bool,
    write_dashboard: bool,
) -> int:
    """Ejecución por defecto (T023): recorre todo el homelab, persiste,
    entrega, y registra el latido. `--gaps` (T028) y `--since` (T032)
    reutilizan esta misma ejecución — no son un modo aparte."""
    from . import deliver, sources, store

    raw_componentes = sources.all_components()

    with store.connect() as conn:
        ejecucion_id = store.save_run(conn, raw_componentes, disparador="manual")
        store.populate_brechas(conn, ejecucion_id)
        persisted_ok = True  # save_run ya hizo commit; si hubiera fallado, habría lanzado

        if gaps_only:
            _print_gaps(conn, ejecucion_id)
        else:
            _print_full_listing(conn, ejecucion_id)

        if since_run_id is not None:
            _print_diff(conn, ejecucion_id, since_run_id)

        telegram_ok = True
        if send_telegram:
            telegram_ok = deliver.send_telegram(conn, ejecucion_id, gaps_only=gaps_only)
            if not telegram_ok:
                print("⚠️  No se pudo entregar por Telegram.", file=sys.stderr)

        dashboard_ok = True
        if write_dashboard:
            dashboard_ok = deliver.write_dashboard_json(conn, ejecucion_id)
            if not dashboard_ok:
                print("⚠️  No se pudo escribir el JSON del dashboard.", file=sys.stderr)

    deliver.record_heartbeat(persisted_ok, telegram_ok and dashboard_ok)
    return 0


def _print_full_listing(conn, ejecucion_id: int) -> None:
    from . import store

    ejecucion = store.get_ejecucion(conn, ejecucion_id)
    print(f"Ejecución #{ejecucion_id} — {ejecucion['total_componentes']} componentes, "
          f"{ejecucion['total_brechas']} brechas")
    for h in store.hallazgos_de_ejecucion(conn, ejecucion_id):
        marca = "❌" if h["es_brecha"] else "✅"
        print(
            f"{marca} [{h['categoria']}] {h['nombre_actual']} — "
            f"declarado={h['estado_declarado_status']} "
            f"vigilado={'sí' if h['esta_vigilado'] else 'no'} "
            f"dashboard={h['llega_a_dashboard']}"
        )


def _print_gaps(conn, ejecucion_id: int) -> None:
    from . import store

    ejecucion = store.get_ejecucion(conn, ejecucion_id)
    print(f"Ejecución #{ejecucion_id} — {ejecucion['total_brechas']} brechas")
    for b in store.brechas_de_ejecucion(conn, ejecucion_id):
        nueva = " [NUEVA]" if b["primera_ejecucion_id"] == ejecucion_id else " [conocida]"
        print(f"❌ [{b['categoria']}] {b['tipo']}{nueva} — {b['contexto']}")


def _print_diff(conn, ejecucion_actual_id: int, since_run_id: int) -> None:
    from . import diff

    c = diff.compare_runs(conn, ejecucion_actual_id, since_run_id)
    print(f"\nComparación contra la ejecución #{since_run_id}:")
    print(f"  Componentes nuevos: {len(c.componentes_nuevos)}")
    for n in c.componentes_nuevos:
        print(f"    + {n}")
    print(f"  Componentes de baja: {len(c.componentes_de_baja)}")
    for n in c.componentes_de_baja:
        print(f"    - {n}")
    print(f"  Brechas nuevas: {len(c.brechas_nuevas)}")
    for n in c.brechas_nuevas:
        print(f"    ❌ {n}")
    print(f"  Brechas resueltas: {len(c.brechas_resueltas)}")
    for n in c.brechas_resueltas:
        print(f"    ✅ {n}")


if __name__ == "__main__":
    sys.exit(main())
