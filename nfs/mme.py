"""
MME backend — polls /enb-info and /ue-info on the metrics HTTP server.

Live JSON shapes verified 2026-04-28 against open5gs MME v2.7.7-6-g288f1ca:

  /enb-info →
    {
      "items": [
        {
          "enb_id": 2,
          "plmn": "99942",
          "network": {"mme_name": "..."},
          "s1": {"setup_success": true, "sctp": {"peer": "[ip]:port", ...}},
          "supported_ta_list": [{"tac": "0001", "plmn": "99942"}, ...],
          "num_connected_ues": 0
        }, ...
      ],
      "pager": {"page": 0, "page_size": 100, "count": N}
    }

  /ue-info →
    {
      "items": [
        {
          "supi": "208090066210704",
          "domain": "EPS",
          "rat": "E-UTRA",
          "cm_state": "idle"|"connected",
          "enb": {"ostream_id": N, ...                              # IDLE: only ostream_id
                  "enb_id": N, "cell_id": N,                         # CONNECTED: also these
                  "mme_ue_ngap_id": N, "ran_ue_ngap_id": N},
          "location": {"tai": {"plmn": "...", "tac_hex": "0001", "tac": 1}},
          "ambr": {"downlink": bps, "uplink": bps},
          "pdn": [{"apn": "...", "qci": N, "ebi": N,
                   "bearer_count": N, "pdu_state": "active"|...}, ...],
          "pdn_count": N
        }, ...
      ],
      "pager": {...}
    }
"""

import asyncio

from . import NfBackend, EnbInfo, UeInfo, Snapshot


def _strip_brackets(s: str) -> str:
    """SCTP peer comes back as '[host]:port' even for IPv4 — clean it."""
    if s.startswith('[') and ']' in s:
        host, _, port = s[1:].partition(']:')
        return f'{host}:{port}' if port else host
    return s


def _parse_enb(item: dict, mme_name: str) -> EnbInfo:
    s1 = item.get('s1', {}) or {}
    sctp = s1.get('sctp', {}) or {}
    tas = item.get('supported_ta_list', []) or []
    return EnbInfo(
        enb_id        = int(item.get('enb_id', 0)),
        plmn          = str(item.get('plmn', '')),
        sctp_peer     = _strip_brackets(sctp.get('peer', '')),
        s1_setup_ok   = bool(s1.get('setup_success', False)),
        supported_tacs = [str(t.get('tac', '')) for t in tas],
        num_conn_ues  = int(item.get('num_connected_ues', 0)),
        mme_name      = mme_name,
        raw           = item,
    )


def _parse_ue(item: dict, mme_name: str) -> UeInfo:
    enb = item.get('enb', {}) or {}
    loc = (item.get('location', {}) or {}).get('tai', {}) or {}
    ambr = item.get('ambr', {}) or {}
    return UeInfo(
        supi          = str(item.get('supi', '')),
        domain        = str(item.get('domain', '')),
        rat           = str(item.get('rat', '')),
        cm_state      = str(item.get('cm_state', '')),
        serving_enb   = enb.get('enb_id'),    # None when idle
        serving_cell  = enb.get('cell_id'),   # None when idle
        tai_plmn      = str(loc.get('plmn', '')),
        tai_tac       = int(loc.get('tac', 0) or 0),
        ambr_dl_bps   = int(ambr.get('downlink', 0) or 0),
        ambr_ul_bps   = int(ambr.get('uplink', 0) or 0),
        pdns          = list(item.get('pdn', []) or []),
        mme_name      = mme_name,
        raw           = item,
    )


class MmeBackend(NfBackend):

    async def poll(self, session) -> Snapshot:
        timeout = self.timeout
        try:
            async with session.get(
                f'{self.base_url}/enb-info',
                timeout=timeout,
            ) as r1:
                r1.raise_for_status()
                enb_json = await r1.json()
            async with session.get(
                f'{self.base_url}/ue-info',
                timeout=timeout,
            ) as r2:
                r2.raise_for_status()
                ue_json = await r2.json()
        except asyncio.TimeoutError:
            return self._down(f'timeout after {timeout:g}s')
        except Exception as e:  # noqa: BLE001 — surface any HTTP/parse error
            return self._down(str(e))

        # Both endpoints carry mme_name nested in each eNB; pull from there
        # for snapshot-level attribution. UE items don't carry it directly,
        # so we use the first eNB's value (or fall back to the NF name).
        mme_name = self.name
        first_enb = (enb_json.get('items') or [{}])[0]
        nested = (first_enb.get('network') or {}).get('mme_name')
        if nested:
            mme_name = nested

        enbs = [_parse_enb(item, mme_name) for item in enb_json.get('items', [])]
        ues  = [_parse_ue(item,  mme_name) for item in ue_json.get('items', [])]

        return self._ok(enbs=enbs, ues=ues, mme_name=mme_name)
