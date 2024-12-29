import sys
import os
import dotenv
import requests
import socket
import subprocess
import grpc
import json
import time

# Reflection imports
from grpc_reflection.v1alpha.reflection_pb2_grpc import ServerReflectionStub
from grpc_reflection.v1alpha.reflection_pb2 import ServerReflectionRequest

# Protobuf descriptor imports
from google.protobuf.descriptor_pb2 import FileDescriptorProto
from google.protobuf import descriptor_pool, descriptor_database, message_factory
from google.protobuf.json_format import MessageToJson

# Tolerance of max height: fixed count integer

# Load environment variables
dotenv.load_dotenv()
balancer_tolerance = os.getenv("BALANCER_TOLERANCE", 50)
chain_id = os.getenv("CHAIN_ID", "osmosis-1")
rpc_list = os.getenv("RPC_LIST", "https://raw.githubusercontent.com/cosmos/chain-registry/refs/heads/master/osmosis/chain.json")
local_rpc_port = os.getenv("LOCAL_RPC_PORT", 9090)
rpc_lb_domain = os.getenv("RPC_LB_DOMAIN", "osmosis-grpc.tududes.com")
rpc_test_timeout = os.getenv("RPC_TEST_TIMEOUT", 5)
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


def sanitize_endpoints(raw_endpoints):
    """Sanitize and deduplicate a list of endpoints."""
    sanitized = set()  # Use a set to automatically deduplicate
    for endpoint in raw_endpoints:
        # Remove the https:// prefix if present
        if endpoint.startswith("https://"):
            endpoint = endpoint[len("https://"):]
        # Ensure valid format (hostname:port)
        if ":" not in endpoint:
            # Add default port if missing
            endpoint = f"{endpoint}:443"
        sanitized.add(endpoint)
    return list(sanitized)


def connect_to_grpc_server(endpoint, timeout_seconds=rpc_test_timeout):
    """
    Attempt to connect over a secure channel first.
    If that fails, fall back to an insecure channel.
    In both cases, we wait up to `timeout_seconds` for the channel to become READY.
    Returns the channel or None if both fail.
    """
    credentials = grpc.ssl_channel_credentials()

    # 1) Try a secure channel
    secure_channel = grpc.secure_channel(endpoint, credentials)
    try:
        # Attempt to verify connectivity within a short timeout.
        grpc.channel_ready_future(secure_channel).result(timeout=timeout_seconds)
        print(f"Secure channel to {endpoint} established.")
        return secure_channel
    except Exception as e:
        secure_channel.close()
        print(f"Secure channel failed for {endpoint}: {e}\nFalling back to insecure channel...")

    # 2) Fall back to an insecure channel
    insecure_channel = grpc.insecure_channel(endpoint)
    try:
        grpc.channel_ready_future(insecure_channel).result(timeout=timeout_seconds)
        print(f"Insecure channel to {endpoint} established.")
        return insecure_channel
    except Exception as e:
        insecure_channel.close()
        print(f"Insecure channel also failed for {endpoint}: {e}")
        # If we get here, neither secure nor insecure worked
        return None


def call_epoch_infos_via_reflection(endpoint):
    """
    Reflection-based approach that dynamically:
      1) Finds the file descriptor for osmosis.epochs.v1beta1.Query
      2) Identifies the 'EpochInfos' method
      3) Sends an empty request message
      4) Parses the response to JSON
    Returns JSON string or None on error.
    """

    service_name = "osmosis.epochs.v1beta1.Query"
    method_name = "EpochInfos"
    full_method_name = f"/{service_name}/{method_name}"

    try:
        print(f"Connecting to {endpoint} using secure gRPC for reflection-based query...")

        channel = connect_to_grpc_server(endpoint)
        reflection_stub = ServerReflectionStub(channel)

        # We use a local in-memory DescriptorDatabase + DescriptorPool
        db = descriptor_database.DescriptorDatabase()
        pool = descriptor_pool.DescriptorPool(db)

        # Step 1: ask for the file containing the symbol "osmosis.epochs.v1beta1.Query"
        request = ServerReflectionRequest(file_containing_symbol=service_name)
        responses = reflection_stub.ServerReflectionInfo(iter([request]))

        for response in responses:
            if response.HasField("file_descriptor_response"):
                fds = response.file_descriptor_response.file_descriptor_proto
                for fd_bytes in fds:
                    fd_proto = FileDescriptorProto()
                    fd_proto.ParseFromString(fd_bytes)
                    db.Add(fd_proto)

        # Now the pool should know about the service "osmosis.epochs.v1beta1.Query".
        service_descriptor = pool.FindServiceByName(service_name)
        if not service_descriptor:
            print(f"Service descriptor for {service_name} not found via reflection.")
            channel.close()
            return None

        # Find the "EpochInfos" method descriptor
        method_descriptor = None
        for i in range(len(service_descriptor.methods)):
            m = service_descriptor.methods[i]
            if m.name == method_name:
                method_descriptor = m
                break

        if not method_descriptor:
            print(f"Method descriptor for {method_name} not found.")
            channel.close()
            return None

        # "EpochInfos" has an empty request in Osmosis, but let's confirm:
        # The request_type is something like "osmosis.epochs.v1beta1.QueryEpochInfosRequest"
        # We'll build a dynamic message for the request:
        request_type = method_descriptor.input_type
        factory = message_factory.MessageFactory(pool)
        request_msg_class = factory.GetPrototype(request_type)
        request_msg = request_msg_class()  # Should be empty

        # Step 2: We do a low-level unary-unary call: /osmosis.epochs.v1beta1.Query/EpochInfos
        # We must supply appropriate serializers: 
        # - request_serializer will do request_msg.SerializeToString()
        # - response_deserializer will parse into the response type

        # Build response message class
        response_type = method_descriptor.output_type
        response_msg_class = factory.GetPrototype(response_type)

        # Prepare the stubs
        # unary_unary(path, request_serializer, response_deserializer)
        grpc_method = channel.unary_unary(
            full_method_name,
            request_serializer=lambda msg: msg.SerializeToString(),
            response_deserializer=lambda buf: response_msg_class.FromString(buf),
        )

        # Call it
        response_msg = grpc_method(request_msg)

        # Step 3: Convert dynamic protobuf message to JSON
        # We can use MessageToJson() if it sees the correct descriptor
        # But in some reflection contexts, we need to supply the descriptor pool
        # Here, if `response_msg` is a valid protobuf message, MessageToJson should work.
        epoch_info_json = MessageToJson(response_msg)
        channel.close()
        
        # json to dict
        epoch_info = json.loads(epoch_info_json)

        return epoch_info

    except grpc.RpcError as e:
        print(f"Reflection-based gRPC call failed: {e}")
    except Exception as e:
        print(f"Error in reflection-based approach: {e}")

    return None





