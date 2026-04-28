"""
Minimal CLI for the first iteration — terminal table that auto-refreshes.

This is the simplest viable view: NF status header + eNB table + UE
table, redrawn every refresh tick. Replaced by the full prompt_toolkit
split-screen UI in the next iteration once the polling loop is shaken
out.
"""

import asyncio
from datetime import datetime

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
    print(f'  {_CYAN}epcview{_RESET}  ({now})  '
          f'— Ctrl-C to quit\n')

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


async def render_loop(refresh_seconds: float, stop: asyncio.Event):
    """Redraw the screen every `refresh_seconds`."""
    while not stop.is_set():
        _draw()
        try:
            await asyncio.wait_for(stop.wait(), timeout=refresh_seconds)
        except asyncio.TimeoutError:
            pass
