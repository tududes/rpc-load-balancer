
# RPC Load Balancer Setup

This repository provides tools for automated testing and setting up a dynamic RPC load balancer using `nginx`.

---

## Overview

The Makefile and accompanying scripts automate the testing of RPC fullnodes by dynamically updating the `nginx` configuration. This ensures only the top-performing nodes are used for proxying.

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
| `RPC_LB_DOMAIN`      | Domain for the RPC load balancer.                            | `osmosis-rpc.tududes.com`       |
| `BALANCER_TOLERANCE` | Maximum difference in ledger height for eligible fullnodes.  | `30`                            |
| `CHAIN_ID`           | Chain ID to validate fullnode compatibility.                 | `osmosis-1` |
| `LOCAL_RPC_PORT`     | Port for local RPC service when applicable.                  | `26657`                        |

---

## Setup Instructions

1. Clone the repository:
   ```bash
   cd $HOME
   git clone https://github.com/tududes/rpc-load-balancer -b osmosis-mainnet
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
split_clients "${msec}${remote_addr}${remote_port}" $osmosis_rpc_upstream {
#BEGIN_SPLIT_CLIENTS
	1.69%	"141.94.73.39:38657";
	1.69%	"65.109.94.26:36608";
	1.69%	"46.4.37.188:26657";
	1.69%	"78.46.108.162:26657";
	1.69%	"178.63.130.196:26657";
	1.69%	"65.108.141.109:56557";
	1.69%	"65.109.125.189:36657";
	1.69%	"65.109.118.35:36608";
	1.69%	"65.109.49.164:36608";
	1.69%	"65.109.82.144:26657";
	1.69%	"188.40.71.173:12557";
	1.69%	"142.132.130.120:26659";
	1.69%	"62.210.93.68:26657";
	1.69%	"65.108.137.22:26657";
	1.69%	"219.100.163.46:26657";
	1.69%	"65.109.33.52:36608";
	1.69%	"208.77.197.84:26657";
	1.69%	"213.239.213.157:26657";
	1.69%	"164.92.91.142:26657";
	1.69%	"164.92.118.66:26657";
	1.69%	"54.181.2.243:26657";
	1.69%	"176.9.139.74:46657";
	1.69%	"5.9.123.14:56657";
	1.69%	"176.9.158.219:41057";
	1.69%	"51.91.118.105:12557";
	1.69%	"5.9.85.89:21657";
	1.69%	"65.109.27.253:36608";
	1.69%	"95.217.150.200:56657";
	1.69%	"148.251.9.235:36657";
	1.69%	"95.216.38.96:36657";
	1.69%	"65.109.93.152:38657";
	1.69%	"65.108.204.178:26657";
	1.69%	"65.109.50.183:26657";
	1.69%	"167.99.253.250:26657";
	1.69%	"65.108.12.253:26657";
	1.69%	"165.232.78.47:26657";
	1.69%	"73.40.192.207:42657";
	1.69%	"162.55.92.114:2002";
	1.69%	"178.63.142.152:26657";
	1.69%	"65.108.121.190:2002";
	1.69%	"64.176.38.31:26657";
	1.69%	"64.176.58.33:26657";
	1.69%	"66.172.36.140:36657";
	1.69%	"141.95.172.102:36657";
	1.69%	"88.99.149.170:18657";
	1.69%	"95.217.150.201:56657";
	1.69%	"5.9.123.76:56657";
	1.69%	"90.188.5.27:47157";
	1.69%	"185.162.251.239:26661";
	1.69%	"64.23.163.140:26657";
	1.69%	"65.21.233.188:12557";
	1.69%	"136.243.72.217:29657";
	1.69%	"35.185.177.175:26657";
	1.69%	"35.197.138.188:26657";
	1.69%	"143.110.231.94:26657";
	1.69%	"176.9.66.48:56657";
	1.69%	"135.181.112.189:12957";
	1.69%	"51.91.212.18:20457";
	*	"77.238.248.110:26657";
#END_SPLIT_CLIENTS
}

server {
	listen 80;
	server_name osmosis-rpc.tududes.com;
	return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name osmosis-rpc.tududes.com;
    resolver 8.8.8.8;

    ssl_certificate     /etc/letsencrypt/live/osmosis-rpc.tududes.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/osmosis-rpc.tududes.com/privkey.pem;

    location / {
        # Pass to whichever upstream was chosen above
        proxy_pass http://$osmosis_rpc_upstream;

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
        proxy_set_header Host           $osmosis_rpc_upstream;
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
