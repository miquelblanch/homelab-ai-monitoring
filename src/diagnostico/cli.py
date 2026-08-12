"""cli — Punto de entrada del diagnóstico de episodios. Contrato:
specs/007-diagnostico-episodios/contracts/cli.md, generalizado a discos
en specs/009-diagnostico-discos/contracts/cli.md.

Uso:
    python3 -m diagnostico.cli congelar --historico RESTART_HISTORY_ID
    python3 -m diagnostico.cli congelar --vivo CONTENEDOR
    python3 -m diagnostico.cli congelar --disco-historico LABEL@MOMENTO_ISO
    python3 -m diagnostico.cli congelar --disco-vivo LABEL
    python3 -m diagnostico.cli congelar --ha-historico CHECK_ID@MOMENTO_ISO
    python3 -m diagnostico.cli congelar --ha-vivo CHECK_ID
    python3 -m diagnostico.cli congelar --backup-historico MOMENTO_ISO
    python3 -m diagnostico.cli congelar --backup-vivo
    python3 -m diagnostico.cli congelar --relay-historico MOMENTO_ISO
    python3 -m diagnostico.cli congelar --relay-vivo NOMBRE
    python3 -m diagnostico.cli congelar --inventario-historico NOMBRE@EJECUCION_ID
    python3 -m diagnostico.cli congelar --inventario-vivo NOMBRE
    python3 -m diagnostico.cli congelar --host-externo-historico NOMBRE@MOMENTO_ISO
    python3 -m diagnostico.cli congelar --host-externo-vivo NOMBRE
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
    origen.add_argument(
        "--ha-vivo",
        metavar="CHECK_ID",
        help="Congela el estado actual de un check de Home Assistant en vivo (feature 010).",
    )
    origen.add_argument(
        "--ha-historico",
        metavar="CHECK_ID@MOMENTO_ISO",
        help="Congela un momento pasado concreto de un check de Home Assistant (feature 010).",
    )
    origen.add_argument(
        "--backup-vivo",
        action="store_true",
        help="Congela el log de backup más reciente (feature 011). Sin argumento — solo hay una serie.",
    )
    origen.add_argument(
        "--backup-historico",
        metavar="MOMENTO_ISO",
        help="Congela el log de backup más cercano a ese momento, dentro de ±12h (feature 011).",
    )
    origen.add_argument(
        "--relay-vivo",
        metavar="NOMBRE",
        help="Congela el estado actual de un relay concreto (feature 012). Entrecomillar si tiene espacios.",
    )
    origen.add_argument(
        "--relay-historico",
        metavar="MOMENTO_ISO",
        help="Congela la evidencia agregada de relays en ±180min de ese momento (feature 012). Sin nombre de relay.",
    )
    origen.add_argument(
        "--inventario-vivo",
        metavar="NOMBRE",
        help="Congela el hallazgo actual de un componente del inventario, en la ejecución más reciente (feature 013). Entrecomillar si tiene espacios.",
    )
    origen.add_argument(
        "--inventario-historico",
        metavar="NOMBRE@EJECUCION_ID",
        help="Congela el hallazgo de un componente del inventario en una ejecución pasada concreta (feature 013).",
    )
    origen.add_argument(
        "--host-externo-vivo",
        metavar="NOMBRE",
        help="Congela el estado ya calculado de un host externo (feature 014). Entrecomillar si tiene espacios.",
    )
    origen.add_argument(
        "--host-externo-historico",
        metavar="NOMBRE@MOMENTO_ISO",
        help="Congela la densidad de muestras de rendimiento de un host externo en ±24h de ese momento (feature 014).",
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
            ha_vivo=args.ha_vivo,
            ha_historico=args.ha_historico,
            backup_vivo=args.backup_vivo,
            backup_historico=args.backup_historico,
            relay_vivo=args.relay_vivo,
            relay_historico=args.relay_historico,
            inventario_vivo=args.inventario_vivo,
            inventario_historico=args.inventario_historico,
            host_externo_vivo=args.host_externo_vivo,
            host_externo_historico=args.host_externo_historico,
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
    ha_vivo: str | None,
    ha_historico: str | None,
    backup_vivo: bool,
    backup_historico: str | None,
    relay_vivo: str | None,
    relay_historico: str | None,
    inventario_vivo: str | None,
    inventario_historico: str | None,
    host_externo_vivo: str | None,
    host_externo_historico: str | None,
) -> int:
    from datetime import datetime

    from . import evidencia, store

    try:
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
            elif disco_historico is not None:
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
            elif ha_vivo is not None:
                episodio = evidencia.congelar_ha_vivo(conn, ha_vivo)
                modo = "en vivo"
            elif ha_historico is not None:
                check_id, _, momento_str = ha_historico.partition("@")
                if not momento_str:
                    print(
                        f"--ha-historico espera CHECK_ID@MOMENTO_ISO, no {ha_historico!r}",
                        file=sys.stderr,
                    )
                    return 1
                episodio = evidencia.congelar_ha_historico(
                    conn, check_id, datetime.fromisoformat(momento_str)
                )
                modo = "histórico"
            elif backup_vivo:
                episodio = evidencia.congelar_backup_vivo(conn)
                modo = "en vivo"
            elif backup_historico is not None:
                episodio = evidencia.congelar_backup_historico(
                    conn, datetime.fromisoformat(backup_historico)
                )
                modo = "histórico"
            elif relay_vivo is not None:
                episodio = evidencia.congelar_relay_vivo(conn, relay_vivo)
                modo = "en vivo"
            elif relay_historico is not None:
                episodio = evidencia.congelar_relay_historico(
                    conn, datetime.fromisoformat(relay_historico)
                )
                modo = "histórico"
            elif inventario_vivo is not None:
                episodio = evidencia.congelar_inventario_vivo(conn, inventario_vivo)
                modo = "en vivo"
            elif inventario_historico is not None:
                nombre, _, ejecucion_id_str = inventario_historico.rpartition("@")
                if not nombre:
                    print(
                        f"--inventario-historico espera NOMBRE@EJECUCION_ID, no "
                        f"{inventario_historico!r}",
                        file=sys.stderr,
                    )
                    return 1
                episodio = evidencia.congelar_inventario_historico(
                    conn, nombre, int(ejecucion_id_str)
                )
                modo = "histórico"
            elif host_externo_vivo is not None:
                episodio = evidencia.congelar_host_externo_vivo(conn, host_externo_vivo)
                modo = "en vivo"
            else:
                nombre, _, momento_str = host_externo_historico.partition("@")
                if not momento_str:
                    print(
                        f"--host-externo-historico espera NOMBRE@MOMENTO_ISO, no "
                        f"{host_externo_historico!r}",
                        file=sys.stderr,
                    )
                    return 1
                episodio = evidencia.congelar_host_externo_historico(
                    conn, nombre, datetime.fromisoformat(momento_str)
                )
                modo = "histórico"
    except ValueError as e:
        # FR-010: los checks de la cerradura se rechazan explícitamente
        # (evidencia.CHECKS_HA_EXCLUIDOS_CERRADURA) — mismo tratamiento
        # que un restart_history_id inexistente, ya usado por --historico.
        print(str(e), file=sys.stderr)
        return 1

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
