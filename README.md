
# RPC Load Balancer Setup

This repository provides tools for automated testing and setting up a dynamic RPC load balancer using `nginx`.

---

## Overview

The `update_endpoints.py` script automates the management of RPC fullnodes by dynamically updating the `nginx` configuration. This ensures only the top-performing nodes are used for proxying.

### How It Works:
1. Reads fullnode entries from `endpoints.txt` and JSON endpoint and combines them.
2. Checks chain ID and fetches remote `ledger_version` to assess node health.
3. Selects the top nodes based on a tolerance within top chain block height.
4. Stages `nginx` with a unique proxy setup for all passing nodes.
5. Tests each node end to end to ensure proper functionality, removing defunct nodes.
6. Updates the `nginx` configuration with the new proxy servers.

---

## Configuration

The setup can be customized using the following environment variables:

| Variable              | Description                                                  | Default                         |
|-----------------------|--------------------------------------------------------------|---------------------------------|
| `GIT_ORG`            | GitHub organization name.                                    | `tududes`                      |
| `GIT_REPO`           | Repository name.                                             | `rpc-load-balancer`            |
| `REPO_PATH`          | Path to the repository.                                      | `~/${GIT_REPO}`                |
| `RPC_LB_DOMAIN`      | Domain for the RPC load balancer.                            | `namada-rpc.tududes.com`       |
| `BALANCER_TOLERANCE` | Maximum difference in ledger height for eligible fullnodes.  | `10`                            |
| `CHAIN_ID`           | Chain ID to validate fullnode compatibility.                 | `namada.5f5de2dd1b88cba30586420` |
| `LOCAL_RPC_PORT`     | Port for local RPC service when applicable.                  | `26657`                        |

---

## Setup Instructions

1. Clone the repository:
   ```bash
   cd $HOME
   git clone https://github.com/tududes/rpc-load-balancer -b namada-mainnet
   cd $HOME/rpc-load-balancer
   ```

2. Configure your environment variables:
   - Edit `.env` to customize the behavior.

3. Install the load balancer:
   ```bash
   apt install make -y
   make install
   ```

4. Test the setup:
   - Verify the `nginx` configuration:
     ```bash
     sudo nginx -t
     ```
   - Reload `nginx`:
     ```bash
     sudo systemctl reload nginx
     ```

5. Automate updates:
   - Add a cron job to periodically update the load balancer:
     ```bash
     # RPC Load Balancer Update
     (crontab -l; echo "*/15 * * * * cd $HOME/rpc-load-balancer && REPO_PATH=$HOME/rpc-load-balancer make cron-nogit >> cron.log 2>&1") | crontab -
     ```

---

## Features

- **Dynamic Updates:** Automatically refresh upstream nodes based on performance and health.
- **Proxy Optimization:** Ensures proper `Host` headers for multi-site compatibility.
- **SSL Ready:** Compatible with Let's Encrypt SSL certificates for secure traffic.
- **High Availability:** Filters out slow or outdated nodes to maintain service quality.
- **Customizable Tolerance:** Adjust ledger height differences to suit your needs.

---

## Example Nginx Configuration

Generated configuration includes only tested RPC fullnodes for proxying:

```nginx
split_clients "${msec}${remote_addr}${remote_port}" $rpc_upstream {
#BEGIN_SPLIT_CLIENTS
	4.17%	"rpc.namada.tududes.com";
	4.17%	"namada.liquify.com";
	4.17%	"namada-rpc.mandragora.io";
	4.17%	"rpc-namada.5elementsnodes.com";
	4.17%	"namada-rpc.sproutstake.space";
	4.17%	"rpc.papadritta.com";
	4.17%	"namada.rpc.decentrio.ventures";
	4.17%	"rpc.namada.stakepool.dev.br";
	4.17%	"rpc.namadascan.io";
	4.17%	"namada-mainnet.rpc.l0vd.com";
	4.17%	"namada.loserboy.xyz";
	4.17%	"namada.itudou.xyz";
	4.17%	"namada-rpc.0xcryptovestor.com";
	4.17%	"namada-rpc.max-02.xyz";
	4.17%	"namada-mainnet-rpc.denodes.xyz";
	4.17%	"namada.rpc.liveraven.net";
	4.17%	"namada-rpc.palamar.io";
	4.17%	"rpc.namada.stakeup.tech";
	4.17%	"rpc.namada.citizenweb3.com";
	4.17%	"lightnode-rpc-mainnet-namada.grandvalleys.com";
	4.17%	"mainnet-namada-rpc.konsortech.xyz";
	4.17%	"namada-rpc.emberstake.xyz";
	4.17%	"rpc-1.namada.nodes.guru";
	*	"rpc-namada.architectnodes.com";
#END_SPLIT_CLIENTS
}

server {
	listen 80;
	server_name namada-rpc.tududes.com;
	return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name namada-rpc.tududes.com;
    resolver 8.8.8.8;

    ssl_certificate     /etc/letsencrypt/live/namada-rpc.tududes.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/namada-rpc.tududes.com/privkey.pem;

    location / {
        # Pass to whichever upstream was chosen above
        proxy_pass https://$rpc_upstream;

        # Retry on error/timeouts
        proxy_intercept_errors on;
        proxy_next_upstream error timeout http_500 http_502 http_503 http_504 http_403 http_404;
        proxy_next_upstream_tries 3;
        proxy_next_upstream_timeout 10s;

        # Timeouts
        proxy_connect_timeout 3s;
        proxy_read_timeout    120s;
        proxy_send_timeout    10s;

        # Pass headers
        proxy_set_header Host           $rpc_upstream;
        proxy_set_header X-Real-IP      $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade        $http_upgrade;
        proxy_set_header Connection     "upgrade";

        # CORS
        proxy_hide_header Access-Control-Allow-Origin;
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Expose-Headers Content-Length;

        if ($request_method = OPTIONS) {
            add_header Access-Control-Allow-Origin   * always;
            add_header Access-Control-Expose-Headers Content-Length;
            return 204;
        }

        proxy_http_version 1.1;
        proxy_ssl_verify off;
    }
}
```

This configuration ensures the best performance by testing nodes.

---

## Troubleshooting

- **Invalid `nginx` Configuration:**
  - Run `sudo nginx -t` to check for syntax errors.
  - Fix reported issues and reload the service using `sudo systemctl reload nginx`.

- **Cron Job Issues:**
  - Verify cron logs (`cron.log`) for errors.
  - Ensure paths and environment variables are correctly set.

- **Node Synchronization Problems:**
  - Ensure nodes listed in `endpoints.txt` are operational.
  - Check JSON endpoint for list of nodes and field used to represent RPC endpoints.
  - Adjust `BALANCER_TOLERANCE` for stricter or looser performance criteria.

---

For additional help, submit issues or feature requests via GitHub!

# DISCLAIMER
This repository serves as a tool to access a more reliable list of RPC endpoints. The code to accomplish this is provided as-is. No guarantees are made regarding the availability or performance of the listed nodes. Use at your own risk.
