import sys
import os
import dotenv
import requests
import socket
import subprocess


# Tolerance of max height: fixed count integer

# Load environment variables
dotenv.load_dotenv()
balancer_tolerance = os.getenv("BALANCER_TOLERANCE", 10)
chain_id = os.getenv("CHAIN_ID", "namada.5f5de2dd1b88cba30586420")
rpc_list = os.getenv("RPC_LIST", "https://raw.githubusercontent.com/Luminara-Hub/namada-ecosystem/refs/heads/main/user-and-dev-tools/mainnet/rpc.json")
local_rpc_port = os.getenv("LOCAL_RPC_PORT", 26657)
rpc_lb_domain = os.getenv("RPC_LB_DOMAIN", "namada-rpc.tududes.com")
nginx_config = sys.argv[1]


def get_local_ips():
    """Retrieve all local IP addresses."""
    try:
        result = subprocess.run(["hostname", "-I"], stdout=subprocess.PIPE, text=True)
        return result.stdout.strip().split()
    except Exception as e:
        print(f"Error retrieving local IPs: {e}")
        return []

def resolve_domain(domain):
    """Resolve the domain to an IP address."""
    try:
        return socket.gethostbyname(domain)
    except socket.gaierror as e:
        print(f"Error resolving domain {domain}: {e}")
        return None

def is_domain_local(domain):
    """Check if the domain is hosted on the local machine."""
    local_ips = get_local_ips()
    domain_ip = resolve_domain(domain)
    return domain_ip in local_ips


# Read endpoints from the adjacent file
with open("endpoints.txt", "r") as f:
    endpoints = [line.strip() for line in f.readlines() if line.strip() != '' and not line.startswith('#')]

try:
    response = requests.get(rpc_list, timeout=5)
    data = response.json()
    for rpc in data:
        if rpc['RPC Address'] not in endpoints:
            endpoints.append(rpc['RPC Address'])
    #print(data)
except Exception as e:
    print(f"Error fetching data from {rpc_list}: {e}")

#print(endpoints)
#quit()



# Fetch ledger_version from each endpoint
ledger_versions = {}
for endpoint in endpoints:
    if len(endpoint) > 0:
        try:
            
            # If the domain is local, swap to 127.0.0.1:local_rpc_port
            domain = endpoint.split("//")[1].split("/")[0]  # Extract domain from endpoint
            if is_domain_local(domain):
                # if localhost port local_rpc_port is open, use it
                local_endpoint = f"http://127.0.0.1:{local_rpc_port}/"
                request = requests.get(f"{local_endpoint}/block", timeout=1)
                if request.status_code == 200:
                    endpoint = local_endpoint
                else:
                    continue
        
            # try the directory endpoint first
            try:
                response = requests.get(f"{endpoint}/", timeout=1)
                data = response.text
                if 'endpoints' not in data:
                    continue
            except Exception as e:
                print(f"Error fetching data from {endpoint}: {e}")
                continue
            
            # get info from the block endpoint
            try:
                response = requests.get(f"{endpoint}/block", timeout=1)
                data = response.json()
                rpc_chain_id = data.get('result', {}).get('block', {}).get('header', {}).get('chain_id', '')
                if rpc_chain_id == chain_id:
                    ledger_version = int(data.get('result', {}).get('block', {}).get('header', {}).get('height', 0))
                    if isinstance(ledger_version, int) and ledger_version > 0:  # Ensure ledger_version is an integer
                        print(f"Endpoint {endpoint} has ledger_version {ledger_version} and chain_id {rpc_chain_id}")
                        ledger_versions[endpoint] = ledger_version
            except Exception as e:
                print(f"Error fetching data from {endpoint}: {e}")
                continue
        except Exception as e:
            print(f"Error fetching data from {endpoint}: {e}")

#print(ledger_versions)
#quit()

# Find the highest ledger_version
max_version = max(ledger_versions.values())

# Filter out endpoints that are within a range ±5 of the highest ledger_version
top_endpoints = [
    endpoint for endpoint, version in ledger_versions.items()
    if (max_version - balancer_tolerance) <= version <= (max_version + balancer_tolerance)
]


# Update Nginx configuration
with open(nginx_config, "r") as f:
    nginx_cfg_content = f.readlines()

# Identify the lines to replace
server_port_beg = "upstream to_proxy_servers {\n"
server_port_end = "}\n"
server_block_beg = "#BEGIN_PROXY_SERVERS\n"
server_block_end = "#END_PROXY_SERVERS\n"

start_index = nginx_cfg_content.index(server_port_beg)
end_index = nginx_cfg_content.index(server_port_end, start_index) + 1

start_proxy_index = nginx_cfg_content.index(server_block_beg)
end_proxy_index = nginx_cfg_content.index(server_block_end, start_proxy_index) + 1

# Replace lines with top endpoints
port_start = 30000  # Starting port for localhost upstream servers
server_port_entries = [server_port_beg]
server_block_entries = [server_block_beg]
upstream_ports = []

for idx, endpoint in enumerate(top_endpoints, start=1):
    host_port = endpoint.split("//")[1].split("/")[0]
    hp_split = host_port.split(":")
    host = hp_split[0]
    port = hp_split[1] if len(hp_split) > 1 else "443"  # Default to 443 if no port is specified
    
    new_port = port_start + idx
    upstream_ports.append(new_port)
    
    server_port_entries.append(f"    server 127.0.0.1:{new_port};\n")
    
    # add_header Access-Control-Allow-Origin *;
    # add_header Access-Control-Max-Age 3600;
    # add_header Access-Control-Expose-Headers Content-Length;
    server_block = (
        f"server {{\n"
        f"	listen      {new_port} ssl http2;\n"
        f"	server_name {new_port}.local;\n"
        f"	ssl_certificate /etc/letsencrypt/live/{rpc_lb_domain}/fullchain.pem;\n"
        f"	ssl_certificate_key /etc/letsencrypt/live/{rpc_lb_domain}/privkey.pem;\n"
        f"	location / {{\n"
        f"		proxy_pass https://{host}:{port};\n"
        f"		proxy_set_header Host {host};\n"
        f"		proxy_set_header X-Real-IP $remote_addr;\n"
        f"		proxy_set_header Upgrade $http_upgrade;\n"
        f"		proxy_set_header Connection 'upgrade';\n"
        #f"		proxy_hide_header Access-Control-Allow-Origin;\n"
        # f"		add_header Access-Control-Allow-Origin *;\n"
        # f"		add_header Access-Control-Max-Age 3600;\n"
        # f"		add_header Access-Control-Expose-Headers Content-Length;\n"
        f"		proxy_http_version 1.1;\n"
        f"		proxy_ssl_verify off;\n"
        f"	}}\n"
        f"}}\n"
    )
    server_block_entries.append(server_block)

# Add the closing lines
server_port_entries.append(server_port_end)
server_block_entries.append(server_block_end)

# Replace the old upstream block with the new configuration
nginx_cfg_content[start_index:end_index] = server_port_entries

# Replace the old proxy server block with the new configuration
nginx_cfg_content[start_proxy_index:end_proxy_index] = server_block_entries


# Write back to the file
with open(nginx_config, "w") as f:
    f.writelines(nginx_cfg_content)

print("Nginx configuration updated!")
