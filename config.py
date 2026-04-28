"""
epcview configuration loader.

Loads epcview.yaml into typed dataclasses. Search order for the config file:
    1. --config <path>
    2. ./epcview.yaml
    3. ~/.config/epcview/epcview.yaml
    4. /etc/epcview/epcview.yaml
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml


@dataclass
class NfConfig:
    name: str
    kind: str           # 'mme' / 'smf' / 'upf' / 'sgwc' / 'sgwu' / 'amf' / 'nrf'
    host: str
    port: int = 9090

    @property
    def base_url(self) -> str:
        return f'http://{self.host}:{self.port}'


@dataclass
class NrfConfig:
    host: str
    port: int
    discover_kinds: List[str] = field(default_factory=lambda: [
        'amf', 'smf', 'upf', 'ausf', 'udm', 'udr', 'pcf',
    ])


@dataclass
class GlobalConfig:
    refresh_seconds: float = 1.0
    http_timeout:    float = 2.0
    history_size:    int   = 2000
    history_db:      Optional[str] = None


@dataclass
class EpcviewConfig:
    globals: GlobalConfig
    nfs:     List[NfConfig] = field(default_factory=list)
    nrf:     Optional[NrfConfig] = None


def _default_path() -> str:
    candidates = [
        './epcview.yaml',
        os.path.expanduser('~/.config/epcview/epcview.yaml'),
        '/etc/epcview/epcview.yaml',
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return './epcview.yaml'


def load(path: Optional[str] = None) -> EpcviewConfig:
    if path is None:
        path = _default_path()
    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    g = raw.get('global', {}) or {}
    glb = GlobalConfig(
        refresh_seconds = float(g.get('refresh_seconds', 1.0)),
        http_timeout    = float(g.get('http_timeout', 2.0)),
        history_size    = int  (g.get('history_size', 2000)),
        history_db      = (os.path.expanduser(g['history_db'])
                            if g.get('history_db') else None),
    )

    nfs = [
        NfConfig(name=n['name'], kind=n['kind'].lower(),
                  host=n['host'], port=int(n.get('port', 9090)))
        for n in raw.get('nfs', []) or []
    ]

    nrf = None
    if raw.get('nrf'):
        n = raw['nrf']
        nrf = NrfConfig(
            host = n['host'],
            port = int(n.get('port', 7777)),
            discover_kinds = [k.lower() for k in n.get('discover_kinds', [
                'amf', 'smf', 'upf', 'ausf', 'udm', 'udr', 'pcf',
            ])],
        )

    return EpcviewConfig(globals=glb, nfs=nfs, nrf=nrf)
