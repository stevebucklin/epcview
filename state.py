"""
Central state store.

Holds the latest Snapshot for each NF (keyed by name) and emits change
events for the history/event log to consume. The CLI views read state
on every redraw; the poller writes after every successful poll.
"""

from collections import defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional

from nfs import Snapshot


class StateStore:

    def __init__(self):
        self._snapshots: Dict[str, Snapshot] = {}
        self._listeners: List[Callable[[Snapshot, Optional[Snapshot]], None]] = []

    def latest(self, nf_name: str) -> Optional[Snapshot]:
        return self._snapshots.get(nf_name)

    def all(self) -> List[Snapshot]:
        return list(self._snapshots.values())

    def by_kind(self, kind: str) -> List[Snapshot]:
        return [s for s in self._snapshots.values() if s.nf_kind == kind]

    def update(self, snap: Snapshot) -> None:
        prev = self._snapshots.get(snap.nf_name)
        self._snapshots[snap.nf_name] = snap
        for cb in self._listeners:
            try:
                cb(snap, prev)
            except Exception:  # noqa: BLE001
                pass

    def subscribe(self, cb: Callable[[Snapshot, Optional[Snapshot]], None]) -> None:
        self._listeners.append(cb)

    # ── cross-NF aggregates the views consume ────────────────────────────────

    def all_enbs(self) -> list:
        out = []
        for s in self.by_kind('mme'):
            if s.up:
                out.extend(s.data.get('enbs', []))
        return out

    def all_ues(self) -> list:
        out = []
        for s in self.by_kind('mme'):
            if s.up:
                out.extend(s.data.get('ues', []))
        # Future: union with AMF UEs (5G); de-dup by supi if both report
        return out

    def all_sessions(self) -> list:
        """All PDU/PDN sessions across every SMF currently up."""
        out = []
        for s in self.by_kind('smf'):
            if s.up:
                out.extend(s.data.get('sessions', []))
        return out

    def sessions_for_supi(self, supi: str) -> list:
        return [s for s in self.all_sessions() if s.supi == supi]

    def all_upf_stats(self) -> list:
        """List of UpfStats for every UPF currently up."""
        out = []
        for s in self.by_kind('upf'):
            if s.up and 'stats' in s.data:
                out.append(s.data['stats'])
        return out


# module-level singleton
STORE = StateStore()
