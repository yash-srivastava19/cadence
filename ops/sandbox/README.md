# Hosted sandbox

What `compute: cadence` in the GitHub Action talks to. The run, and the
customer's model key, stay on their runner. Only candidates come here, and
each one is measured in a fresh container with no network.

```text
runner: cadence run ──CADENCE_SANDBOX (curl)──▶ HTTPS ──▶ server.py ──▶ docker run -i cadence-sandbox
```

## Set up a box

On an Ubuntu machine with Docker, Python 3 and Tailscale:

```bash
docker build -t cadence-sandbox --build-arg CADENCE_REF=main ops/sandbox
sudo mkdir -p /etc/cadence && openssl rand -hex 24 | sudo tee /etc/cadence/tokens
python3 ops/sandbox/server.py 8787 &          # localhost only
sudo tailscale funnel --bg 8787               # public HTTPS on the box's ts.net name
```

The URL is `https://<box>.<tailnet>.ts.net/run`. Give a customer one line
from `/etc/cadence/tokens` as their `CADENCE_TOKEN` secret.

Rebuild the image with the same `CADENCE_REF` the customers' action uses, so
both sides run the same cadence.
