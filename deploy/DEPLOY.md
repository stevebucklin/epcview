# epcview — deployment

A self-contained Python TUI that polls Open5GS EPC / 5GC NFs over HTTP
once per second and renders a live unified view. Designed to run on any
host that has TCP reachability to your NF metrics ports — typically a
laptop on the same VLAN as the core, or a jumphost.

This document covers a fresh install on a Linux laptop / workstation.
macOS works the same way; Windows via WSL2.

## 1. Requirements

- Python 3.8+ (3.10 or newer recommended)
- `pip` and the `venv` module
- TCP reachability from the host to every NF's metrics port (default
  9090) — verify with `curl -sf http://<nf>:9090/metrics` or
  `/enb-info`/`/pdu-info` before bothering with epcview

That's the whole list. epcview pulls in two pure-Python deps
(`aiohttp`, `PyYAML`) and uses no native libraries.

## 2. Install

Unpack the tarball wherever you keep tooling. `~/opt/epcview` works
well — the runtime tree is self-contained and doesn't require root.

```bash
mkdir -p ~/opt && cd ~/opt
tar -xzf /path/to/epcview-0.1.0.tar.gz
cd epcview-0.1.0
```

Create a virtualenv and install dependencies into it. Keeping deps out
of system site-packages avoids version churn the next time you upgrade
the OS.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

Quick smoke test (no NFs configured yet — should just print the banner
and exit):

```bash
python3 main.py
```

You should see:

```
  epcview — Open5GS EPC/5GC dashboard
  Steve Bucklin — Version 0.1.0 — 28 April 2026
  Polling 0 NF(s) every 1s  (timeout 2s)

  ! No NFs configured. Edit epcview.yaml.
```

If the banner shows but you get import errors, the venv didn't activate
— re-run `. .venv/bin/activate` and re-install.

## 3. Configure

The default config search order is:

1. `--config <path>`  (CLI flag, overrides everything)
2. `./epcview.yaml`   (the bundled default)
3. `~/.config/epcview/epcview.yaml`
4. `/etc/epcview/epcview.yaml`

Per-user is the cleanest pattern on a laptop:

```bash
mkdir -p ~/.config/epcview
cp epcview.yaml ~/.config/epcview/epcview.yaml
```

Edit the file — only the `nfs:` list needs your attention. One entry
per NF you want to watch:

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

## 4. Run

From the install directory, with the venv active:

```bash
python3 main.py
```

For convenience, drop a small launcher into `~/.local/bin`:

```bash
cat > ~/.local/bin/epcview <<'EOF'
#!/usr/bin/env bash
set -e
EPCVIEW_DIR="$HOME/opt/epcview-0.1.0"
exec "$EPCVIEW_DIR/.venv/bin/python3" "$EPCVIEW_DIR/main.py" "$@"
EOF
chmod +x ~/.local/bin/epcview
```

You can then run `epcview` from anywhere. `Ctrl-C` exits cleanly.

## 5. Optional: run as a systemd --user service

Useful if you want it humming in a tmux pane the moment you log in.

```ini
# ~/.config/systemd/user/epcview.service
[Unit]
Description=epcview — Open5GS EPC/5GC live dashboard
After=network-online.target

[Service]
Type=simple
ExecStart=%h/.local/bin/epcview
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now epcview
journalctl --user -u epcview -f
```

The service is mostly useful as a "always on" background poller that
populates an on-disk history (`history_db:` in the YAML) so the
interactive view starts with context. Foreground use from a terminal is
the usual mode.

## 6. Troubleshooting

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
registered but have no active PDN won't show on the SMF. This is also
normal right after an SMF restart until the UEs re-establish their
sessions.

**Mismatched IMSIs between MME and SMF** — real divergence in core
state. Worth investigating in your EPC, not an epcview issue.

## 7. Uninstall

```bash
rm -rf ~/opt/epcview-*
rm -rf ~/.config/epcview
rm -f  ~/.local/bin/epcview
systemctl --user disable --now epcview 2>/dev/null
rm -f  ~/.config/systemd/user/epcview.service
```
