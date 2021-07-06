# -*- coding: utf-8 -*-

import click
import os
import importlib
import sys
from watchgod import run_process
from functools import wraps
from distutils.spawn import find_executable
from latte.utils.caching import flushall as flushbigcache
from multiprocessing import cpu_count
import subprocess
from distutils.spawn import find_executable
import frappe
import latte
from uuid import uuid4


def get_env(overrides):
	env = os.environ.copy()
	env.pop('DEV_SERVER', None)
	env.update(overrides)
	return env

def pass_context(f):
	@wraps(f)
	def _func(ctx, *args, **kwargs):
		from latte import _dict
		return f(_dict(ctx.obj), *args, **kwargs)

	return click.pass_context(_func)

def get_site(context):
	try:
		site = context.sites[0]
		return site
	except (IndexError, TypeError):
		print('Please specify --site sitename')
		sys.exit(1)

def get_installed_apps():
	with open(os.path.abspath('./apps.txt')) as f:
		apps = [app for app in f.read().split('\n') if app]
	return apps

def patch_all():
	enqueued_patches = []
	for app in get_installed_apps():
		try:
			patches = importlib.import_module(f'{app}.monkey_patches')
			enqueued_patches += getattr(patches, 'ENQUEUED', [])
		except ModuleNotFoundError:
			print(f'No monkey_patches in {app}')
		else:
			print(f'Loaded monkey patches from app {app}')
	for patch in enqueued_patches:
		patch()

@click.command('patch-all')
def patch_all_command():
	patch_all()

def show_changes(changes):
	flushall()
	print(changes)

@click.command('worker')
@click.option('--queue', type=str)
@click.option('--noreload', 'no_reload', is_flag=True, default=False)
@click.option('--quiet', is_flag=True, default=False, help='Hide Log Outputs')
@click.option('--enable-scheduler', is_flag=True, default=False, help='Enable Scheduler')
def latte_worker(queue, quiet=False, no_reload=False, enable_scheduler=False):
	if not queue:
		raise Exception('Cannot run worker without queue')

	if no_reload:
		start_gevent_background_worker(queue, quiet, enable_scheduler)
	else:
		run_process(
			'../apps/',
			start_gevent_background_worker,
			args=(queue, quiet, enable_scheduler),
			min_sleep=4000,
			callback=show_changes,
		)

@click.command('gevent-worker')
@click.option('--queue', type=str)
@click.option('--noreload', 'no_reload',is_flag=True, default=False)
@click.option('--quiet', is_flag = True, default = False, help = 'Hide Log Outputs')
@click.option('--enable-scheduler', is_flag = True, default = False, help = 'Enable Scheduler')
def gevent_worker(queue, quiet=False, no_reload=False, enable_scheduler=False):
	if not queue:
		raise Exception('Cannot run worker without queue')
	if no_reload:
		start_gevent_background_worker(queue, quiet, enable_scheduler)
	else:
		run_process(
			'../apps/',
			start_gevent_background_worker,
			args=(queue, quiet, enable_scheduler),
			min_sleep=4000,
			callback=show_changes,
		)

def start_gevent_background_worker(queue, quiet, enable_scheduler):
	python_path = os.path.abspath('../env/bin/python')
	print('Starting gevent background worker for', queue)

	os.execve(python_path, [
		python_path,
		'-u',
		'-c',
		'\n'.join(line.strip() for line in f'''
			from gevent import monkey
			monkey.patch_all()
			from latte.commands.utils import patch_all
			patch_all()
			from latte.utils.background.gevent_worker import start
			start(queues="{queue}", enable_scheduler={enable_scheduler})
		'''.split('\n'))
	], get_env({'GEVENT_RESOLVER': 'ares',
				'PATCH_WERKZEUG_LOCAL': 'YES'}))

@click.command('kafka-worker')
@click.option('--noreload', 'no_reload', is_flag=True, default=False)
@click.option('--partition-claim', 'partition_claim', default=str(uuid4()))
@click.option('--hostnameclaim', 'hostnameclaim', is_flag=True, default=False)
@click.option('--queue', 'queue', default='')
def kafka_worker(partition_claim, no_reload=False, hostnameclaim=False, queue=''):
	queue = queue or os.environ.get('KAFKA_QUEUE_NAME') or 'default'
	if hostnameclaim:
		import socket
		partition_claim = socket.gethostname()

	if no_reload:
		start_kafka_background_worker(partition_claim, queue)
	else:
		run_process(
			'../apps/',
			start_kafka_background_worker,
			kwargs={
				'partition_claim': partition_claim,
				'queue': queue,
			},
			min_sleep=4000,
			callback=show_changes,
		)

