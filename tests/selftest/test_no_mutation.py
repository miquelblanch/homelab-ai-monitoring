"""test_no_mutation — T040 (hallazgo G2 de `/speckit-analyze`): FR-016,
el inventario nunca modifica el homelab. `sources._run_ro()` solo permite
subcomandos de una lista blanca de solo lectura; cualquier otro debe
fallar de forma ruidosa (una excepción de programación), no en silencio."""

from __future__ import annotations

from inventory import sources
from tests.selftest import check


def test_comando_de_solo_lectura_permitido() -> None:
    # "true" no está en la lista blanca, pero probamos con uno que sí lo
    # está y confirmamos que no lanza por estar en la lista.
    try:
        sources._run_ro(["docker", "ps", "-a", "--format", "{{json .}}"])
        ok = True
    except RuntimeError:
        ok = False
    check("docker ps está en la lista blanca y no lanza", ok)


def test_comando_mutante_rechazado() -> None:
    for cmd in (
        ["docker", "restart", "algun-contenedor"],
        ["docker", "rm", "-f", "algun-contenedor"],
        ["docker", "stop", "algun-contenedor"],
        ["launchctl", "kickstart", "-k", "algo"],
        ["rm", "-rf", "/"],
    ):
        try:
            sources._run_ro(cmd)
            lanzo = False
        except RuntimeError:
            lanzo = True
        check(f"{' '.join(cmd)} fuera de la lista blanca ⇒ RuntimeError", lanzo)


def test_lista_blanca_no_incluye_subcomandos_mutantes_de_docker() -> None:
    mutantes = {"restart", "rm", "stop", "kill", "pause", "unpause", "rename", "update"}
    permitidos = {sub for (prog, sub) in sources._READONLY_ALLOWLIST if prog == "docker"}
    check(
        "ningún subcomando mutante de docker está en la lista blanca",
        mutantes.isdisjoint(permitidos),
    )
