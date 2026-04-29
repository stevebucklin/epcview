# epcview — deployment

A self-contained Python TUI that polls Open5GS EPC / 5GC NFs over HTTP
once per second and renders a live unified view. Designed to run on any
host that has TCP reachability to your NF metrics ports — typically a
laptop on the same VLAN as the core, or a jumphost.

## Install

```bash
tar -xzf epcview-0.1.0.tar.gz
cd epcview-0.1.0
sudo ./deploy/install.sh
```

That's it. The installer:

- Apt-installs `python3`, `python3-venv`, `python3-pip` if missing.
- Wipes any previous `/opt/epcview-*` (clean upgrade).
- Stages the source tree under `/opt/epcview-<version>`.
- Builds a venv there and installs `aiohttp` + `PyYAML`.
- Drops a launcher at `/usr/local/bin/epcview` so any user can run
  `epcview` without sudo.
- Drops `epcview-uninstall` at `/usr/local/sbin/`.
- Seeds `/etc/epcview/epcview.yaml` with the bundled default (only if
  not already present — re-installs preserve your edits). The latest
  bundled default is always available as
  `/etc/epcview/epcview.yaml.example`.

The install needs root (writes to `/opt`, `/usr/local`, `/etc`); the
runtime does not — `epcview` runs as the invoking user.

Requires apt-based Linux (Ubuntu / Debian / Mint). On other distros
install `python3`, the venv module, and pip by hand first; the installer
will skip its own apt step.

## Run

```bash
epcview
```

Press Ctrl-C to quit.

## Configure

Two ways, in order of precedence:

1. **Per-user** — drop a YAML at `~/.config/epcview/epcview.yaml`. Use
   when one machine serves several operators with different views.
2. **System default** — edit `/etc/epcview/epcview.yaml`. This is what
   the installer seeded; survives upgrades.

Only the `nfs:` list usually needs your attention. One entry per NF you
want to watch:

```yaml
nfs:
  - name: mme-1
    kind: mme        # mme | smf | upf  (sgwc/sgwu/amf coming)
    host: 172.22.0.50
    port: 9090

  - name: smf-1
    kind: smf
    host: 172.22.0.52
    port: 9090

  - name: upf-1
    kind: upf
    host: 172.22.0.56
    port: 9090
```

`global:` knobs you can leave alone unless something is hurting:

| key                | default | meaning                                 |
| ------------------ | ------: | --------------------------------------- |
| `refresh_seconds`  | `1`     | poll every NF this often                |
| `http_timeout`     | `2`     | mark an NF down after no response in Ns |
| `history_size`     | `2000`  | in-memory event ring buffer length      |
| `history_db`       | `null`  | optional path for persistent history    |

## Uninstall

```bash
sudo epcview-uninstall
```

Removes every `/opt/epcview-*`, the launcher, the uninstaller itself,
`/etc/epcview/`, and the invoking user's `~/.config/epcview/` plus any
`epcview.service` user unit. Other users' per-user configs (if any) are
flagged but not auto-removed — clean those by hand.

## Troubleshooting

**`● down` next to an NF** — the host:port isn't reachable, or the NF
isn't exposing its metrics. Check from the same host with `curl`:

```bash
curl -v http://<host>:9090/metrics       # works for upf, sgwu, sgwc
curl -v http://<host>:9090/enb-info      # mme
curl -v http://<host>:9090/pdu-info      # smf
```

A 400 from `/pdu-info` means the SMF binary predates that endpoint —
upgrade to a build that includes the custom JSON metrics.

**`timeout after 2s`** — the NF is reachable but slow. Bump
`http_timeout` in `global:`.

**Empty Sessions table while MME shows UEs** — UEs that are EMM
registered but have no active PDN won't show on the SMF. Also normal
right after an SMF restart, until UEs re-establish their sessions.

**Mismatched IMSIs between MME and SMF** — real divergence in core
state. Worth investigating in your EPC, not an epcview issue.

## Optional: systemd --user service

If you want it humming in the background as you log in. Drop in
`~/.config/systemd/user/epcview.service`:

```ini
[Unit]
Description=epcview — Open5GS EPC/5GC live dashboard
After=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/epcview
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now epcview
journalctl --user -u epcview -f
```

Mostly useful with `history_db:` set in the YAML so the interactive
view starts with context.
