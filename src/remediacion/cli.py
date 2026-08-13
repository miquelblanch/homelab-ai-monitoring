"""cli — Punto de entrada de la remediación. Contrato:
specs/019-remediacion-automatica/contracts/cli.md.

Uso:
    python3 -m remediacion.cli comprobar
    python3 -m remediacion.cli pendientes
    python3 -m remediacion.cli tipos
    python3 -m remediacion.cli aprobar INTENTO_ID
    python3 -m remediacion.cli rechazar INTENTO_ID
    python3 -m remediacion.cli deshacer INTENTO_ID
    python3 -m remediacion.cli modo TIPO_ACCION (--automatico | --manual)
    python3 -m remediacion.cli historial TIPO_ACCION
    python3 -m remediacion.cli --selftest

Garantías (contracts/cli.md), válidas para cualquier subcomando:
1. Todo tipo de acción empieza en modo manual (FR-002).
2. `comprobar` nunca actúa sobre un fichero fuera de la lista cerrada
   de logs vigilados (FR-005).
3. Ninguna rotación trunca ni borra contenido — siempre renombra
   (FR-009).
4. `deshacer` nunca sobreescribe lo escrito después de la rotación
   (FR-010).
5. Sin ninguna llamada de red ni a DeepSeek (FR-013). Sin ninguna
   notificación ni superficie de dashboard (FR-014).
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m remediacion.cli",
        description="Remediación automática — primera pieza (rotar_log).",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Autocomprobación de lógica pura, contra logs de prueba en un directorio temporal.",
    )

    subparsers = parser.add_subparsers(dest="comando")

    subparsers.add_parser("comprobar", help="Evalúa la lista cerrada de logs vigilados (FR-005/FR-006/FR-007).")
    subparsers.add_parser("pendientes", help="Lista los intentos pendientes de aprobación.")
    subparsers.add_parser("tipos", help="Lista los tipos de acción que existen y su modo actual — solo lectura.")

    aprobar_parser = subparsers.add_parser("aprobar", help="Aprueba un intento pendiente y ejecuta la rotación.")
    aprobar_parser.add_argument("intento_id", type=int)

    rechazar_parser = subparsers.add_parser("rechazar", help="Rechaza un intento pendiente, sin tocar el fichero.")
    rechazar_parser.add_argument("intento_id", type=int)

    deshacer_parser = subparsers.add_parser("deshacer", help="Deshace un intento ya ejecutado (FR-010).")
    deshacer_parser.add_argument("intento_id", type=int)

    modo_parser = subparsers.add_parser("modo", help="Cambia el modo de un tipo de acción (FR-003).")
    modo_parser.add_argument("tipo_accion")
    modo_grupo = modo_parser.add_mutually_exclusive_group(required=True)
    modo_grupo.add_argument("--automatico", action="store_true")
    modo_grupo.add_argument("--manual", action="store_true")

    historial_parser = subparsers.add_parser("historial", help="Recuento de intentos por estado (FR-004).")
    historial_parser.add_argument("tipo_accion")

    return parser


def _run_selftest() -> int:
    from tests.selftest import run_all

    return run_all()


def _run_comprobar() -> int:
    from . import acciones, store

    with store.connect() as conn:
        creados = acciones.comprobar_rotar_log(conn)
        acciones.escribir_snapshot(conn)  # feature 020 — para el dashboard

    if not creados:
        print("nada por encima del umbral, o ya había una propuesta pendiente")
        return 0
    for intento in creados:
        print(f"intento {intento.id} — {intento.componente} — {intento.estado} — {intento.detalle}")
    return 0


def _run_pendientes() -> int:
    from . import store

    with store.connect() as conn:
        pendientes = store.listar_pendientes(conn)

    if not pendientes:
        print("sin propuestas pendientes")
        return 0
    for intento in pendientes:
        print(f"intento {intento.id} — {intento.tipo_accion} — {intento.componente} — {intento.detalle}")
    return 0


def _run_tipos() -> int:
    from . import acciones, store

    with store.connect() as conn:
        modos = store.listar_modos(conn, acciones.TIPOS_ACCION)

    for tipo_accion, modo in modos:
        print(f"{tipo_accion} — modo {modo}")
    return 0


def _run_aprobar(intento_id: int) -> int:
    from . import acciones, store

    try:
        with store.connect() as conn:
            intento = acciones.resolver_aprobacion(conn, intento_id)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"intento {intento.id} — {intento.estado} — {intento.detalle}")
    return 0


def _run_rechazar(intento_id: int) -> int:
    from . import acciones, store

    try:
        with store.connect() as conn:
            intento = acciones.resolver_rechazo(conn, intento_id)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"intento {intento.id} — {intento.estado}")
    return 0


def _run_deshacer(intento_id: int) -> int:
    from . import acciones, store

    try:
        with store.connect() as conn:
            intento = acciones.resolver_deshacer(conn, intento_id)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    print(f"intento {intento.id} — {intento.estado} — {intento.detalle}")
    return 0


def _run_modo(tipo_accion: str, automatico: bool) -> int:
    from . import store

    nuevo_modo = "automatico" if automatico else "manual"
    with store.connect() as conn:
        conteo = store.historial(conn, tipo_accion)
        print(f"historial de {tipo_accion}: {conteo or 'sin intentos todavía'}")
        store.set_modo(conn, tipo_accion, nuevo_modo)
    print(f"{tipo_accion} → modo {nuevo_modo}")
    return 0


def _run_historial(tipo_accion: str) -> int:
    from . import store

    with store.connect() as conn:
        conteo = store.historial(conn, tipo_accion)
        modo = store.get_modo(conn, tipo_accion)
    print(f"{tipo_accion} — modo actual: {modo}")
    print(conteo or "sin intentos todavía")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selftest:
        return _run_selftest()

    if args.comando == "comprobar":
        return _run_comprobar()
    if args.comando == "pendientes":
        return _run_pendientes()
    if args.comando == "tipos":
        return _run_tipos()
    if args.comando == "aprobar":
        return _run_aprobar(args.intento_id)
    if args.comando == "rechazar":
        return _run_rechazar(args.intento_id)
    if args.comando == "deshacer":
        return _run_deshacer(args.intento_id)
    if args.comando == "modo":
        return _run_modo(args.tipo_accion, args.automatico)
    if args.comando == "historial":
        return _run_historial(args.tipo_accion)

    build_parser().print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
