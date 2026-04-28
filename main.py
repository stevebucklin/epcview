"""
epcview — entry point.

Usage:
    python3 main.py [--config <path>]
"""

import argparse
import asyncio
import sys

import config as cfg
import version


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

    # The poller, state store, and CLI loop live in upcoming files. For the
    # scaffolding milestone we just verify config loads and print the NF list.
    print('  Configured NFs:')
    for nf in conf.nfs:
        print(f'    {nf.name:<10} {nf.kind:<6} {nf.base_url}')
    print()
    print('  (Polling/UI not yet implemented — scaffold only.)')


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
