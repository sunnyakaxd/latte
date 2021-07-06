const fs = require('fs');
const path = require('path');
const redis = require('redis');
const bench_path = path.resolve(__dirname, '..', '..', '..');

function get_path(file_path) {
	return path.resolve(bench_path, file_path);
}

function get_conf() {
	// defaults
	const conf = {
		redis_async_broker_port: 12311,
		socketio_port: 3000
	};

	function read_config(file_path) {
		const full_path = path.resolve(bench_path, file_path);

		if (fs.existsSync(full_path)) {
			var bench_config = JSON.parse(fs.readFileSync(full_path));
			for (var key in bench_config) {
				if (bench_config[key]) {
					conf[key] = bench_config[key];
				}
			}
		}
	}

	// get ports from bench/config.json
	read_config('config.json');
	read_config('sites/common_site_config.json');

	// detect current site
	if (fs.existsSync('sites/currentsite.txt')) {
		conf.default_site = fs.readFileSync('sites/currentsite.txt').toString().trim();
	}

	return conf;
}

function get_redis_subscriber() {
	const conf = get_conf();
	const host = conf.redis_socketio || conf.redis_async_broker_port;
	return redis.createClient(host);
}

function get_redis_cache() {
	const conf = get_conf();
	const host = conf.redis_cache;
	return redis.createClient(host);
}

module.exports = {
	get_path,
	get_conf,
	get_redis_cache,
	get_redis_subscriber,
}