def start_kafka_background_worker(partition_claim, queue):
	python_path = os.path.abspath('../env/bin/python')
	print('Initialising Kafka Worker for', partition_claim)

	os.execve(python_path, [
		python_path,
		'-u',
		'-c',
		'\n'.join(line.strip() for line in f'''
			from gevent import monkey
			monkey.patch_all()
			from latte.commands.utils import patch_all
			patch_all()
			import latte.utils.background.kafka_worker
			latte.utils.background.kafka_worker.PARTITION_CLAIM_ID = '{partition_claim}'
			latte.utils.background.kafka_worker.RUNNER_QUEUE_NAME = '{queue}'
			print('Claim=', latte.utils.background.kafka_worker.PARTITION_CLAIM_ID)
			latte.utils.background.kafka_worker.start()
		'''.split('\n'))
	], get_env({
		'GEVENT_RESOLVER': 'ares',
		'PATCH_WERKZEUG_LOCAL': 'YES',
	}))


LOG_FORMATS = {
	'json': ' '.join('''
		{
			"remote_ip":"%(h)s",
			"request_id":"%({X-Request-Id}i)s",
			"response_code":%(s)s,
			"request_method":"%(m)s",
			"request_path":"%(U)s",
			"request_querystring":"%(q)s",
			"request_timetaken":%(D)s,
			"response_length":%(B)s
		}
	'''.split('\n')),
	'simple': '%(m)s %(U)s %(q)s := %(s)s | %(D)s | %(B)s',
	'json_aio': ' '.join('''
		{
			"remote_ip":"%a",
			"request_id":"%{X-Request-Id}i",
			"response_code":%s,
			"request_path":"%r",
			"request_timetaken":%T,
			"response_length":%b
		}
	'''.split('\n')),
	'simple_aio': '%a %r := %s | %T | %b',
}

@click.command('mqtt-client')
@click.option('--noreload', "no_reload", is_flag=True, default=False)
def mqtt_client(no_reload=False):
	if no_reload:
		start_mqtt_worker()
	else:
		run_process(
			'../apps/',
			start_mqtt_worker,
			min_sleep=4000,
			callback=show_changes,
		)

def start_mqtt_worker():
	python_path = os.path.abspath('../env/bin/python')
	print('Initialising MQTT Worker')
	mqtt_path = os.path.abspath('../apps/latte/start_mqtt.py')
	os.execve(
		python_path,
		[
			python_path,
			'-u',
			mqtt_path,
		]
	, get_env({
		'GEVENT_RESOLVER': 'ares',
		'PATCH_WERKZEUG_LOCAL': 'YES',
	}))

@click.command('serve')
@click.option('--host', default='0.0.0.0')
@click.option('--port', default=8000)
@click.option('--bind-socket', default=None)
@click.option('--workers', default=cpu_count())
@click.option('--worker-connections', default=50)
@click.option('--worker-class', default='gevent')
@click.option('--app', default='latte.app:application')
@click.option('--access-logfile', default='-')
@click.option('--access-logformat', default='simple')
@click.option('--noreload', "no_reload", is_flag=True, default=False)
@click.option('--debug', "is_debug", is_flag=True, default=False)
def serve(
	host=None, port=None, bind_socket=None,
	workers=2, worker_connections=50, worker_class='',
	app='',
	access_logfile=None, access_logformat=None, profile=False, no_reload=False,
	sites_path='.', site=None, is_debug=False
	):

	args = (
		host, port, bind_socket,
		workers, worker_connections, worker_class,
		app,
		access_logfile, access_logformat, profile,
		sites_path, site, is_debug
	)
	if no_reload:
		start_web_worker(*args)
	else:
		run_process(
			'../apps/',
			start_web_worker,
			args=args,
			min_sleep=4000,
			callback=show_changes,
		)

