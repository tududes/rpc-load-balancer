SHELL=/usr/bin/env bash

ifndef GIT_ORG
GIT_ORG=0LNetworkCommunity
endif

ifndef GIT_REPO
GIT_REPO=rpc-load-balancer-v5
endif

ifndef REPO_PATH
REPO_PATH=~/${GIT_REPO}
endif

ifndef RPC_LB_DOMAIN
RPC_LB_DOMAIN=testnet-rpc.openlibra.space
endif

ifndef RPC_LB_DOMAIN_V5
RPC_LB_DOMAIN_V5=mainnet-v5-rpc.openlibra.space
endif


ifndef RPC_LB_SITE_FILE
RPC_LB_SITE_FILE=rpc-load-balancer
endif

ifndef RPC_LB_SITE_FILE_V5
RPC_LB_SITE_FILE_V5=rpc-load-balancer-v5
endif


define RPC_LB_SITE_CONTENTS
upstream fullnodes {
	server 127.0.0.1:8080;
}

server {
	listen 80;
	server_name ${RPC_LB_DOMAIN};
	return 301 https://$$host$$request_uri;
}

server {
	listen 8080 ssl;
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


define RPC_LB_SITE_CONTENTS_V5
upstream fullnodesv5 {
	server 127.0.0.1:8080;
}

server {
	listen 80;
	server_name ${RPC_LB_DOMAIN_V5};
	return 301 https://$$host$$request_uri;
}

server {
	listen 8080 ssl;
	server_name ${RPC_LB_DOMAIN_V5};

	ssl_certificate /etc/letsencrypt/live/${RPC_LB_DOMAIN_V5}/fullchain.pem;
	ssl_certificate_key /etc/letsencrypt/live/${RPC_LB_DOMAIN_V5}/privkey.pem;
	ssl_verify_client optional;

	location / {
		proxy_pass http://fullnodesv5;
		proxy_set_header Host $$host;
		proxy_set_header X-Real-IP $$remote_addr;
		proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $$scheme;
	}
}

server {
	listen 8081 ssl;
	server_name ${RPC_LB_DOMAIN_V5};

	location / {
		proxy_pass http://fullnodesv5;
		proxy_set_header Host $$host;
		proxy_set_header X-Real-IP $$remote_addr;
		proxy_set_header X-Forwarded-For $$proxy_add_x_forwarded_for;
		proxy_set_header X-Forwarded-Proto $$scheme;
	}
}
endef
export RPC_LB_SITE_CONTENTS_V5


install: rpc-load-balancer
	sudo apt install -y python3 nginx nginx-common nginx-full
	sudo ln -sf /etc/nginx/sites-available/${RPC_LB_SITE_FILE} /etc/nginx/sites-enabled/${RPC_LB_SITE_FILE}
	sudo systemctl reload nginx
	sudo apt install certbot python3-certbot-nginx
	sudo certbot certonly --manual --preferred-challenges=dns --server https://acme-v02.api.letsencrypt.org/directory --domain ${RPC_LB_DOMAIN}
	sudo systemctl reload nginx


install-v5: rpc-load-balancer-v5
	sudo apt install -y python3 nginx nginx-common nginx-full
	sudo ln -sf /etc/nginx/sites-available/${RPC_LB_SITE_FILE_V5} /etc/nginx/sites-enabled/${RPC_LB_SITE_FILE_V5}
	sudo systemctl reload nginx
	sudo apt install certbot python3-certbot-nginx
	sudo certbot certonly --manual --preferred-challenges=dns --server https://acme-v02.api.letsencrypt.org/directory --domain ${RPC_LB_DOMAIN_V5}
	sudo systemctl reload nginx


pull:
	cd ${REPO_PATH} && git pull


push:
	cd ${REPO_PATH} && git add -A && git commit -m "rpc health check" && git push 


update:
	cd ${REPO_PATH} && sudo python3 update_endpoints.py /etc/nginx/sites-available/${RPC_LB_SITE_FILE} > ${REPO_PATH}/update.log 2>&1
	sudo nginx -t
	sudo systemctl reload nginx


update-v5:
	cd ${REPO_PATH} && sudo python3 update_endpoints.py /etc/nginx/sites-available/${RPC_LB_SITE_FILE_V5} > ${REPO_PATH}/update.log 2>&1
	sudo nginx -t
	sudo systemctl reload nginx


cron: pull update push
	echo "Finished!"


cron-v5: pull update-v5 push
	echo "Finished!"


cron-nogit: update
	echo "Finished without git!"


cron-nogit-v5: update-v5
	echo "Finished without git!"


rpc-load-balancer:
	@echo "$$RPC_LB_SITE_CONTENTS" | sudo tee /etc/nginx/sites-available/${RPC_LB_SITE_FILE}

rpc-load-balancer-v5:
	@echo "$$RPC_LB_SITE_CONTENTS_V5" | sudo tee /etc/nginx/sites-available/${RPC_LB_SITE_FILE_V5}