# Read endpoints from the adjacent file
with open("endpoints.txt", "r") as f:
    endpoints = [line.strip() for line in f.readlines() if line.strip() != '' and not line.startswith('#')]

try:
    response = requests.get(rpc_list, timeout=5)
    data = response.json()
    for endpoint in data["apis"]["grpc"]:
        endpoints.append(f"{endpoint['address']}")
except Exception as e:
    print(f"Error fetching data from {rpc_list}: {e}")

# Sanitize and deduplicate endpoints
endpoints = sanitize_endpoints(endpoints)

print("Endpoints to check:")
print(endpoints)

# Attempt reflection-based call to fetch EpochInfos from each endpoint
ledger_versions = {}
for endpoint in endpoints:
    if len(endpoint) > 0:
        try:
            epoch_info = call_epoch_infos_via_reflection(endpoint)
            if epoch_info:
                # get the current epoch start height:
                # {'epochs': [{'identifier': 'day', 'startTime': '2021-06-18T17:00:00Z', 'duration': '86400s', 'currentEpoch': '1289', 'currentEpochStartTime': '2024-12-28T17:16:09.898160996Z', 'epochCountingStarted': True, 'currentEpochStartHeight': '26562396'}, {'identifier': 'week', 'startTime': '2021-06-18T17:00:00Z', 'duration': '604800s', 'currentEpoch': '184', 'currentEpochStartTime': '2024-12-27T17:02:07.229632445Z', 'epochCountingStarted': True, 'currentEpochStartHeight': '26498258'}]}
                
                for epoch in epoch_info['epochs']:
                    if epoch['identifier'] == 'day':
                        ledger_versions[endpoint] = int(epoch['currentEpochStartHeight'])
                        break
        except Exception as e:
            print(f"Error fetching data from {endpoint}: {e}")

print("Ledger versions:")
print(ledger_versions)
#quit()

# Find the most popular ledger version
ledger_version_counts = {}
for endpoint, ledger_version in ledger_versions.items():
    if ledger_version not in ledger_version_counts:
        ledger_version_counts[ledger_version] = 0
    ledger_version_counts[ledger_version] += 1


# Filter out endpoints that are not in the most popular ledger version using a list comprehension
top_endpoints = [
    endpoint for endpoint, ledger_version in ledger_versions.items() 
    if ledger_version == max(ledger_version_counts, key=ledger_version_counts.get)
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
percent_per_server = 100 / ( (count_endpoints * 2) + 1 )
percent_per_server = round(percent_per_server, 2)

i=0
for idx, endpoint in enumerate(top_endpoints, start=1):
    i += 1
    hp_split = endpoint.split(":")
    host = hp_split[0]
    port = hp_split[1] if len(hp_split) > 1 else "443"  # Default to 443 if no port is specified
        
    #server_port_entries.append(f"    server 127.0.0.1:{new_port};\n")
    protocol = "grpcs" if port == "443" else "grpc"
    upstream = f"{protocol}://{host}:{port}"
    if i < count_endpoints:
        server_port_entries.append(f"\t{percent_per_server}%\tgrpc://{host}:{port};\n")
        server_port_entries.append(f"\t{percent_per_server}%\tgrpcs://{host}:{port};\n")
        #server_port_entries.append(f"\t{percent_per_server}%\t{upstream};\n")
    else:
        server_port_entries.append(f"\t{percent_per_server}%\tgrpc://{host}:{port};\n")
        server_port_entries.append(f"\t*\tgrpcs://{host}:{port};\n")
        #server_port_entries.append(f"\t*\tgrpcs://{upstream};\n")

# Add the closing lines
server_port_entries.append(server_port_end)

# Replace the old upstream block with the new configuration
nginx_cfg_content[start_index:end_index] = server_port_entries


# Write back to the file
with open(nginx_config, "w") as f:
    f.writelines(nginx_cfg_content)

print("Nginx configuration updated!")