def start_web_worker(host, port, bind_socket,
	workers, worker_connections, worker_class,
	app,
	access_logfile, access_logformat, profile, sites_path, site, is_debug):
	guni_path = os.path.abspath('../apps/latte/start_guni.py')
	python_path = os.path.abspath('../env/bin/python')
	print('Starting latte patched server at', guni_path)
	# Added to enable local debugging of applications using tools like VSCode/PyCharm
	# Enable --debug in local process parameters for bench serve to use with debugger.
	if is_debug:
		worker_class = "sync"
		workers = 1
		worker_connections = 1

	additional_flags = [
		'-w', f'{workers}',
		'--worker-connections', f'{worker_connections}',
		app,
		'-k', worker_class,
		'-t', '120',
	]
	print('ADDITIONALFLAGS', additional_flags)

	print(bind_socket)
	if bind_socket:
		additional_flags += ['-b', f'unix://{bind_socket}']
	elif port:
		host = host or '0.0.0.0'
		additional_flags += ['-b', f'{host}:{port}']

	if access_logfile:
		additional_flags += ['--access-logfile', '-',]

	access_logformat = LOG_FORMATS.get(access_logformat, access_logformat)

	additional_flags += ['--access-logformat', access_logformat,]

	if not is_debug:
		os.execve(
			python_path,
			[
				python_path,
				'-u',
				guni_path,
			] + additional_flags
		, get_env({
			'GEVENT_RESOLVER': 'ares',
			'PATCH_WERKZEUG_LOCAL': 'YES',
		}))
	else:
		sys.argv = sys.argv[0:1] + additional_flags
		print(sys.argv)
		from gunicorn.app.wsgiapp import run
		sys.exit(run())

@click.command('kafka')
@click.option('--zk_port')
@click.option('--broker_port')
def kafka(zk_port, broker_port):
	print("Starting kafka...")
	latte.init(site='')
	if not zk_port:
		if frappe.local.conf.kafka.get("zk_port"):
			zk_port = frappe.local.conf.kafka.get("zk_port")
		else:
			zk_port = 2181
	if not broker_port:
		if frappe.local.conf.kafka.get("broker_port"):
			broker_port = frappe.local.conf.kafka.get("broker_port")
		else:
			broker_port = 10180
	docker_url = ['dock.elasticrun.in/kafka-dev']
	additional_flags = [f'-p{zk_port}',f'-p{broker_port}'] + docker_url
	os.execv('/usr/bin/docker',['/usr/bin/docker','run'] + additional_flags)

@click.command('console')
@pass_context
def console(context):
	"Start ipython console for a site"
	from latte import _dict
	site = get_site(context)
	ipython_path = os.path.abspath('../env/bin/ipython')
	os.execve(ipython_path, [
		ipython_path,
		'-i',
		'../apps/latte/ipython_loader.py'
	], _dict(os.environ).update({
		'site': site,
		'GEVENT_RESOLVER': 'ares',
		'PATCH_WERKZEUG_LOCAL': 'YES',
	}))

@click.command('processlist')
@click.option('--full', is_flag=True, default=False)
@pass_context
def processlist(context, full):
	import frappe, latte
	site = get_site(context)
	latte.init(site=site)
	from frappe.commands.utils import find_executable
	mysql = find_executable('mysql')
	os.execv(mysql, [
		mysql,
		'-u',
		frappe.conf.db_name,
		f'-p{frappe.conf.db_password}',
		'--host',
		frappe.local.conf.db_host or '127.0.0.1',
		'-e',
		f'show {"full" if full else ""} processlist'
	])

def flushall():
	import latte, frappe
	from redis import ConnectionError
	latte.init(site='')
	# print('Flushing redis cache')
	flushbigcache()

@click.command('schedule')
@click.option('--noreload', 'no_reload', is_flag=True, default=False)
def start_scheduler(no_reload=None):
	if no_reload:
		watched_start_scheduler()
	else:
		run_process(
			'../apps/',
			watched_start_scheduler,
			min_sleep=4000,
			callback=show_changes,
		)

@click.command('mariadb')
@pass_context
def mariadb(context):
	"""
		Enter into mariadb console for a given site.
	"""
	import os, frappe, latte

	site  = get_site(context)
	latte.init(site=site)
	host = frappe.conf.db_host or '127.0.0.1'
	port = frappe.conf.db_port or 3306
	user = frappe.conf.db_user or frappe.conf.db_name
	password = frappe.conf.db_password
	db_name = frappe.conf.db_name

	# This is assuming you're within the bench instance.
	mysql = find_executable('mysql')
	os.execv(mysql, [
		mysql,
		'-u', user,
		f"-p{password}",
		'--host', host,
		'--port', str(port),
		"-A",
		db_name,
	])

def watched_start_scheduler():
	python_path = os.path.abspath('../env/bin/python')
	print('Starting scheduler')

	os.execv(python_path, [
		python_path,
		'-c',
		'\n'.join(line.strip() for line in f'''
			from gevent import monkey
			monkey.patch_all()
			from latte.commands.utils import patch_all
			patch_all()
			from latte.utils.scheduler import start_scheduler
			start_scheduler()
		'''.split('\n'))
	])

