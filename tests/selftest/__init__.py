"""tests.selftest — runner de autocomprobación, mismo patrón que
`test_docker_monitor.py` del resto del homelab: sin pytest, funciones
`test_*` que llaman a `check(label, cond)`, recolectadas en `FAILURES`.

Uso:
    python3 -m inventory.cli --selftest
"""

from __future__ import annotations

import contextlib
import importlib
import pkgutil
from unittest.mock import patch

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

    # 2026-10-31: una autocomprobación de comprobar-contenedores mandó a
    # Telegram de verdad un «ℹ️ remediación — couchdb: … prueba: healthcheck
    # mal configurado». Durante el selftest ningún módulo puede leer las
    # credenciales de Telegram: todo aviso falla en silencio (False).
    with contextlib.ExitStack() as pila:
        for ruta in ("_homelab_bridge_common", "inventory._homelab_bridge", "remediacion._homelab_bridge"):
            try:
                modulo = importlib.import_module(ruta)
            except ImportError:
                continue
            pila.enter_context(patch.object(modulo, "telegram_credentials", return_value=("", "")))
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
