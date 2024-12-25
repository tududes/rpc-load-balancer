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
#BEGIN_PROXY_SERVERS
#END_PROXY_SERVERS
upstream to_proxy_servers {
	server 127.0.0.1:30001;
}

server {
	listen 80;
	server_name ${RPC_LB_DOMAIN};
	return 301 https://$$host$$request_uri;
}

server {
	listen 443 ssl http2;
	server_name ${RPC_LB_DOMAIN};

	ssl_certificate /etc/letsencrypt/live/${RPC_LB_DOMAIN}/fullchain.pem;
	ssl_certificate_key /etc/letsencrypt/live/${RPC_LB_DOMAIN}/privkey.pem;

	location / {
		proxy_pass http://to_proxy_servers;
		proxy_intercept_errors on;
		proxy_next_upstream error timeout http_502 http_503 http_504 http_404 http_403;

		proxy_connect_timeout 3s; # Reduce connection timeout
		proxy_read_timeout 120s;   # Reduce read timeout
		proxy_send_timeout 10s;   # Reduce send timeout

		proxy_set_header X-Real-IP $$remote_addr;
		proxy_set_header Upgrade $$http_upgrade;
		proxy_set_header Connection "upgrade";

		# Remove conflicting Access-Control-Allow-Origin headers from upstream
		proxy_hide_header Access-Control-Allow-Origin;

		# Dynamically set Access-Control-Allow-Origin based on the Origin header
		if ($$http_origin ~* ^https?://(.*\.namada\.tududes\.com)$$) {
			add_header Access-Control-Allow-Origin $$http_origin always;
		}

		# Set additional CORS headers
		add_header Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE, PATCH" always;
		add_header Access-Control-Allow-Headers "Authorization, Content-Type, X-Requested-With" always;
		add_header Access-Control-Allow-Credentials true always;

		# Handle preflight OPTIONS requests
		if ($$request_method = OPTIONS) {
			add_header Access-Control-Allow-Origin $$http_origin always;
			add_header Access-Control-Allow-Methods "GET, POST, OPTIONS, PUT, DELETE, PATCH" always;
			add_header Access-Control-Allow-Headers "Authorization, Content-Type, X-Requested-With" always;
			add_header Access-Control-Allow-Credentials true always;
			return 204;
		}

		proxy_http_version 1.1;
		proxy_ssl_verify off;
	}
}
endef
export RPC_LB_SITE_CONTENTS


install: rpc-load-balancer do-install update


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


update:
	cd ${REPO_PATH} && sudo python3 update_endpoints.py /etc/nginx/sites-available/${RPC_LB_SITE_FILE} > ${REPO_PATH}/update.log 2>&1
	sudo nginx -t
	sudo systemctl reload nginx
	sleep 5
	# count the number of upstream servers and fire off curl requests to $RPC_LB_DOMAIN/block for each one
	export NUM_UPSTREAMS=$$(grep -c "server " /etc/nginx/sites-available/${RPC_LB_SITE_FILE}); \
	for i in $$(seq 1 $$NUM_UPSTREAMS); do \
		curl -s -k https://${RPC_LB_DOMAIN}/block; \
	done


cron: pull update push
	echo "Finished!"


cron-nogit: update
	echo "Finished without git!"


rpc-load-balancer:
	mkdir -p /etc/nginx/sites-available/
	@echo "$$RPC_LB_SITE_CONTENTS" | sudo tee /etc/nginx/sites-available/${RPC_LB_SITE_FILE}
