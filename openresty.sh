#!/bin/sh
docker ps -a | grep -q $1
CONTAINER_EXISTS=$?
if [ $CONTAINER_EXISTS -eq 0 ]; then
  echo -n "Found existing container for openresty. Cleaning up..."
  docker stop $1 && docker rm -f $1 >> /dev/null 2>&1
  echo "Done!"
fi

docker run \
  --name $1 \
  --mount source=$2,target=/usr/local/openresty/nginx/conf/nginx.conf,type=bind \
  --mount source=$3,target=/usr/local/openresty/nginx/conf/conf.d,type=bind \
  --mount source=$4,target=$4,type=bind \
  -p $5:8000 \
  -p $6:443 \
  -p $7:80 \
  openresty/openresty:1.17.8.2-alpine

#exec $4/apps/latte/bench.sh serve --bind-socket $4/config/frappe-gunicorn.sock --workers 1
