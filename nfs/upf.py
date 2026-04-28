"""
UPF backend — scrapes the Prometheus /metrics endpoint.

Upstream open5gs UPF exposes only Prometheus counters/gauges (no custom
JSON listing of PDU sessions or per-UE byte tallies — yet). We pull the
text-format scrape, parse the handful of metrics we care about, and
surface them as a UpfStats record in the snapshot.

Live shape verified 2026-04-28 against open5gs UPF v2.7.7-6-g288f1ca:

  fivegs_upffunction_upf_sessionnbr            <gauge>   active PFCP sessions
  pfcp_peers_active                            <gauge>   connected SMFs
  fivegs_upffunction_upf_qosflows{dnn="..."}   <gauge>   QoS flows per DNN/APN
  fivegs_ep_n3_gtp_indatapktn3upf              <counter> N3 ingress packets
  fivegs_ep_n3_gtp_outdatapktn3upf             <counter> N3 egress packets
  fivegs_upffunction_sm_n4sessionestabreq      <counter> N4 estab attempts
  fivegs_upffunction_sm_n4sessionestabfail     <counter> N4 estab failures
  fivegs_upffunction_sm_n4sessionreport        <counter> N4 usage reports issued
  fivegs_upffunction_sm_n4sessionreportsucc    <counter> N4 usage reports acked
  process_resident_memory_bytes                <gauge>   RSS
  process_open_fds                             <gauge>   open file descriptors

Same metric layout works for SGW-U (the names are 5G-flavoured but the
4G data path uses the identical N3/PFCP plumbing). When SGW-U support
lands we'll alias this backend.
"""

import asyncio
import re
from typing import Dict, Tuple

from . import NfBackend, Snapshot, UpfStats


# Each non-comment, non-blank line is:
#   metric_name{label="v",label="v"} <number>     (labels optional)
_LINE_RE = re.compile(
    r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([-+]?[0-9.eE+]+|NaN|\+Inf|-Inf)\s*$'
)
_LABEL_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


def _parse_prom(text: str) -> Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float]:
    """Tiny Prometheus text-format parser — name+label-set → value."""
    out: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = _LINE_RE.match(line)
        if not m:
            continue
        name, label_blob, value = m.groups()
        labels = ()
        if label_blob:
            labels = tuple(sorted(_LABEL_RE.findall(label_blob)))
        try:
            num = float(value)
        except ValueError:
            continue
        out[(name, labels)] = num
    return out


def _g(metrics, name: str) -> float:
    """Single unlabelled metric value, 0 if absent."""
    return metrics.get((name, ()), 0)


class UpfBackend(NfBackend):

    async def poll(self, session) -> Snapshot:
        timeout = self.timeout
        try:
            async with session.get(
                f'{self.base_url}/metrics',
                timeout=timeout,
            ) as r:
                r.raise_for_status()
                text = await r.text()
        except asyncio.TimeoutError:
            return self._down(f'timeout after {timeout:g}s')
        except Exception as e:  # noqa: BLE001
            return self._down(str(e))

        m = _parse_prom(text)

        qos_by_dnn: Dict[str, int] = {}
        for (name, labels), val in m.items():
            if name == 'fivegs_upffunction_upf_qosflows':
                dnn = dict(labels).get('dnn', '?')
                qos_by_dnn[dnn] = int(val)

        stats = UpfStats(
            upf_name               = self.name,
            sessions_active        = int(_g(m, 'fivegs_upffunction_upf_sessionnbr')),
            pfcp_peers_active      = int(_g(m, 'pfcp_peers_active')),
            qos_flows_by_dnn       = qos_by_dnn,
            gtp_in_packets         = int(_g(m, 'fivegs_ep_n3_gtp_indatapktn3upf')),
            gtp_out_packets        = int(_g(m, 'fivegs_ep_n3_gtp_outdatapktn3upf')),
            n4_estab_req           = int(_g(m, 'fivegs_upffunction_sm_n4sessionestabreq')),
            n4_estab_fail          = int(_g(m, 'fivegs_upffunction_sm_n4sessionestabfail')),
            n4_session_report      = int(_g(m, 'fivegs_upffunction_sm_n4sessionreport')),
            n4_session_report_succ = int(_g(m, 'fivegs_upffunction_sm_n4sessionreportsucc')),
            rss_bytes              = int(_g(m, 'process_resident_memory_bytes')),
            open_fds               = int(_g(m, 'process_open_fds')),
            raw                    = {},
        )

        return self._ok(stats=stats)
