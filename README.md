
# RPC Load Balancer Setup

This repository provides tools for automated testing and setting up a dynamic gRPC load balancer using `nginx`.

---

## Overview

The Makefile and accompanying scripts automate the testing of gRPC fullnodes by dynamically updating the `nginx` configuration. This ensures only the top-performing nodes are used for proxying.

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
| `RPC_LB_DOMAIN`      | Domain for the gRPC load balancer.                            | `osmosis-grpc.tududes.com`       |
| `BALANCER_TOLERANCE` | Maximum difference in ledger height for eligible fullnodes.  | `50`                            |
| `CHAIN_ID`           | Chain ID to validate fullnode compatibility.                 | `osmosis-1` |
| `LOCAL_RPC_PORT`     | Port for local gRPC service when applicable.                 | `9090`                        |

---

## Setup Instructions

1. Clone the repository:
   ```bash
   cd $HOME
   git clone https://github.com/tududes/rpc-load-balancer -b osmosis-mainnet-grpc grpc-load-balancer
   cd $HOME/grpc-load-balancer
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
     # gRPC Load Balancer Update
     (crontab -l; echo "*/15 * * * * cd $HOME/grpc-load-balancer && REPO_PATH=$HOME/grpc-load-balancer make cron-nogit >> cron.log 2>&1") | crontab -
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

Generated configuration includes only tested gRPC fullnodes for proxying:

```nginx
split_clients "${msec}${remote_addr}${remote_port}" $osmosis_grpc_upstream {
#BEGIN_SPLIT_CLIENTS
	20.00%	grpc://osmosis-grpc.polkachu.com:12590;
	20.00%	grpcs://grpc.archive.osmosis.zone:443;
	20.00%	grpcs://osmosis.grpc.stakin-nodes.com:443;
	20.00%	grpcs://grpc.osmosis.zone:443;
	*	grpc://grpc-osmosis-01.stakeflow.io:6754;
#END_SPLIT_CLIENTS
}

server {
	listen 80;
	server_name osmosis-grpc.tududes.com;
	return 301 https://$host$request_uri;
}

server {
	listen 443 ssl http2;
	server_name osmosis-grpc.tududes.com;
	resolver 8.8.8.8;

	ssl_certificate	 /etc/letsencrypt/live/osmosis-grpc.tududes.com/fullchain.pem;
	ssl_certificate_key /etc/letsencrypt/live/osmosis-grpc.tududes.com/privkey.pem;

	location / {
		# Pass to whichever upstream was chosen above
		grpc_pass $osmosis_grpc_upstream;
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
  - Check JSON endpoint for list of nodes and field used to represent gRPC endpoints.
  - Adjust `BALANCER_TOLERANCE` for stricter or looser performance criteria.

---

For additional help, submit issues or feature requests via GitHub!

# DISCLAIMER
This repository serves as a tool to access a more reliable list of gRPC endpoints. The code to accomplish this is provided as-is. No guarantees are made regarding the availability or performance of the listed nodes. Use at your own risk.
