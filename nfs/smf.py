"""
SMF backend — polls /pdu-info on the metrics HTTP server.

Live JSON shape verified 2026-04-28 against open5gs SMF
(post-08f4ffb17 build with /pdu-info enabled):

  /pdu-info →
    {
      "items": [
        {
          "supi": "234880000004747",
          "pdu": [
            {
              "ebi":   5,                      # 4G bearer ID (matches default qfi on 5G)
              "apn":   "ims",                  # APN (4G) / DNN (5G)
              "ipv4":  "10.10.0.2",
              "ipv6":  "...",                  # optional, only when allocated
              "snssai": {"sst": 0, "sd": "000000"},
              "qos_flows": [{"ebi": 5, "qci": 5}, ...],
              "pdu_state": "active"|"unknown"|...
            }, ...
          ],
          "ue_activity": "active"|"unknown"|...
        }, ...
      ],
      "pager": {"page": 0, "page_size": 100, "count": N}
    }

Note: SMF does not expose a UE-level record beyond what's in /pdu-info,
so we flatten one record per (supi, ebi) into a session list. The /metrics
Prometheus endpoint is left for a future iteration if we need rate
counters — for now /pdu-info gives us the live session inventory.
"""

import asyncio

from . import NfBackend, PduSessionInfo, Snapshot


def _parse_session(supi: str, item: dict, smf_name: str) -> PduSessionInfo:
    snssai = item.get('snssai') or {}
    return PduSessionInfo(
        supi       = supi,
        ebi        = int(item.get('ebi', 0) or 0),
        apn        = str(item.get('apn', '')),
        ipv4       = item.get('ipv4') or None,
        ipv6       = item.get('ipv6') or None,
        snssai_sst = (int(snssai['sst']) if 'sst' in snssai else None),
        snssai_sd  = (str(snssai['sd'])  if 'sd'  in snssai else None),
        qos_flows  = list(item.get('qos_flows', []) or []),
        pdu_state  = str(item.get('pdu_state', 'unknown')),
        smf_name   = smf_name,
        raw        = item,
    )


class SmfBackend(NfBackend):

    async def poll(self, session) -> Snapshot:
        timeout = self.timeout
        try:
            async with session.get(
                f'{self.base_url}/pdu-info',
                timeout=timeout,
            ) as r:
                r.raise_for_status()
                pdu_json = await r.json()
        except asyncio.TimeoutError:
            return self._down(f'timeout after {timeout:g}s')
        except Exception as e:  # noqa: BLE001 — surface any HTTP/parse error
            return self._down(str(e))

        smf_name = self.name  # SMF JSON doesn't carry a self-name; use config label
        sessions = []
        for ue in pdu_json.get('items', []) or []:
            supi = str(ue.get('supi', ''))
            for pdu in ue.get('pdu', []) or []:
                sessions.append(_parse_session(supi, pdu, smf_name))

        return self._ok(sessions=sessions, smf_name=smf_name)
