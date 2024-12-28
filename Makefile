SHELL=/usr/bin/env bash

ifndef GIT_ORG
GIT_ORG=tududes
endif

ifndef GIT_REPO
GIT_REPO=rpc-load-balancer
endif

ifndef REPO_PATH
REPO_PATH=~/${GIT_REPO}
endif

ifndef RPC_LB_DOMAIN
RPC_LB_DOMAIN=namada-rpc.tududes.com
endif

ifndef RPC_LB_SITE_FILE
RPC_LB_SITE_FILE=rpc-load-balancer
endif


define RPC_LB_SITE_CONTENTS
split_clients "$${msec}$${remote_addr}$${remote_port}" $$rpc_upstream {
#BEGIN_SPLIT_CLIENTS
	99%	localhost:26657;
# Always use DOT at end entry if you wonder why, read the SC code.
	*	localhost:26657;
#END_SPLIT_CLIENTS
}

server {
	listen 80;
	server_name ${RPC_LB_DOMAIN};
	return 301 https://$$host$$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${RPC_LB_DOMAIN};
    resolver 8.8.8.8;

    ssl_certificate     /etc/letsencrypt/live/${RPC_LB_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${RPC_LB_DOMAIN}/privkey.pem;

    location / {
        # Pass to whichever upstream was chosen above
        proxy_pass https://$$rpc_upstream;

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
        proxy_set_header Host           $$rpc_upstream;
        proxy_set_header X-Real-IP      $$remote_addr;
        proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
        proxy_set_header Upgrade        $$http_upgrade;
        proxy_set_header Connection     "upgrade";

        # CORS
        proxy_hide_header Access-Control-Allow-Origin;
        add_header Access-Control-Allow-Origin * always;
        add_header Access-Control-Expose-Headers Content-Length;

        if ($$request_method = OPTIONS) {
            add_header Access-Control-Allow-Origin   * always;
            add_header Access-Control-Expose-Headers Content-Length;
            return 204;
        }

        proxy_http_version 1.1;
        proxy_ssl_verify off;
    }
}
endef
export RPC_LB_SITE_CONTENTS


install: rpc-load-balancer do-install update-list test-list
	echo "Finished!"


do-install:
	sudo apt install -y python3 nginx nginx-common nginx-full
	sudo ln -sf /etc/nginx/sites-available/${RPC_LB_SITE_FILE} /etc/nginx/sites-enabled/${RPC_LB_SITE_FILE}
	sudo apt install certbot python3-certbot-nginx -y
	sudo certbot certonly --manual --preferred-challenges=dns --server https://acme-v02.api.letsencrypt.org/directory --domain ${RPC_LB_DOMAIN}
#	sudo certbot --nginx -d ${RPC_LB_DOMAIN} --register-unsafely-without-email --agree-tos
	sudo systemctl reload nginx

pull:
	cd ${REPO_PATH} && git pull


push:
	cd ${REPO_PATH} && git add -A && git commit -m "rpc health check" && git push 


update-list: rpc-load-balancer-staged
	cd ${REPO_PATH} && sudo python3 update_endpoints.py /etc/nginx/sites-available/${RPC_LB_SITE_FILE}-staged

test-list:
	cd ${REPO_PATH} && sudo python3 test_upstream_domains.py /etc/nginx/sites-available/${RPC_LB_SITE_FILE}-staged
	export NUM_UPSTREAMS=$$(grep -c "server " /etc/nginx/sites-available/${RPC_LB_SITE_FILE}); \
	for i in $$(seq 1 $$NUM_UPSTREAMS); do \
		curl -s -k https://${RPC_LB_DOMAIN}/block; \
	done

cron: pull update-list test-list push
	echo "Finished!"


cron-nogit: update-list test-list
	echo "Finished without git!"



rpc-load-balancer-staged:
	mkdir -p /etc/nginx/sites-available/
	@echo "$$RPC_LB_SITE_CONTENTS" | sudo tee /etc/nginx/sites-available/${RPC_LB_SITE_FILE}-staged

rpc-load-balancer:
	mkdir -p /etc/nginx/sites-available/
	@echo "$$RPC_LB_SITE_CONTENTS" | sudo tee /etc/nginx/sites-available/${RPC_LB_SITE_FILE}