@click.command('jupyter')
@pass_context
def jupyter(context):
	try:
		from pip import main
	except ImportError:
		from pip._internal import main

	reqs = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'])
	installed_packages = [r.decode().split('==')[0] for r in reqs.split()]
	if 'jupyter' not in installed_packages:
		main(['install', 'jupyter'])
	site = get_site(context)
	latte.init(site=site)
	jupyter_notebooks_path = os.path.abspath(frappe.get_site_path('jupyter_notebooks'))
	sites_path = os.path.abspath(frappe.get_site_path('..'))
	try:
		os.stat(jupyter_notebooks_path)
	except OSError:
		print('Creating folder to keep jupyter notebooks at {}'.format(jupyter_notebooks_path))
		os.mkdir(jupyter_notebooks_path)
	bin_path = os.path.abspath('../env/bin')
	print(f'''
Starting Jupyter notebook
Run the following in your first cell to connect notebook to frappe
```
import latte, os, frappe
os.chdir("{sites_path}")
from latte.commands.utils import patch_all
patch_all()
latte.init(site='{site}', sites_path='{sites_path}')
latte.connect()
frappe.local.lang = frappe.db.get_default('lang')
frappe.db.connect()
```

	''')
	os.execve('{0}/jupyter'.format(bin_path), [
		'{0}/jupyter'.format(bin_path),
		'notebook',
		jupyter_notebooks_path,
	], get_env({
		# 'PATCH_WERKZEUG_LOCAL': 'YES',
	}))

@click.command('auto-incr')
@click.option('--dt')
@pass_context
def autoincrement(context, dt):
	site = get_site(context)
	latte.init(site=site)
	latte.connect()
	from latte.latte_core.naming.auto_increment import migrate
	migrate(dt)

@click.command('setup-openresty')
@click.option('--override', is_flag=True, default=False)
def setup_openresty(override):
	import shutil
	from latte.utils.file_ops import read, write
	from jinja2 import Environment
	if os.path.exists('../config/latte-openresty'):
		if (not override):
			while (yes := input('Openresty is already configured. Overwrite? (y/n)').lower()) not in ('y', 'n'):
				if yes == 'n':
					return

	os.makedirs('../config/latte-openresty/conf.d', exist_ok=True)
	openresty_path = os.path.abspath('../apps/latte/openresty/')
	bench_path = os.path.abspath('../')
	config_path = f'{bench_path}/config/latte-openresty'
	jinjaenv = Environment()
	ctx = {
		'BENCH_FOLDER': bench_path,
	}
	conf = jinjaenv.from_string(read(f'{openresty_path}/conf.d/latte-nginx.conf')).render(ctx)
	write(f'{config_path}/conf.d/latte-nginx.conf', conf)
	shutil.copy(f'{openresty_path}/main-nginx.conf', f'{config_path}/main-nginx.conf')
	shutil.copy(f'{openresty_path}/conf.d/proxy-handler.lua', f'{config_path}/conf.d/proxy-handler.lua')

@click.command('openresty')
@click.option('--docker-name', default='latte-openresty')
@click.option('--web-port', default='8000')
@click.option('--port-443', default='8443')
@click.option('--port-80', default='8080')
def start_openresty(docker_name, web_port, port_443, port_80):
	shell_file = os.path.abspath('../apps/latte/openresty.sh')
	nginx_conf = os.path.abspath('../config/latte-openresty/main-nginx.conf')
	frappe_conf = os.path.abspath('../config/latte-openresty/conf.d')
	bench_path = os.path.abspath('..')
	os.execve(shell_file, [
		shell_file,
		docker_name,
		nginx_conf,
		frappe_conf,
		bench_path,
		web_port,
		port_443,
		port_80,
	], get_env({

	}))


@click.command('execute')
@click.argument('method')
@click.option('--args')
@click.option('--kwargs')
@pass_context
def execute(context, method, args=None, kwargs=None, profile=False):
	"Execute a function"
	patch_all()
	import json
	from frappe.utils.response import json_handler
	for site in context.sites:
		try:
			latte.init(site=site)
			latte.connect()

			if args:
				try:
					args = eval(args)
				except NameError:
					args = [args]
			else:
				args = ()

			if kwargs:
				kwargs = eval(kwargs)
			else:
				kwargs = {}

			frappe.local.flags.request_id = frappe.local.flags.task_id = 'bench-execute'
			ret = frappe.get_attr(method)(*args, **kwargs)

			if frappe.db:
				frappe.db.commit()
		finally:
			latte.destroy()
		if ret:
			print(json.dumps(ret, default=json_handler))

