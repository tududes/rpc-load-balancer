import sys
import os
import dotenv
import requests
import socket
import subprocess


# Tolerance of max height: fixed count integer

# Load environment variables
dotenv.load_dotenv()
balancer_tolerance = os.getenv("BALANCER_TOLERANCE", 30)
chain_id = os.getenv("CHAIN_ID", "osmosis-1")
rpc_list = os.getenv("RPC_LIST", "https://snapshots.kjnodes.com/_rpc/osmosis.json")
local_rpc_port = os.getenv("LOCAL_RPC_PORT", 26657)
rpc_lb_domain = os.getenv("RPC_LB_DOMAIN", "osmosis-rpc.tududes.com")
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
    for key, value in data.items():
        print(value)
        # {'moniker': 'rpc-2.osmosis.nodes.guru', 'network': 'osmosis-1', 'tx_index': 'on', 'earliest_block_height': 23074631, 'latest_block_height': 26518126, 'voting_power': 0, 'is_validator': False, 'blocks_indexed': 3443495, 'catching_up': False, 'data_since': '2024-10-28T12:59:45.261114204Z'}
        if value['network'] == chain_id:
            endpoints.append(f"http://{key}")
    #print(data)
except Exception as e:
    print(f"Error fetching data from {rpc_list}: {e}")

print("Endpoints to check:")
print(endpoints)
#quit()



# Fetch ledger_version from each endpoint
ledger_versions = {}
for endpoint in endpoints:
    if len(endpoint) > 0:
        try:
            
            # If the domain is local, swap to 127.0.0.1:local_rpc_port
            domain = endpoint.split("//")[1].split("/")[0]  # Extract domain from endpoint
            # if is_domain_local(domain):
            #     # if localhost port local_rpc_port is open, use it
            #     local_endpoint = f"http://127.0.0.1:{local_rpc_port}/"
            #     request = requests.get(f"{local_endpoint}/block", timeout=1)
            #     if request.status_code == 200:
            #         endpoint = local_endpoint
            #     else:
            #         continue
        
            # try the directory endpoint first
            try:
                response = requests.get(f"{endpoint}/", timeout=1)
                data = response.text
                if 'endpoints' not in data:
                    continue
            except Exception as e:
                print(f"Error fetching data from {endpoint}: {e}")
                continue
            
            
            # make sure the tx_index is on
            try:
                response = requests.get(f"{endpoint}/status", timeout=1)
                data = response.json()
                tx_indexer_status = data.get('result', {}).get('node_info', {}).get('other', {}).get('tx_index', '')
                if tx_indexer_status != "on":
                    print(f"Endpoint {endpoint} has tx_index: {tx_indexer_status}")
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

print("Ledger versions:")
print(ledger_versions)
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
#server_port_beg = "upstream to_proxy_servers {\n"
server_port_beg = "#BEGIN_SPLIT_CLIENTS\n"
server_port_end = "#END_SPLIT_CLIENTS\n"

# Find the start and end index of the block
start_index = nginx_cfg_content.index(server_port_beg)
end_index = nginx_cfg_content.index(server_port_end, start_index) + 1

# Replace lines with top endpoints
server_port_entries = [server_port_beg]

# determine the percentage for each server port entry
count_endpoints = len(top_endpoints)
percent_per_server = 100 / count_endpoints
percent_per_server = round(percent_per_server, 2)

i=0
for idx, endpoint in enumerate(top_endpoints, start=1):
    i += 1
    host_port = endpoint.split("//")[1].split("/")[0]
    hp_split = host_port.split(":")
    host = hp_split[0]
    port = hp_split[1] if len(hp_split) > 1 else "443"  # Default to 443 if no port is specified
        
    #server_port_entries.append(f"    server 127.0.0.1:{new_port};\n")
    if i < count_endpoints:
        server_port_entries.append(f"	{percent_per_server}%	{host_port};\n")
    else:
        server_port_entries.append(f"	*	{host_port};\n")

# Add the closing lines
server_port_entries.append(server_port_end)

# Replace the old upstream block with the new configuration
nginx_cfg_content[start_index:end_index] = server_port_entries


# Write back to the file
with open(nginx_config, "w") as f:
    f.writelines(nginx_cfg_content)

print("Nginx configuration updated!")
