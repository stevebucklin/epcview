"""
Async polling loop.

One asyncio task per NF; each runs a loop that polls every
`refresh_seconds`, parses the response into a Snapshot, and pushes it
into the StateStore. NF backend instances are cached so a long-running
session can reuse connections.
"""

import asyncio
import logging
from typing import Dict, List

import aiohttp

from config import EpcviewConfig, NfConfig
from nfs import NfBackend
from nfs.mme import MmeBackend
from nfs.smf import SmfBackend
from nfs.upf import UpfBackend
from state import StateStore

log = logging.getLogger(__name__)


def _make_backend(nf: NfConfig, timeout: float) -> NfBackend:
    if nf.kind == 'mme':
        return MmeBackend(nf.name, nf.kind, nf.base_url, timeout)
    if nf.kind == 'smf':
        return SmfBackend(nf.name, nf.kind, nf.base_url, timeout)
    if nf.kind == 'upf':
        return UpfBackend(nf.name, nf.kind, nf.base_url, timeout)
    # Future: sgwc, sgwu, amf
    raise NotImplementedError(f'No backend yet for kind={nf.kind}')


class Poller:

    def __init__(self, conf: EpcviewConfig, store: StateStore):
        self._conf  = conf
        self._store = store
        self._tasks: List[asyncio.Task] = []
        self._stop  = asyncio.Event()
        self._session: aiohttp.ClientSession = None

    async def run(self):
        # One shared aiohttp session — connection-pooled, fast.
        connector = aiohttp.TCPConnector(limit=32)
        self._session = aiohttp.ClientSession(connector=connector)

        try:
            backends = []
            for nf in self._conf.nfs:
                try:
                    backends.append(_make_backend(nf, self._conf.globals.http_timeout))
                except NotImplementedError as e:
                    log.warning("Skipping %s: %s", nf.name, e)

            self._tasks = [
                asyncio.create_task(self._poll_loop(b),
                                     name=f'poll-{b.name}')
                for b in backends
            ]
            await self._stop.wait()
        finally:
            for t in self._tasks:
                t.cancel()
            if self._tasks:
                await asyncio.gather(*self._tasks, return_exceptions=True)
            await self._session.close()

    def stop(self):
        self._stop.set()

    async def _poll_loop(self, backend: NfBackend):
        interval = self._conf.globals.refresh_seconds
        while not self._stop.is_set():
            snap = await backend.poll(self._session)
            self._store.update(snap)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass  # interval elapsed, poll again
