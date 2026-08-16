"""cli — Punto de entrada de la remediación. Contratos:
specs/019-remediacion-automatica/contracts/cli.md,
specs/021-remediacion-contenedores/contracts/cli.md.

Uso:
    python3 -m remediacion.cli comprobar
    python3 -m remediacion.cli comprobar-contenedores
    python3 -m remediacion.cli comprobar-agentes
    python3 -m remediacion.cli pendientes
    python3 -m remediacion.cli tipos
    python3 -m remediacion.cli contenedores
    python3 -m remediacion.cli agentes
    python3 -m remediacion.cli aprobar INTENTO_ID
    python3 -m remediacion.cli rechazar INTENTO_ID
    python3 -m remediacion.cli deshacer INTENTO_ID
    python3 -m remediacion.cli modo TIPO_ACCION (--automatico | --manual)
    python3 -m remediacion.cli modo-contenedor CONTENEDOR (--automatico | --manual)
    python3 -m remediacion.cli historial TIPO_ACCION
    python3 -m remediacion.cli --selftest

Garantías de 019 (contracts/cli.md), válidas para `rotar_log`:
1. Todo tipo de acción empieza en modo manual (FR-002).
2. `comprobar` nunca actúa sobre un fichero fuera de la lista cerrada
   de logs vigilados (FR-005).
3. Ninguna rotación trunca ni borra contenido — siempre renombra
   (FR-009).
4. `deshacer` nunca sobreescribe lo escrito después de la rotación
   (FR-010).
5. Sin ninguna llamada de red ni a DeepSeek (FR-013). Sin ninguna
   notificación ni superficie de dashboard (FR-014).

Garantías añadidas por 021 (contracts/cli.md), válidas para
`reiniciar_contenedor`:
6. DeepSeek nunca elige fuera de la lista cerrada de acciones (FR-003).
7. Ningún contenedor crítico ni `frigate` recibe una evaluación, una
   propuesta, ni un cambio de modo (FR-006).
8. Un fallo de la llamada a DeepSeek nunca se registra como "ninguna
   acción aplica" — estado `sin_evaluar`, distinto de `sin_accion`
   (FR-015).
9. Sin llamada a DeepSeek sin presupuesto disponible (FR-013/FR-014).
10. Ningún reinicio se ejecuta sin verificación real de `running`
    (FR-010). Sin operación de deshacer para un intento de reinicio
    (FR-016) — `deshacer` lo rechaza explícitamente.

Garantías añadidas por 022 (specs/022-clasificacion-remediacion/,
contracts/cli.md), válidas para contenedores críticos:
11. `comprobar-contenedores` ya SÍ evalúa contenedores críticos
    (FR-009) — pero siempre con modo forzado a "manual"; nunca los
    ejecuta sin aprobación explícita (FR-008/FR-010). `frigate`
    (NEVER_RESTART) sigue totalmente excluido, sin cambios (FR-007).
12. `modo-contenedor CONTENEDOR --automatico` sigue rechazado para un
    crítico (ahora vía la guarda de `store.set_modo_contenedor`, no
    solo en este módulo) — `--manual` sobre un crítico se acepta sin
    efecto real. Sobre `frigate` (NEVER_RESTART), ambos se rechazan.
13. `contenedores --incluir-criticos` añade los críticos a la lista,
    con `modo: null` — nunca mezclados con el modo real de los no
    críticos.

Garantías añadidas por 026 (contracts/cli.md), válidas para
`reiniciar_agente`:
14. DeepSeek nunca elige fuera de la lista cerrada de acciones para un
    agente (mismo criterio que la garantía 6).
15. Ningún `com.homeassistant.*` se reinicia sin que `sudo -n`
    confirme el permiso exacto en el momento de ejecutar — un permiso
    no instalado produce `estado="fallido"` con el motivo real, nunca
    un intento ignorado en silencio.
16. Un reinicio de agente se verifica EN VIVO (`launchctl list`),
    nunca contra el volcado periódico `LAUNCHAGENTS_RAW` ni contra el
    código de salida de `launchctl kickstart` (FR-006).
17. Sin operación de deshacer para un intento de agente (FR-007) —
    `deshacer` lo rechaza explícitamente, mismo criterio que un
    reinicio de contenedor.
18. El cortacircuito de agentes cuenta solo sobre `intentos_agente`,
    con el mismo umbral compartido que contenedores (3 intentos/6h,
    Clarifications sesión 2026-08-16).
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
        help=(
            "Autocomprobación — ejecuta la suite completa compartida de los "
            "tres paquetes (diagnóstico, inventario, remediación), no solo "
            "la de este paquete. Contra logs de prueba en un directorio temporal."
        ),
    )

    subparsers = parser.add_subparsers(dest="comando")

    subparsers.add_parser("comprobar", help="Evalúa la lista cerrada de logs vigilados (FR-005/FR-006/FR-007).")
    subparsers.add_parser(
        "comprobar-contenedores",
        help="Evalúa con DeepSeek los contenedores no críticos caídos (021, FR-001/FR-002/FR-006).",
    )
    subparsers.add_parser(
        "comprobar-agentes",
        help="Evalúa con DeepSeek los LaunchAgents/LaunchDaemons caídos (026, FR-001/FR-002/FR-012).",
    )
    subparsers.add_parser("pendientes", help="Lista los intentos pendientes de aprobación (rotar_log, reiniciar_contenedor y reiniciar_agente).")
    subparsers.add_parser("tipos", help="Lista los tipos de acción que existen y su modo actual — solo lectura.")
    contenedores_parser = subparsers.add_parser(
        "contenedores",
        help="Lista los contenedores no críticos con su modo actual — solo lectura (021).",
    )
    contenedores_parser.add_argument(
        "--incluir-criticos",
        action="store_true",
        help="Añade también los contenedores críticos, con modo null (022, contracts/cli.md).",
    )
    subparsers.add_parser(
        "agentes",
        help="Lista los 43 candidatos (amsterdam9.*/com.homeassistant.*) con su estado — solo lectura (026).",
    )

    aprobar_parser = subparsers.add_parser("aprobar", help="Aprueba un intento pendiente y lo ejecuta.")
    aprobar_parser.add_argument("intento_id", type=int)

    rechazar_parser = subparsers.add_parser("rechazar", help="Rechaza un intento pendiente, sin ejecutar nada.")
    rechazar_parser.add_argument("intento_id", type=int)

    deshacer_parser = subparsers.add_parser("deshacer", help="Deshace un intento ya ejecutado (FR-010 de 019). Rechaza reinicios de contenedor (FR-016 de 021) y de agente (FR-007 de 026).")
    deshacer_parser.add_argument("intento_id", type=int)

    modo_parser = subparsers.add_parser("modo", help="Cambia el modo de un tipo de acción (FR-003).")
    modo_parser.add_argument("tipo_accion")
    modo_grupo = modo_parser.add_mutually_exclusive_group(required=True)
    modo_grupo.add_argument("--automatico", action="store_true")
    modo_grupo.add_argument("--manual", action="store_true")

    modo_c_parser = subparsers.add_parser(
        "modo-contenedor", help="Cambia el modo de un contenedor concreto (021, FR-004/FR-006)."
    )
    modo_c_parser.add_argument("contenedor")
    modo_c_grupo = modo_c_parser.add_mutually_exclusive_group(required=True)
    modo_c_grupo.add_argument("--automatico", action="store_true")
    modo_c_grupo.add_argument("--manual", action="store_true")

    historial_parser = subparsers.add_parser("historial", help="Recuento de intentos por estado (FR-004).")
    historial_parser.add_argument("tipo_accion")

    return parser


def _run_selftest() -> int:
    """Ejecuta `tests.selftest.run_all()`, que descubre y corre todos
    los `test_*.py` del directorio — compartido por los tres paquetes,
    no acotado a este (specs/025-consolidar-parseo-deepseek/). Mismo
    mecanismo en `diagnostico.cli`/`inventory.cli --selftest`."""
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
        pendientes_reinicio = store.listar_pendientes_reinicio(conn)
        pendientes_agente = store.listar_pendientes_agente(conn)

    if not pendientes and not pendientes_reinicio and not pendientes_agente:
        print("sin propuestas pendientes")
        return 0
    for intento in pendientes:
        print(f"intento {intento.id} — {intento.tipo_accion} — {intento.componente} — {intento.detalle}")
    for intento in pendientes_reinicio:
        print(f"intento {intento.id} — reiniciar_contenedor — {intento.contenedor} — {intento.detalle}")
    for intento in pendientes_agente:
        print(f"intento {intento.id} — reiniciar_agente — {intento.label} — {intento.detalle}")
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

    with store.connect() as conn:
        ubicacion = store.localizar_intento(conn, intento_id)
        if ubicacion is None:
            print(f"intento {intento_id} no existe", file=sys.stderr)
            return 1
        tabla, _ = ubicacion
        try:
            if tabla == "reinicio":
                intento = acciones.resolver_aprobacion_reinicio(conn, intento_id)
                print(f"intento {intento.id} — {intento.contenedor} — {intento.estado} — {intento.detalle}")
            elif tabla == "agente":
                intento = acciones.resolver_aprobacion_agente(conn, intento_id)
                print(f"intento {intento.id} — {intento.label} — {intento.estado} — {intento.detalle}")
            else:
                intento = acciones.resolver_aprobacion(conn, intento_id)
                print(f"intento {intento.id} — {intento.estado} — {intento.detalle}")
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
    return 0


def _run_rechazar(intento_id: int) -> int:
    from . import acciones, store

    with store.connect() as conn:
        ubicacion = store.localizar_intento(conn, intento_id)
        if ubicacion is None:
            print(f"intento {intento_id} no existe", file=sys.stderr)
            return 1
        tabla, _ = ubicacion
        try:
            if tabla == "reinicio":
                intento = acciones.resolver_rechazo_reinicio(conn, intento_id)
                print(f"intento {intento.id} — {intento.contenedor} — {intento.estado}")
            elif tabla == "agente":
                intento = acciones.resolver_rechazo_agente(conn, intento_id)
                print(f"intento {intento.id} — {intento.label} — {intento.estado}")
            else:
                intento = acciones.resolver_rechazo(conn, intento_id)
                print(f"intento {intento.id} — {intento.estado}")
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
    return 0


def _run_deshacer(intento_id: int) -> int:
    from . import acciones, store

    with store.connect() as conn:
        ubicacion = store.localizar_intento(conn, intento_id)
        if ubicacion is None:
            print(f"intento {intento_id} no existe", file=sys.stderr)
            return 1
        tabla, _ = ubicacion
        if tabla == "reinicio":
            print(
                f"intento {intento_id} es un reinicio de contenedor — sin operación "
                f"de deshacer (FR-016 de 021)",
                file=sys.stderr,
            )
            return 1
        if tabla == "agente":
            print(
                f"intento {intento_id} es un reinicio de agente — sin operación "
                f"de deshacer (FR-007 de 026)",
                file=sys.stderr,
            )
            return 1
        try:
            intento = acciones.resolver_deshacer(conn, intento_id)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            return 1
    print(f"intento {intento.id} — {intento.estado} — {intento.detalle}")
    return 0


def _run_comprobar_contenedores() -> int:
    from . import acciones, store
    from diagnostico import store as diagnostico_store

    with store.connect() as conn_remediacion, diagnostico_store.connect() as conn_diagnostico:
        creados = acciones.comprobar_reiniciar_contenedor(conn_remediacion, conn_diagnostico)

    if not creados:
        print("nada por evaluar, o ya había un intento pendiente/sin_evaluar reciente")
        return 0
    for intento in creados:
        print(f"intento {intento.id} — {intento.contenedor} — {intento.estado} — {intento.detalle}")
    return 0


def _run_comprobar_agentes() -> int:
    from . import acciones, store
    from diagnostico import store as diagnostico_store

    with store.connect() as conn_remediacion, diagnostico_store.connect() as conn_diagnostico:
        creados = acciones.comprobar_reiniciar_agente(conn_remediacion, conn_diagnostico)
        acciones.escribir_snapshot(conn_remediacion)  # 026 — bloque agentes[] para el dashboard

    if not creados:
        print("nada por evaluar, o ya había un intento pendiente/sin_evaluar reciente")
        return 0
    for intento in creados:
        print(f"intento {intento.id} — {intento.label} — {intento.estado} — {intento.detalle}")
    return 0


def _run_agentes() -> int:
    from . import _homelab_bridge as bridge
    from . import store

    with store.connect() as conn:
        modo = store.get_modo(conn, "reiniciar_agente")
        for agente in bridge.listar_agentes_conocidos():
            label = agente["label"]
            estado = "activo" if agente["running"] else "caído"
            linea = f"{label} — {estado} — modo {modo}"
            if agente["requiere_sudo"]:
                sudoers_ok = bridge.sudoers_permitido(label)
                linea += f" — sudoers {'instalado' if sudoers_ok else 'NO instalado'}"
            print(linea)
    return 0


def _run_contenedores(incluir_criticos: bool = False) -> int:
    from . import _homelab_bridge as bridge
    from . import store

    criticos = bridge.docker_critical()
    never_restart = bridge.docker_never_restart()
    nombres = tuple(
        c["name"]
        for c in bridge.listar_contenedores()
        if c.get("name") and c["name"] not in criticos and c["name"] not in never_restart
    )
    with store.connect() as conn:
        modos = store.listar_modos_contenedor(conn, nombres)

    if not modos and not (incluir_criticos and criticos):
        print("sin contenedores no críticos conocidos (¿docker_monitor.py disponible?)")
        return 0
    for contenedor, modo in modos:
        print(f"{contenedor} — modo {modo}")
    if incluir_criticos:
        # 022, contracts/cli.md: los críticos no tienen modo configurable
        # — se listan aparte, con "null", nunca mezclados con listar_modos_contenedor
        # (que solo conoce configuracion_contenedor, sin fila para ellos).
        for contenedor in sorted(criticos):
            print(f"{contenedor} — modo null (crítico)")
    return 0


def _run_modo_contenedor(contenedor: str, automatico: bool) -> int:
    from . import _homelab_bridge as bridge
    from . import store

    if contenedor in bridge.docker_never_restart():
        print(
            f"{contenedor} es NEVER_RESTART — rechazado, sin escribir nada "
            f"(FR-007 de 022, sin cambios respecto a FR-006 de 021)",
            file=sys.stderr,
        )
        return 1
    nuevo_modo = "automatico" if automatico else "manual"
    with store.connect() as conn:
        try:
            store.set_modo_contenedor(conn, contenedor, nuevo_modo)
        except ValueError as e:
            # store.set_modo_contenedor ya rechaza "automatico" para un
            # crítico (FR-008, guarda de escritura, research.md §2 de
            # 022) — "manual" sobre un crítico sí se acepta, sin efecto
            # real sobre la evaluación (evaluar_contenedor la fuerza).
            print(str(e), file=sys.stderr)
            return 1
    print(f"{contenedor} → modo {nuevo_modo}")
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
    if args.comando == "comprobar-contenedores":
        return _run_comprobar_contenedores()
    if args.comando == "comprobar-agentes":
        return _run_comprobar_agentes()
    if args.comando == "pendientes":
        return _run_pendientes()
    if args.comando == "tipos":
        return _run_tipos()
    if args.comando == "contenedores":
        return _run_contenedores(args.incluir_criticos)
    if args.comando == "agentes":
        return _run_agentes()
    if args.comando == "aprobar":
        return _run_aprobar(args.intento_id)
    if args.comando == "rechazar":
        return _run_rechazar(args.intento_id)
    if args.comando == "deshacer":
        return _run_deshacer(args.intento_id)
    if args.comando == "modo":
        return _run_modo(args.tipo_accion, args.automatico)
    if args.comando == "modo-contenedor":
        return _run_modo_contenedor(args.contenedor, args.automatico)
    if args.comando == "historial":
        return _run_historial(args.tipo_accion)

    build_parser().print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