@click.command('export-fixtures')
@pass_context
def export_fixtures(context):
	"Export fixtures"
	from frappe.utils.fixtures import export_fixtures
	for site in context.sites:
		try:
			latte.init(site=site)
			latte.connect()
			export_fixtures()
		finally:
			latte.destroy()

@click.command('migrate')
@click.option('--verbose', default=True)
@click.option('--rebuild-website', default=False)
@pass_context
def migrate(context, verbose=True, rebuild_website=False):
	from frappe.migrate import migrate
	patch_all()
	for site in context.sites:
		try:
			latte.init(site=site)
			latte.connect()
			migrate(verbose=verbose, rebuild_website=rebuild_website)
			frappe.db.commit()
		finally:
			latte.destroy()

@click.command('new-site')
@click.argument('site')
@click.option('--db-name', help='Database name')
@click.option('--mariadb-root-username', default='root', help='Root username for MariaDB')
@click.option('--mariadb-root-password', help='Root password for MariaDB')
@click.option('--admin-password', help='Administrator password for new site', default=None)
@click.option('--verbose', is_flag=True, default=False, help='Verbose')
@click.option('--force', help='Force restore if site/database already exists', is_flag=True, default=False)
@click.option('--reinstall', help='Force restore if site/database already exists', is_flag=True, default=False)
@click.option('--source_sql', help='Initiate database with a SQL file')
@click.option('--install-app', multiple=True, help='Install app after installation')
def new_site(site, mariadb_root_username=None, mariadb_root_password=None, admin_password=None,
	verbose=False, install_apps=None, source_sql=None, force=None, install_app=None, db_name=None, reinstall=False):
	"Create a new site"
	patch_all()
	latte.init(site=site, new_site=True)

	from frappe.commands.site import _new_site, use

	_new_site(db_name, site, mariadb_root_username=mariadb_root_username, mariadb_root_password=mariadb_root_password, admin_password=admin_password,
			verbose=verbose, install_apps=install_app, source_sql=source_sql, force=force, reinstall=reinstall)

	if len(frappe.utils.get_sites()) == 1:
		use(site)

@click.command('install-app')
@click.argument('app')
@pass_context
def install_app(context, app):
	"Install a new app to site"
	patch_all()
	from frappe.installer import install_app as _install_app
	for site in context.sites:
		latte.init(site=site)
		latte.connect()
		try:
			_install_app(app, verbose=context.verbose)
		finally:
			latte.destroy()

@click.command('list-apps')
@pass_context
def list_apps(context):
	"List apps in site"
	patch_all()
	site = get_site(context)
	latte.init(site=site)
	latte.connect()
	print("\n".join(frappe.get_installed_apps()))
	latte.destroy()


@click.command('clear-cache')
@pass_context
def clear_cache(context):
	"Clear cache, doctype cache and defaults"
	patch_all()
	import frappe.sessions
	import frappe.website.render
	from frappe.desk.notifications import clear_notifications
	for site in context.sites:
		try:
			latte.connect(site)
			frappe.clear_cache()
			clear_notifications()
			frappe.website.render.clear_cache()
		finally:
			frappe.destroy()

@click.command('clear-website-cache')
@pass_context
def clear_website_cache(context):
	"Clear website cache"
	patch_all()
	import frappe.website.render
	for site in context.sites:
		try:
			latte.init(site=site)
			latte.connect()
			frappe.website.render.clear_cache()
		finally:
			frappe.destroy()

@click.command('destroy-all-sessions')
@click.option('--reason')
@pass_context
def destroy_all_sessions(context, reason=None):
	"Clear sessions of all users (logs them out)"
	patch_all()
	import frappe.sessions
	for site in context.sites:
		try:
			latte.init(site=site)
			latte.connect()
			frappe.sessions.clear_all_sessions(reason)
			frappe.db.commit()
		finally:
			frappe.destroy()

commands = [
	clear_cache,
	clear_website_cache,
	destroy_all_sessions,
	setup_openresty,
	start_openresty,
	autoincrement,
	latte_worker,
	gevent_worker,
	kafka_worker,
	mqtt_client,
	serve,
	console,
	processlist,
	kafka,
	start_scheduler,
	mariadb,
	patch_all_command,
	jupyter,
	execute,
	export_fixtures,
	migrate,
	new_site,
	install_app,
	list_apps,
]
