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
upstream fullnodes {
	server 127.0.0.1:443;
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
		proxy_pass http://fullnodes;
		proxy_set_header Host $$host;
		proxy_set_header X-Real-IP $$remote_addr;
		proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $$scheme;
	}
}
endef
export RPC_LB_SITE_CONTENTS


install: rpc-load-balancer
	sudo apt install -y python3 nginx nginx-common nginx-full
	sudo ln -sf /etc/nginx/sites-available/${RPC_LB_SITE_FILE} /etc/nginx/sites-enabled/${RPC_LB_SITE_FILE}
	sudo apt install certbot python3-certbot-nginx -y
	sudo certbot certonly --manual --preferred-challenges=dns --server https://acme-v02.api.letsencrypt.org/directory --domain ${RPC_LB_DOMAIN}
	sudo systemctl reload nginx


pull:
	cd ${REPO_PATH} && git pull


push:
	cd ${REPO_PATH} && git add -A && git commit -m "rpc health check" && git push 


update:
	cd ${REPO_PATH} && sudo python3 update_endpoints.py /etc/nginx/sites-available/${RPC_LB_SITE_FILE} > ${REPO_PATH}/update.log 2>&1
	sudo nginx -t
	sudo systemctl reload nginx


cron: pull update push
	echo "Finished!"


cron-nogit: update
	echo "Finished without git!"


rpc-load-balancer:
	mkdir -p /etc/nginx/sites-available/
	@echo "$$RPC_LB_SITE_CONTENTS" | sudo tee /etc/nginx/sites-available/${RPC_LB_SITE_FILE}
