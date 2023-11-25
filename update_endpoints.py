import sys
import requests

balancer_tolerance = 0.03

#nginx_config = "/etc/nginx/sites-available/rpc-load-balancer"
nginx_config = sys.argv[1]

# Read endpoints from the adjacent file
with open("endpoints.txt", "r") as f:
    endpoints = [line.strip() for line in f.readlines()]

# Fetch ledger_version from each endpoint
ledger_versions = {}
for endpoint in endpoints:
    if len(endpoint) > 0:
        try:
            response = requests.get(endpoint, timeout=5)
            data = response.json()
            ledger_version = int(data.get('ledger_version'))
            if isinstance(ledger_version, int) and ledger_version > 0:  # Ensure ledger_version is an integer
                ledger_versions[endpoint] = int(ledger_version)
        except Exception as e:
            print(f"Error fetching data from {endpoint}: {e}")

print(ledger_versions)
#quit()

# Find the highest ledger_version
max_version = max(ledger_versions.values())

# Filter out endpoints that are within 3% of the highest ledger_version
top_endpoints = [endpoint for endpoint, version in ledger_versions.items() if version >= int((1.0 - balancer_tolerance) * max_version)]

# Update Nginx configuration
with open(nginx_config, "r") as f:
    content = f.readlines()

# Identify the lines to replace
start_index = content.index("upstream fullnodes {\n")
end_index = content.index("}\n", start_index) + 1

# Replace lines with top endpoints
new_lines = ["upstream fullnodes {\n"] + [f"    server {endpoint.split('//')[1].split('/')[0]};\n" for endpoint in top_endpoints] + ["}\n"]
content[start_index:end_index] = new_lines

# Write back to the file
with open(nginx_config, "w") as f:
    f.writelines(content)

print("Nginx configuration updated!")
