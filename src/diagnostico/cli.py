"""cli — Punto de entrada del diagnóstico de episodios. Contrato:
specs/007-diagnostico-episodios/contracts/cli.md, generalizado a discos
en specs/009-diagnostico-discos/contracts/cli.md.

Uso:
    python3 -m diagnostico.cli congelar --historico RESTART_HISTORY_ID
    python3 -m diagnostico.cli congelar --vivo CONTENEDOR
    python3 -m diagnostico.cli congelar --disco-historico LABEL@MOMENTO_ISO
    python3 -m diagnostico.cli congelar --disco-vivo LABEL
    python3 -m diagnostico.cli diagnosticar EPISODIO_ID
    python3 -m diagnostico.cli mostrar EPISODIO_ID [--diagnostico DIAGNOSTICO_ID]
    python3 -m diagnostico.cli --selftest

Garantías (contracts/cli.md), válidas para cualquier subcomando:
1. Nunca ejecuta ni propone una acción correctiva sobre el homelab (FR-012).
2. Nunca actúa sobre un contenedor crítico más allá de leer su evidencia
   (FR-013a) — la única diferencia es el campo `es_critico` del snapshot.
3. `diagnosticar` nunca llama a DeepSeek si ya se sabe que superaría el
   límite de gasto diario (FR-010).
4. Ningún subcomando se dispara solo — cada invocación la decide Miquel
   explícitamente (FR-015).
5. `diagnosticar` nunca vuelve a consultar el estado en vivo del homelab
   — toda su entrada es el snapshot ya persistido al congelar (FR-002).
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m diagnostico.cli",
        description="Diagnóstico de episodios de contenedor (sin remediación).",
    )
    parser.add_argument(
        "--selftest",
        action="store_true",
        help="Autocomprobación de lógica pura, sin tocar DeepSeek/Docker/homelab.db reales.",
    )

    subparsers = parser.add_subparsers(dest="comando")

    congelar_parser = subparsers.add_parser(
        "congelar", help="Congela el snapshot de evidencia de un episodio (FR-002)."
    )
    origen = congelar_parser.add_mutually_exclusive_group(required=True)
    origen.add_argument(
        "--historico",
        metavar="RESTART_HISTORY_ID",
        type=int,
        help="Congela un episodio ya cerrado de homelab.db.restart_history.",
    )
    origen.add_argument(
        "--vivo",
        metavar="CONTENEDOR",
        help="Congela el estado actual de un contenedor en vivo.",
    )
    origen.add_argument(
        "--disco-vivo",
        metavar="LABEL",
        help="Congela el estado actual de un disco en vivo (feature 009).",
    )
    origen.add_argument(
        "--disco-historico",
        metavar="LABEL@MOMENTO_ISO",
        help="Congela un momento pasado concreto de un disco (feature 009).",
    )

    diagnosticar_parser = subparsers.add_parser(
        "diagnosticar", help="Diagnostica un episodio ya congelado (FR-003 a FR-011)."
    )
    diagnosticar_parser.add_argument("episodio_id", type=int)

    mostrar_parser = subparsers.add_parser(
        "mostrar", help="Imprime un episodio y sus intentos de diagnóstico (FR-006)."
    )
    mostrar_parser.add_argument("episodio_id", type=int)
    mostrar_parser.add_argument(
        "--diagnostico",
        metavar="DIAGNOSTICO_ID",
        type=int,
        default=None,
        help="Filtra a un intento de diagnóstico concreto.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.selftest:
        return _run_selftest()

    if args.comando == "congelar":
        return _run_congelar(
            historico=args.historico,
            vivo=args.vivo,
            disco_vivo=args.disco_vivo,
            disco_historico=args.disco_historico,
        )
    if args.comando == "diagnosticar":
        return _run_diagnosticar(args.episodio_id)
    if args.comando == "mostrar":
        return _run_mostrar(args.episodio_id, diagnostico_id=args.diagnostico)

    build_parser().print_help()
    return 1


def _run_selftest() -> int:
    """T029 — orquesta test_evidencia/test_deepseek/test_gasto/test_store/
    test_reproducibilidad/test_baseline_beszel, mismo patrón que
    `inventory.cli --selftest`."""
    from tests.selftest import run_all

    return run_all()


def _run_congelar(
    *,
    historico: int | None,
    vivo: str | None,
    disco_vivo: str | None,
    disco_historico: str | None,
) -> int:
    from datetime import datetime

    from . import evidencia, store

    with store.connect() as conn:
        if historico is not None:
            episodio = evidencia.congelar_historico(conn, historico)
            modo = "histórico"
        elif vivo is not None:
            episodio = evidencia.congelar_vivo(conn, vivo)
            modo = "en vivo"
        elif disco_vivo is not None:
            episodio = evidencia.congelar_disco_vivo(conn, disco_vivo)
            modo = "en vivo"
        else:
            label, _, momento_str = disco_historico.partition("@")
            if not momento_str:
                print(
                    f"--disco-historico espera LABEL@MOMENTO_ISO, no {disco_historico!r}",
                    file=sys.stderr,
                )
                return 1
            episodio = evidencia.congelar_disco_historico(
                conn, label, datetime.fromisoformat(momento_str)
            )
            modo = "histórico"

    print(
        f"episodio {episodio.id} congelado ({episodio.componente}, {modo}, "
        f"crítico={'sí' if episodio.es_critico else 'no'})"
    )
    return 0


def _run_diagnosticar(episodio_id: int) -> int:
    from . import deepseek, store

    with store.connect() as conn:
        episodio = store.get_episodio(conn, episodio_id)
        if episodio is None:
            print(f"episodio {episodio_id} no existe", file=sys.stderr)
            return 1

        # deepseek.diagnosticar_episodio ya aplica el cortacircuitos de
        # gasto (FR-010), llama a DeepSeek si hay presupuesto, persiste
        # el diagnóstico y sus hipótesis, y registra el coste real.
        diagnostico, hipotesis = deepseek.diagnosticar_episodio(conn, episodio)

    print(f"diagnóstico #{diagnostico.id}: {diagnostico.conclusion_tipo}")
    print(f"  {diagnostico.conclusion_texto}")
    print(f"  {len(hipotesis)} hipótesis consideradas")
    return 0


def _run_mostrar(episodio_id: int, *, diagnostico_id: int | None) -> int:
    from . import store

    with store.connect() as conn:
        episodio = store.get_episodio(conn, episodio_id)
        if episodio is None:
            print(f"episodio {episodio_id} no existe", file=sys.stderr)
            return 1

        print(
            f"episodio {episodio.id} — {episodio.componente} ({episodio.origen}) "
            f"({'en vivo' if episodio.en_vivo else 'histórico'}, "
            f"crítico={'sí' if episodio.es_critico else 'no'})"
        )
        print(f"  ventana: {episodio.ventana_inicio} .. {episodio.ventana_fin}")

        diagnosticos = store.diagnosticos_de_episodio(conn, episodio_id)
        if diagnostico_id is not None:
            diagnosticos = [d for d in diagnosticos if d["id"] == diagnostico_id]

        if not diagnosticos:
            print("  (sin diagnósticos todavía)")
            return 0

        for d in diagnosticos:
            print(f"\n  diagnóstico #{d['id']} — {d['conclusion_tipo']} "
                  f"({d['creado_en']})")
            print(f"    {d['conclusion_texto']}")
            for h in store.hipotesis_de_diagnostico(conn, d["id"]):
                print(f"    [{h['desenlace']}] {h['descripcion']}")
                print(f"      comprobación: {h['comprobacion']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
