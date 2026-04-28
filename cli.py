"""
Minimal CLI for the first iteration — terminal table that auto-refreshes.

This is the simplest viable view: NF status header + eNB table + UE
table, redrawn every refresh tick. Replaced by the full prompt_toolkit
split-screen UI in the next iteration once the polling loop is shaken
out.
"""

import asyncio
from datetime import datetime

import version
from state import STORE


_ANSI_CLEAR = '\033[2J\033[H'
_DIM     = '\033[2m'
_RESET   = '\033[0m'
_GREEN   = '\033[92m'
_YELLOW  = '\033[33m'
_RED     = '\033[91;1m'
_CYAN    = '\033[96;1m'


def _draw():
    print(_ANSI_CLEAR, end='')
    now = datetime.now().strftime('%H:%M:%S')
    print(f'  {_CYAN}epcview{_RESET} v{version.__version__}  '
          f'— Open5GS EPC/5GC live dashboard')
    print(f'  {_DIM}{version.__author__} — {version.__release__}'
          f'   ({now})   Ctrl-C to quit{_RESET}\n')

    # ── NF status row ──
    print(f'  {"NF":<22} {"KIND":<6} {"STATUS":<10} {"DETAIL"}')
    print(f'  {"--":<22} {"----":<6} {"------":<10} {"------"}')
    for snap in sorted(STORE.all(), key=lambda s: s.nf_name):
        if snap.up:
            status = f'{_GREEN}● up{_RESET}    '
            detail = ''
            if snap.nf_kind == 'mme':
                e = len(snap.data.get('enbs', []))
                u = len(snap.data.get('ues', []))
                detail = f'{e} eNB(s)  {u} UE(s)  ({snap.data.get("mme_name","")})'
            elif snap.nf_kind == 'smf':
                sess = snap.data.get('sessions', [])
                ues = len({s.supi for s in sess})
                detail = f'{len(sess)} session(s)  {ues} UE(s)'
            elif snap.nf_kind == 'upf':
                st = snap.data.get('stats')
                if st is not None:
                    detail = (f'{st.sessions_active} PFCP sess  '
                              f'{st.pfcp_peers_active} SMF peer(s)  '
                              f'in/out {st.gtp_in_packets}/{st.gtp_out_packets} pkt')
        else:
            status = f'{_RED}● down{_RESET}  '
            detail = snap.error or ''
        ts = snap.timestamp.strftime('%H:%M:%S')
        print(f'  {snap.nf_name:<22} {snap.nf_kind:<6} {status} {_DIM}{ts}{_RESET}  {detail}')
    print()

    # ── eNB table ──
    enbs = sorted(STORE.all_enbs(), key=lambda e: e.enb_id)
    print(f'  {_CYAN}eNBs{_RESET} ({len(enbs)})')
    if enbs:
        print(f'    {"ID":>6}  {"PLMN":<6}  {"SCTP peer":<24}  '
              f'{"S1":<5}  {"TACs":<8}  {"UEs":>3}  {"MME"}')
        print(f'    {"--":>6}  {"----":<6}  {"---------":<24}  '
              f'{"--":<5}  {"----":<8}  {"---":>3}  {"---"}')
        for e in enbs:
            s1 = (f'{_GREEN}OK{_RESET}   ' if e.s1_setup_ok
                  else f'{_RED}FAIL{_RESET} ')
            tacs = ','.join(e.supported_tacs) or '-'
            print(f'    {e.enb_id:>6}  {e.plmn:<6}  {e.sctp_peer:<24}  '
                  f'{s1}  {tacs:<8}  {e.num_conn_ues:>3}  '
                  f'{_DIM}{e.mme_name}{_RESET}')
    print()

    # ── UE table ──
    ues = sorted(STORE.all_ues(), key=lambda u: u.supi)
    print(f'  {_CYAN}UEs{_RESET} ({len(ues)})')
    if ues:
        print(f'    {"SUPI/IMSI":<17}  {"DOMAIN":<6}  {"STATE":<10}  '
              f'{"ENB":>5}  {"TAI":<14}  {"AMBR↓/↑":<14}  {"APNs"}')
        print(f'    {"---------":<17}  {"------":<6}  {"-----":<10}  '
              f'{"---":>5}  {"---":<14}  {"-------":<14}  {"----"}')
        for u in ues:
            state_col = (_GREEN if u.cm_state == 'connected'
                         else _YELLOW if u.cm_state == 'idle' else _DIM)
            enb = str(u.serving_enb) if u.serving_enb is not None else '-'
            tai = f'{u.tai_plmn}/{u.tai_tac:04x}'
            ambr = f'{u.ambr_dl_bps//10**6}/{u.ambr_ul_bps//10**6} M'
            apns = ','.join(p.get('apn','?') for p in u.pdns) or '-'
            print(f'    {u.supi:<17}  {u.domain:<6}  '
                  f'{state_col}{u.cm_state:<10}{_RESET}  '
                  f'{enb:>5}  {tai:<14}  {ambr:<14}  {apns}')
    print()

    # ── PDU/PDN session table (SMF) ──
    sessions = sorted(STORE.all_sessions(), key=lambda s: (s.supi, s.ebi))
    print(f'  {_CYAN}Sessions{_RESET} ({len(sessions)})')
    if sessions:
        print(f'    {"SUPI":<17}  {"EBI":>3}  {"APN/DNN":<14}  '
              f'{"IPv4":<15}  {"S-NSSAI":<10}  {"QCI/5QI":<7}  {"STATE":<8}  {"SMF"}')
        print(f'    {"----":<17}  {"---":>3}  {"-------":<14}  '
              f'{"----":<15}  {"-------":<10}  {"-------":<7}  {"-----":<8}  {"---"}')
        for s in sessions:
            ipv4 = s.ipv4 or '-'
            if s.snssai_sst is not None:
                snssai = f'{s.snssai_sst}/{s.snssai_sd or "-"}'
            else:
                snssai = '-'
            qcis = ','.join(str(q.get('qci', q.get('5qi', '?')))
                             for q in s.qos_flows) or '-'
            state_col = (_GREEN if s.pdu_state == 'active'
                         else _YELLOW if s.pdu_state == 'unknown' else _DIM)
            print(f'    {s.supi:<17}  {s.ebi:>3}  {s.apn:<14}  '
                  f'{ipv4:<15}  {snssai:<10}  {qcis:<7}  '
                  f'{state_col}{s.pdu_state:<8}{_RESET}  '
                  f'{_DIM}{s.smf_name}{_RESET}')
    print()

    # ── UPF stats ──
    upfs = sorted(STORE.all_upf_stats(), key=lambda s: s.upf_name)
    if upfs:
        print(f'  {_CYAN}UPFs{_RESET} ({len(upfs)})')
        print(f'    {"NAME":<10}  {"SESS":>4}  {"PEERS":>5}  {"GTP IN":>10}  '
              f'{"GTP OUT":>10}  {"N4 ESTAB":>9}  {"N4 FAIL":>7}  '
              f'{"RSS":>7}  {"FDS":>4}  {"QOS BY DNN"}')
        print(f'    {"----":<10}  {"----":>4}  {"-----":>5}  {"------":>10}  '
              f'{"-------":>10}  {"--------":>9}  {"-------":>7}  '
              f'{"---":>7}  {"---":>4}  {"----------"}')
        for st in upfs:
            qos = ', '.join(f'{d}={n}' for d, n in sorted(st.qos_flows_by_dnn.items())) or '-'
            rss_mb = st.rss_bytes // (1024 * 1024)
            print(f'    {st.upf_name:<10}  {st.sessions_active:>4}  '
                  f'{st.pfcp_peers_active:>5}  {st.gtp_in_packets:>10}  '
                  f'{st.gtp_out_packets:>10}  {st.n4_estab_req:>9}  '
                  f'{st.n4_estab_fail:>7}  {rss_mb:>5}MB  '
                  f'{st.open_fds:>4}  {qos}')
        print()


async def render_loop(refresh_seconds: float, stop: asyncio.Event):
    """Redraw the screen every `refresh_seconds`."""
    while not stop.is_set():
        _draw()
        try:
            await asyncio.wait_for(stop.wait(), timeout=refresh_seconds)
        except asyncio.TimeoutError:
            pass
