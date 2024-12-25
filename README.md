
# RPC Load Balancer Setup

This repository provides tools for automated testing and setting up a dynamic RPC load balancer using `nginx`.

---

## Overview

The `update_endpoints.py` script automates the management of RPC fullnodes by dynamically updating the `nginx` configuration. This ensures only the top-performing nodes are used for proxying.

### How It Works:
1. Reads fullnode entries from `endpoints.txt`.
2. Fetches remote `ledger_version` to assess node health.
3. Selects the top nodes based on a tolerance within top chain block height.
4. Configures `nginx` with a unique proxy setup for all qualifying nodes.

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
   git clone https://github.com/tududes/rpc-load-balancer.git ~/rpc-load-balancer
   cd ~/rpc-load-balancer
   ```

2. Install the load balancer:
   ```bash
   apt install make -y
   make install
   ```

3. Configure your environment variables:
   - Edit `.env` to customize the behavior.

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
     (crontab -l; echo "*/15 * * * * cd $HOME/rpc-load-balancer && REPO_PATH=$HOME/rpc-load-balancer make cron >> cron.log 2>&1") | crontab -
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

Generated configuration includes the top three RPC fullnodes for proxying:

```nginx
#BEGIN_PROXY_SERVERS
server {
  listen      30001 default_server;
  server_name 30001.local;
  location / {
      proxy_pass       https://127.0.0.1:26657;
      proxy_set_header Host 127.0.0.1;
  }
}
server {
  listen      30002 default_server;
  server_name 30002.local;
  location / {
      proxy_pass       https://namada.liquify.com:443;
      proxy_set_header Host namada.liquify.com;
  }
}
server {
  listen      30003 default_server;
  server_name 30003.local;
  location / {
      proxy_pass       https://namada-rpc.mandragora.io:443;
      proxy_set_header Host namada-rpc.mandragora.io;
  }
}
#END_PROXY_SERVERS
```

This configuration ensures the best performance by qualifying and testing nodes.

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
  - Adjust `BALANCER_TOLERANCE` for stricter or looser performance criteria.

---

For additional help, submit issues or feature requests via GitHub.
