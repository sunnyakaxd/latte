redis_cache: redis-server config/redis_cache.conf
#redis_big_cache: redis-server config/redis_big_cache.conf
redis_socketio: redis-server config/redis_socketio.conf
redis_queue_socket: redis-server config/redis_queue.conf
#web: bench serve --port 8002 --workers 2
openresty: ./apps/latte/bench.sh openresty --web-port 8000 --port-443 443 --port-80 80
web: ./apps/latte/bench.sh serve --bind-socket ../config/frappe-gunicorn.sock --workers 1
#mosquitto: mosquitto -p 8301
#mosquitto_client: ./apps/latte/bench.sh mqtt-client
#web_debug: bench server --port 8002 --debug --noreload
#web_async: bench serve --port 8100 --app latte.async_app:init_app --worker-class aiohttp.GunicornWebWorker --access-logformat simple_aio
#web_perf: bench serve --port 8008 --app perf
#socketio: node apps/frappe/socketio.js > /dev/null
socketio: nodemon --watch apps/latte/socketio --harmony --trace-warnings apps/latte/socketio/socketio.js

watch: ./apps/latte/bench.sh watch

worker_all: ./apps/latte/bench.sh worker --queue spine,long,short,default --enable-scheduler
#schedule: bench schedule
#worker_kafka0: ./apps/latte/bench.sh kafka-worker --partition-claim kafka0
#worker_kafka1: ./apps/latte/bench.sh kafka-worker --partition-claim kafka1
#worker_kafka2: ./apps/latte/bench.sh kafka-worker --partition-claim kafka2
#worker_host_kafka: ./apps/latte/bench.sh kafka-worker --hostnameclaim
#async_event_dispatcher: ./apps/latte/bench.sh --site site1.docker aio-eventdispatcher
