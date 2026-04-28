"""
NF backend abstractions.

Each component type (MME, SMF, UPF, AMF, …) has its own module here that
knows how to poll its specific endpoints (Open5GS custom JSON +/- the
standard Prometheus /metrics) and turn the result into a Snapshot.

A Snapshot is a normalised, parser-output structure consumed by the
state store and the views. Per-NF specifics live in `data` (a dict of
typed lists/dicts keyed by what the NF cares about).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── normalised data records ──────────────────────────────────────────────────

@dataclass
class EnbInfo:
    """A single eNB known to an MME."""
    enb_id:         int
    plmn:           str
    sctp_peer:      str            # 'host:port' (brackets stripped)
    s1_setup_ok:    bool
    supported_tacs: List[str]      # e.g. ['0001', '0002']
    num_conn_ues:   int
    mme_name:       str            # which MME reports this eNB
    raw:            dict = field(default_factory=dict)  # original JSON for drill-down


@dataclass
class UeInfo:
    """A single UE known to an MME (or AMF on the 5G side)."""
    supi:           str            # IMSI for EPS, SUPI for 5GS
    domain:         str            # 'EPS' / '5GS'
    rat:            str            # 'E-UTRA' / 'NR'
    cm_state:       str            # 'idle' / 'connected'
    serving_enb:    Optional[int]  # only when connected
    serving_cell:   Optional[int]  # only when connected
    tai_plmn:       str
    tai_tac:        int
    ambr_dl_bps:    int
    ambr_ul_bps:    int
    pdns:           List[dict]     # [{apn, qci, ebi, bearer_count, pdu_state}, ...]
    mme_name:       str            # which MME owns this UE
    raw:            dict = field(default_factory=dict)


@dataclass
class Snapshot:
    """One poll's worth of data from one NF.

    Always created — even on poll failure (with up=False, error set).
    The poller publishes this to the state store on every cycle.
    """
    nf_name:    str
    nf_kind:    str
    timestamp:  datetime
    up:         bool
    error:      Optional[str]      = None
    data:       Dict[str, Any]     = field(default_factory=dict)
    # Conventions for `data`:
    #   mme:  {'enbs': [EnbInfo,...], 'ues': [UeInfo,...]}
    #   smf:  {'sessions': [...]}
    #   upf:  {'pfcp_sessions': N, 'rx_bytes': N, 'tx_bytes': N, ...}
    #   amf:  {'gnbs': [...], 'ues': [...]}


# ── backend protocol ─────────────────────────────────────────────────────────

class NfBackend:
    """Abstract: each NF type subclasses and implements poll()."""

    def __init__(self, name: str, kind: str, base_url: str, timeout: float):
        self.name = name
        self.kind = kind
        self.base_url = base_url
        self.timeout = timeout

    async def poll(self, session) -> Snapshot:
        raise NotImplementedError(
            f'{type(self).__name__}.poll() not implemented'
        )

    # Helpers used by concrete backends.
    def _ok(self, **data) -> Snapshot:
        return Snapshot(
            nf_name   = self.name,
            nf_kind   = self.kind,
            timestamp = datetime.now(),
            up        = True,
            data      = data,
        )

    def _down(self, error: str) -> Snapshot:
        return Snapshot(
            nf_name   = self.name,
            nf_kind   = self.kind,
            timestamp = datetime.now(),
            up        = False,
            error     = error,
        )
