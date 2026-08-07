"""tests.selftest — runner de autocomprobación, mismo patrón que
`test_docker_monitor.py` del resto del homelab: sin pytest, funciones
`test_*` que llaman a `check(label, cond)`, recolectadas en `FAILURES`.

Uso:
    python3 -m inventory.cli --selftest
"""

from __future__ import annotations

import importlib
import pkgutil

FAILURES: list[str] = []


def check(label: str, cond: bool) -> None:
    print(f"  {'OK   ' if cond else 'FALLO'} {label}")
    if not cond:
        FAILURES.append(label)


def run_all() -> int:
    """Descubre y ejecuta todos los `test_*.py` de este paquete (T037:
    junta test_evaluate, test_identity, test_diff, test_no_mutation)."""
    FAILURES.clear()

    import tests.selftest as _pkg

    for _, modname, _ in pkgutil.iter_modules(_pkg.__path__):
        if not modname.startswith("test_"):
            continue
        module = importlib.import_module(f"tests.selftest.{modname}")
        print(modname)
        for name in sorted(dir(module)):
            if name.startswith("test_"):
                getattr(module, name)()

    if FAILURES:
        print(f"\n{len(FAILURES)} fallo(s): {', '.join(FAILURES)}")
        return 1
    print("\nTodo OK")
    return 0
