import sys
import os
import dotenv
import requests
import socket
import subprocess


# Tolerance of max height: fixed count integer

# Load environment variables
dotenv.load_dotenv()
balancer_tolerance = os.getenv("BALANCER_TOLERANCE", 7)
chain_id = os.getenv("CHAIN_ID", "namada.5f5de2dd1b88cba30586420")
rpc_list = os.getenv("RPC_LIST", "https://raw.githubusercontent.com/Luminara-Hub/namada-ecosystem/refs/heads/main/user-and-dev-tools/mainnet/rpc.json")
local_rpc_port = os.getenv("LOCAL_RPC_PORT", 26657)
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
start_index = nginx_cfg_content.index("upstream fullnodes {\n")
end_index = nginx_cfg_content.index("}\n", start_index) + 1

# Replace lines with top endpoints
new_lines = ["upstream fullnodes {\n"]
for endpoint in top_endpoints:
    try:
        # Extract hostname and port
        host_port = endpoint.split("//")[1].split("/")[0]
        if ":" not in host_port:
            # Add default port if not specified
            host_port += ":443"
        new_lines.append(f"    server {host_port};\n")
    except IndexError:
        raise ValueError(f"Invalid endpoint format: {endpoint}")
new_lines.append("}\n")

nginx_cfg_content[start_index:end_index] = new_lines


# Write back to the file
with open(nginx_config, "w") as f:
    f.writelines(nginx_cfg_content)

print("Nginx configuration updated!")
