# 0L Network RPC Load Balancer Setup

This repository contains the tools to set up and maintain a load balancer for RPC endpoints.

## How it works

The `update_endpoints.py` reads from the `endpoints.txt` each RPC fullnode entry, requests the remote `ledger_version`, and ranks the nodes among the top 3% to skip nodes that are behind.

The passing ranked fullnodes are used to update the `nginx` upstream list for round-robin selection.

## Configuration

Several environment variables can be adjusted to tailor the setup to specific needs:

- `GIT_ORG`: The GitHub organization (default: `0LNetworkCommunity`).
- `GIT_REPO`: The repository name (default: `rpc-load-balancer-v5`). (`IMPORTANT NOTICE for v5:` this was changed in the Makefile)
- `REPO_PATH`: The path to the repository (default: `~/${GIT_REPO}`).
- `RPC_LB_DOMAIN`: The domain for the RPC load balancer (default: `mainnet-rpc.openlibra.space`).
- `RPC_LB_SITE_FILE`: The Nginx site configuration filename (default: `rpc-load-balancer-v5`).

## Usage

1. Clone this repository.
2. `IMPORTANT NOTICE for v5:` Move the repo to `~/rpc-load-balancer-v5`
3. Adjust the environment variables as needed.
4. Run `make install` to set up the load balancer.
5. You can configure a root user cronjob entry to execute `cd ~/rpc-load-balancer-v5 && REPO_PATH=~/rpc-load-balancer-v5 make cron-v5 make cron` every 15 minutes or so.

## Cronjob Notes

Your cron entry should be done as root `sudo crontab -e` while the repo can live elsewhere.

In order for Git to comply, you will need to declare the directory safe:
```
sudo git config --global --add safe.directory /home/nodeuser/rpc-load-balancer-v5
```

You should also configure the GitHub user under root (use your info):
```
sudo git config --global user.email "8675309+someuser@users.noreply.github.com"
sudo git config --global user.name "someuser"
```

Cronjob:
```
# 0L Network RPC Load Balancer Update
*/15 * * * * cd /home/nodeuser/rpc-load-balancer-v5 && REPO_PATH=/home/nodeuser/rpc-load-balancer-v5 make cron-v5 >> cron.log 2>&1
```
