"""
epcview — entry point.

Usage:
    python3 main.py [--config <path>]
"""

import argparse
import asyncio
import signal
import sys

import config as cfg
import version
from cli import render_loop
from poller import Poller
from state import STORE


def _banner(conf: cfg.EpcviewConfig):
    print(f'\n  epcview — Open5GS EPC/5GC dashboard')
    print(f'  {version.__author__} — Version {version.__version__}'
          f' — {version.__release__}')
    print(f'  Polling {len(conf.nfs)} NF(s) every {conf.globals.refresh_seconds:g}s'
          f'  (timeout {conf.globals.http_timeout:g}s)')
    if conf.nrf is not None:
        print(f'  NRF discovery: {conf.nrf.host}:{conf.nrf.port}')
    print()


async def _main(config_path: str):
    conf = cfg.load(config_path)
    _banner(conf)

    if not conf.nfs:
        print('  ! No NFs configured. Edit epcview.yaml.')
        return

    stop = asyncio.Event()

    # Ctrl-C handler — sets stop event, lets tasks unwind cleanly
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    poller = Poller(conf, STORE)

    poller_task  = asyncio.create_task(poller.run(),       name='poller')
    render_task  = asyncio.create_task(
        render_loop(conf.globals.refresh_seconds, stop),
        name='render'
    )

    await stop.wait()

    poller.stop()
    await asyncio.gather(poller_task, render_task, return_exceptions=True)
    print('\n  Stopped.\n')


def parse_args():
    p = argparse.ArgumentParser(description='epcview — EPC/5GC live dashboard')
    p.add_argument('--config', default=None,
                   help='Path to epcview.yaml (default: search '
                        './epcview.yaml → ~/.config/epcview/epcview.yaml '
                        '→ /etc/epcview/epcview.yaml)')
    return p.parse_args()


if __name__ == '__main__':
    args = parse_args()
    try:
        asyncio.run(_main(args.config))
    except KeyboardInterrupt:
        pass
    sys.exit(0)
