# epcview

Live terminal dashboard for an Open5GS EPC / 5GC deployment.

Polls each Network Function's HTTP metrics + custom JSON endpoints
(`/enb-info`, `/ue-info`, `/pdu-info`, `/gnb-info`, `/metrics`) once
per second and renders a unified view of:

- **eNBs and gNBs** — peer state, supported TACs, UEs per cell
- **UEs** — IMSI, attach state, serving cell, APN, AMBR, bearer/QFI
  status, with a **per-UE drill-down** that correlates MME ↔ SMF ↔ UPF
- **Sessions** — APN/DNN, EBI/QFI, throughput, tunnel state
- **History** — UE attach/detach, session create/release, NF up/down

Manual NF list for 4G; optional NRF discovery for 5G.

## Quick start

```bash
pip install -r requirements.txt
cp epcview.yaml ~/.config/epcview/epcview.yaml   # edit hosts/ports
python3 main.py
```

## Status

Scaffolding only at present. See task list in development notes.
