#!/usr/bin/env python3

import sys
import os
import re
import subprocess
import time
import shutil

####################################
# Constants / Configuration
####################################

# The live NGINX config path (where your Makefile writes the final config)
STAGED_CONFIG_PATH = sys.argv[1]

# Replace -staged with -live to get the live config path
LIVE_CONFIG_PATH = STAGED_CONFIG_PATH.replace("-staged", "")

# A temporary test config path
TEST_CONFIG_PATH = f"{STAGED_CONFIG_PATH}-single"

# The domain used for test requests using basename of file
TEST_SERVER_NAME = os.path.basename(TEST_CONFIG_PATH).split(".")[0]

# A test port (to avoid clashing with 443 in production)
TEST_LISTEN_PORT = 443

# Curl URL for testing
CURL_TEST_URL = f"https://{TEST_SERVER_NAME}:{TEST_LISTEN_PORT}/"

# Markers in the config where we insert our random upstream lines
BEGIN_MARKER = "#BEGIN_SPLIT_CLIENTS\n"
END_MARKER   = "#END_SPLIT_CLIENTS\n"

####################################
# Utility functions
####################################

def run_cmd(cmd, check=True):
    """
    Utility to run a shell command and optionally check for errors.
    Returns (stdout) or raises RuntimeError on non-zero exit if check=True.
    """
    print(f"[CMD] {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print("Error:", result.stderr.strip())
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.stdout.strip()

def nginx_test_and_reload():
    """Run 'nginx -t' and 'systemctl reload nginx'."""
    run_cmd(["sudo", "nginx", "-t"])
    #run_cmd(["sudo", "systemctl", "reload", "nginx"])
    run_cmd(["sudo", "nginx", "-s", "reload"])
    time.sleep(1)  # short pause to let reload settle

def curl_test(url):
    """
    Run a curl test to the provided URL.
    Return True if HTTP code is 2xx, False otherwise.
    """
    
    # replace the cmd with a curl command that returns the http code
    cmd = ["curl", "-ks", "-o", "/dev/null", "-w", "%{http_code}", "--resolve", f"{TEST_SERVER_NAME}:{TEST_LISTEN_PORT}:127.0.0.1", url]
    
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print("[CURL ERROR]", proc.stderr.strip())
        return False

    http_code = proc.stdout.strip()
    print("[CURL RESPONSE]", http_code)
    # If 2xx => success
    return http_code.startswith("2")


####################################
# Core logic
####################################

def get_split_clients_block(config_text):
    begin_idx = config_text.index(BEGIN_MARKER)
    end_idx = config_text.index(END_MARKER, begin_idx) + 1

    if begin_idx is None or end_idx is None or end_idx <= begin_idx:
        raise ValueError("Could not find #BEGIN_SPLIT_CLIENTS / #END_SPLIT_CLIENTS block.")
    
    return begin_idx, end_idx


def get_domains_from_config(config_text):
    """
    Extract lines between #BEGIN_SPLIT_CLIENTS and #END_SPLIT_CLIENTS
    of the form:
        3.57%  "domain";
        *      "domain";
    and return a list of those domain strings (without quotes).
    """
    
    # print(config_text)
    # quit()

    begin_idx, end_idx = get_split_clients_block(config_text)   
    block_lines = config_text[begin_idx+1:end_idx]  # lines inside the block

    # print(block_lines)
    # quit()

    # Regex to match lines like: 
    # ['\t2.7%\t127.0.0.1;\n', '\t2.7%\tnamada.liquify.com;\n', '\t2.7%\tnamada-rpc.mandragora.io;\n', '\t2.7%\tnamadam.powerstaking.tech;\n', '\t2.7%\tnamada-main.stakesystems.io;\n', '\t2.7%\trpc-namada.5elementsnodes.com;\n', '\t2.7%\tnamada-rpc.hadesguard.tech;\n', '\t2.7%\tnamada-mainnet-rpc.itrocket.net;\n', '\t2.7%\tnamada-rpc.sproutstake.space;\n', '\t2.7%\trpc.papadritta.com;\n', '\t2.7%\tnamada.rpc.decentrio.ventures;\n', '\t2.7%\trpc.namada.stakepool.dev.br;\n', '\t2.7%\trpc.namadascan.io;\n', '\t2.7%\tnamada-rpc.synergynodes.com;\n', '\t2.7%\tnamada-mainnet.rpc.l0vd.com;\n', '\t2.7%\tnamada.loserboy.xyz;\n', '\t2.7%\tnamada.itudou.xyz;\n', '\t2.7%\trpc.namada.validatus.com;\n', '\t2.7%\tnamada-rpc.0xcryptovestor.com;\n', '\t2.7%\tnamada-rpc.0xwave.com;\n', '\t2.7%\tnamada-mainnet-rpc.mellifera.network;\n', '\t2.7%\tnamada-rpc.max-02.xyz;\n', '\t2.7%\tnamada-mainnet-rpc.denodes.xyz;\n', '\t2.7%\tnamada.rpc.liveraven.net;\n', '\t2.7%\tnamada-rpc.palamar.io;\n', '\t2.7%\tnamada-rpc.validatorvn.com;\n', '\t2.7%\trpc.namada.stakeup.tech;\n', '\t2.7%\trpc.namada.citizenweb3.com;\n', '\t2.7%\tlightnode-rpc-mainnet-namada.grandvalleys.com;\n', '\t2.7%\tmainnet-namada-rpc.konsortech.xyz;\n', '\t2.7%\tnamada-rpc.contributiondao.com;\n', '\t2.7%\tnamada-mainnet-rpc.crouton.digital;\n', '\t2.7%\tnamada-rpc.emberstake.xyz;\n', '\t2.7%\trpc-1.namada.nodes.guru;\n', '\t2.7%\tnamada.tdrsys.com;\n', '\t2.7%\trpc-namada.architectnodes.com;\n', '\t*\tnamada-rpc.murphynode.net;\n', '#END_SPLIT_CLIENTS\n']
    
    pattern = re.compile(r'^\s*(?:\d+(?:\.\d+)?%|\*)\s+([^\s;]+);')

    domains = []
    for bl in block_lines:
        match = pattern.search(bl.strip())
        if match:
            domains.append(match.group(1))
    return domains


def build_config_for_single_domain(config_text, domain):
    # 1) Replace the SPLIT_CLIENTS block with a single line

    # print(config_text)
    # quit()

    begin_idx, end_idx = get_split_clients_block(config_text)

    # We'll build something like:
    #   * "<domain>";
    # as the single line in that block (100%).
    new_block_lines = [
        BEGIN_MARKER,
        f"\t*\t\"{domain}\";\n",  # 100% traffic to this domain
        END_MARKER
    ]
    
    # Replace the old upstream block with the new configuration
    config_text[begin_idx:end_idx] = new_block_lines
    
    # Find the server_name line and replace it
    config_text = [re.sub(r"server_name\s+[^;]+;", f"server_name {TEST_SERVER_NAME};", line) for line in config_text]
    
    # For any instance of rpc_upstream replace it with rpc_upstream_test
    config_text = [re.sub(r"rpc_upstream", TEST_SERVER_NAME.replace("-", "_"), line) for line in config_text]

    return config_text


def build_final_config(config_text, working_domains):
    """
    Given the original config text and a list of working domains,
    rebuild the lines between #BEGIN_SPLIT_CLIENTS and #END_SPLIT_CLIENTS
    so each domain has an equal share of traffic, except the last uses '*'.
    """
    if not working_domains:
        raise ValueError("No working domains found, cannot build final config.")

    begin_idx, end_idx = get_split_clients_block(config_text)

    # We'll build something like:
    #   * "<domain>";
    # as the single line in that block (100%).
        
    n = len(working_domains)
    percentage = 100.0 / n

    new_block_lines = [BEGIN_MARKER]
    # For the first (n-1) domains, we give them a specific fraction
    # The final domain gets '*'
    # e.g. if we have 3 domains, each ~33.33%. The last line is '* "last.domain";'
    
    if n == 1:
        # Only one domain => a single line: '* "domain";'
        new_block_lines.append(f"\t*\t\"{working_domains[0]}\";\n")
    else:
        fraction_str = f"{percentage:.2f}%"
        for d in working_domains[:-1]:
            new_block_lines.append(f"\t{fraction_str}\t\"{d}\";\n")
        
        # final domain with '*'
        new_block_lines.append(f"\t*\t\"{working_domains[-1]}\";\n")

    new_block_lines.append(END_MARKER)

    # Replace the old upstream block with the new configuration
    config_text[begin_idx:end_idx] = new_block_lines

    return config_text


def main():
    # 1) Read the live/original config
    with open(STAGED_CONFIG_PATH, "r") as f:
        original_cfg = f.readlines()
        
    # print(original_cfg)
    # quit()

    # 2) Extract domain lines from the #BEGIN_SPLIT_CLIENTS block
    all_domains = get_domains_from_config(original_cfg)
    print("[INFO] Found domains in split_clients block:")
    for d in all_domains:
        print("  -", d)

    if not all_domains:
        print("[ERROR] No domains found. Exiting.")
        return

    #quit() 
    
    # 3) Create a backup of the original config
    backup_path = LIVE_CONFIG_PATH + ".bak"
    print(f"[INFO] Backing up original config to {backup_path}")
    shutil.copy(LIVE_CONFIG_PATH, backup_path)

    working = []

    # 4) Test each domain individually
    for domain in all_domains:
        print(f"\n=== Testing domain: {domain} ===")

        # a) Build test config that assigns 100% to this domain
        test_cfg = build_config_for_single_domain(original_cfg, domain)
        # print(test_cfg)
        # quit()

        # b) Write test config
        with open(TEST_CONFIG_PATH, "w") as tf:
            tf.writelines(test_cfg)
            
        # enable the site by replacing the sites-available string with sites-enabled
        run_cmd(["sudo", "ln", "-sf", TEST_CONFIG_PATH, TEST_CONFIG_PATH.replace("sites-available", "sites-enabled")])
        
        # c) Check syntax and reload
        try:
            nginx_test_and_reload()
        except RuntimeError:
            print(f"[FAIL] NGINX test/reload failed for domain {domain}. Skipping.")
            continue

        # d) Curl test
        success = curl_test(CURL_TEST_URL)
        if success:
            print(f"[PASS] Domain {domain} responded successfully.")
            working.append(domain)
        else:
            print(f"[FAIL] Domain {domain} did not respond with 2xx.")


    # remove the test enabled site configs
    run_cmd(["sudo", "rm", "-f", TEST_CONFIG_PATH])
    run_cmd(["sudo", "rm", "-f", TEST_CONFIG_PATH.replace("sites-available", "sites-enabled")])

    
    # 5) If no domains worked, restore backup and bail
    if not working:
        print("[ERROR] No domains worked. Restoring backup and exiting.")
        shutil.copy(backup_path, LIVE_CONFIG_PATH)
        try:
            nginx_test_and_reload()
        except RuntimeError:
            pass
        return


    # 6) Build final config with only working domains, each evenly distributed
    final_cfg_text = build_final_config(original_cfg, working)
    
    
    # 7) Write final config, test, reload
    print("\n[INFO] Writing final config with working domains only:")
    for wd in working:
        print("  -", wd)

    with open(LIVE_CONFIG_PATH, "w") as f:
        f.writelines(final_cfg_text)

    try:
        nginx_test_and_reload()
        print("[SUCCESS] Final config loaded with working domains.")
    except RuntimeError:
        print("[ERROR] Final config failed. Restoring backup.")
        shutil.copy(backup_path, LIVE_CONFIG_PATH)
        try:
            nginx_test_and_reload()
        except RuntimeError:
            pass

if __name__ == "__main__":
    main()
