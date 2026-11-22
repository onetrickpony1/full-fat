"""JASP's connection for chats (its MCP server, the setting rpcServerEnabled) is on only while Full Fat opens JASP.

While the setting is on, any program on this computer can reach JASP whenever JASP starts. JASP reads the setting
once, when it starts, and never writes it back unless the user ticks its box (see the end of jasp.py's docstring).
So Full Fat switches it on, starts JASP, waits until JASP answers, and switches it off again. JASP's connection
then stays up until JASP quits, and the next JASP start without Full Fat has none.

A user who had switched the setting on before Full Fat keeps it: Full Fat records the value it first found
(state key `jasp_changes`, field `previous`) and only ever puts that value back.
"""

from __future__ import annotations

from . import jasp, state

ON = ("true", "1")


def record(store: jasp.Store) -> dict | None:
    for c in state.load().get("jasp_changes", []):
        if isinstance(c, dict) and isinstance(c.get("store"), dict) and \
                jasp.Store.from_json(c["store"]).ident() == store.ident():
            return c
    return None


def remember(store: jasp.Store) -> dict:
    """Back up JASP's settings and note the original value, the first time Full Fat sees this store."""
    rec = record(store)
    if rec is not None:
        return rec
    store.backup(state.backup_dir())
    rec = {"store": store.to_json(), "previous": store.get(jasp.KEY_ENABLED)}
    changes = [c for c in state.load().get("jasp_changes", []) if isinstance(c, dict)]
    state.save({"jasp_changes": changes + [rec]})
    return rec


def users_own(rec: dict | None) -> bool:
    """The setting was on before Full Fat touched it: it belongs to the user and stays on."""
    return rec is not None and str(rec.get("previous")).lower() in ON


def switch_on(store: jasp.Store) -> bool:
    remember(store)
    if not store.enabled():
        store.set(jasp.KEY_ENABLED, True)
    return store.enabled()


def switch_off(store: jasp.Store) -> bool:
    """Put back the value from before Full Fat. False when it stays on because it is the user's own."""
    rec = remember(store)
    if users_own(rec):
        return False
    restore(rec)
    return True


def restore(rec: dict) -> None:
    """Put one recorded store back as it was before Full Fat (unless it was on, which stays)."""
    if users_own(rec):
        return
    store = jasp.Store.from_json(rec["store"])
    if store.kind == "ini" and not store.exists():
        return
    prev = rec.get("previous")
    if prev is None:
        if store.get(jasp.KEY_ENABLED) is not None:
            store.remove(jasp.KEY_ENABLED)
    elif store.enabled():
        store.set(jasp.KEY_ENABLED, False)


def left_on(store: jasp.Store) -> bool:
    """On disk although it is not the user's own: a chat start that was interrupted, or an older Full Fat."""
    return store.enabled() and not users_own(record(store)) and record(store) is not None
