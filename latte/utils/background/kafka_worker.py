from zlib import decompress
import frappe

import sys
import signal
from kafka import KafkaConsumer, TopicPartition
from kafka.structs import OffsetAndMetadata
from kafka.errors import CommitFailedError
from itertools import chain

from zlib import decompress
from latte.utils.background.job import Task, fastrunner, get_kafka_queue_name
from latte.utils.linked_list import LinkedList
from math import ceil
import latte
import gevent
from gevent.signal import signal as handle_signal
import pickle
from gevent.lock import BoundedSemaphore as Lock
from redis import StrictRedis, ConnectionError

job_pool = Task.pool

# Runtime claim ID for this worker
PARTITION_CLAIM_ID = None
RUNNER_QUEUE_NAME = None

CLAIM_EXPIRY = 30

PROCESSING_MAP = {}

COMMIT_LOCK = Lock()

def start():
	print('Starting Kafka worker', PARTITION_CLAIM_ID)

	# claim id will be set by setting module variable by orchestrator
	if not PARTITION_CLAIM_ID:
		raise Exception('CLAIM ID NOT SET')

	if not RUNNER_QUEUE_NAME:
		raise Exception('RUNNER QUEUE NAME IS NOT SET')

	runner = gevent.spawn(poll_and_process)

	# handler to await task completion in case of SIGTERM/SIGINT
	def graceful_shutdown(*args, **kwargs):
		import traceback
		traceback.print_stack()
		# consumer and consumer.close()
		graceful = job_pool.join(timeout=10)
		print('Graceful Shutdown', graceful)
		print('Exiting')
		if not runner.dead:
			gevent.kill(runner)
		sys.exit(int(not graceful))

	handle_signal(signal.SIGHUP, graceful_shutdown)
	handle_signal(signal.SIGINT, graceful_shutdown)
	handle_signal(signal.SIGTERM, graceful_shutdown)
	runner.join()

def poll_and_process():
	consumer = None
	try:
		print('Creating Consumer')
		consumer = create_consumer()
		topic = get_kafka_queue_name(RUNNER_QUEUE_NAME)
		refresh_assignments(consumer)
		print(f'Consumer process {consumer} spawned')
		while True:
			COMMIT_LOCK.acquire()
			# print('POLLING')
			messages = list(chain(*(consumer.poll().values())))
			COMMIT_LOCK.release()
			# assignments = consumer.assignment()
			# print(len(messages), len(assignments), [row.partition for row in assignments])
			for msg in messages:
				job_meta = pickle.loads(decompress(msg.value))
				if not (log_flags := job_meta.get('log_flags')):
					log_flags = job_meta['log_flags'] = {}

				log_flags['partition_key'] = job_meta['partition_key']
				log_flags['partition'] = msg.partition

				task = Task(partition=msg.partition, **job_meta)
				try:
					PROCESSING_MAP[msg.partition].push((task, msg,))
				except KeyError:
					PROCESSING_MAP[msg.partition] = LinkedList((
						task, msg,
					))

			if not messages:
				gevent.sleep(5)
			else:
				running_partitions = [
					TopicPartition(topic, partition)
					for partition, queue in PROCESSING_MAP.items()
					if queue
				]
				# print('Pausing', running_partitions)
				COMMIT_LOCK.acquire()
				try:
					consumer.pause(*running_partitions)
				finally:
					COMMIT_LOCK.release()

			# print([key for key, value in PROCESSING_MAP.items() if value])
			# wait_for_clearance(consumer)
			spawn_runners(consumer)
	except Exception as e:
		handle_error(consumer, e)

# def wait_for_clearance(consumer):
# 	length = 1
# 	while (length):
# 		spawn_runners(consumer)
# 		gevent.sleep(5)
# 		length = sum(ll.length for ll in PROCESSING_MAP.values())

RUNNER_MAP = {}

def spawn_runners(consumer):
	for partition, partition_queue in PROCESSING_MAP.items():
		if not partition_queue:
			continue

		try:
			if RUNNER_MAP[partition].dead:
				raise KeyError
		except KeyError:
			# print('Runner spawning for', partition)
			RUNNER_MAP[partition] = job_pool.spawn(
				kafkarunner,
				consumer=consumer,
				partition=partition,
				partition_queue=partition_queue,
			)

RUNNING_PARTITION_LOCK_MAP = {}
PARTITION_MAP = {}

def acquire_partition_lock(partition):
	try:
		partitition_lock = RUNNING_PARTITION_LOCK_MAP[partition]
	except KeyError:
		partitition_lock = RUNNING_PARTITION_LOCK_MAP[partition] = Lock()

	partitition_lock.acquire()
	return partitition_lock

def is_claim_active(partition):
	cache = get_persistent_cache()
	claim_key = f'KafkaQueuePartititionClaim:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}:{partition}'
	claim_script = f'''
		if redis.call('get', '{claim_key}') == '{PARTITION_CLAIM_ID}'
		then
			redis.call('expire', '{claim_key}', {CLAIM_EXPIRY})
			return 1
		end
	'''
	return not not cache.eval(claim_script, 0)

class RebalancedException(Task.DontCatchMe):
	pass

class ActiveCheckFailed(Task.DontCatchMe):
	pass

def before_commit(task):
	try:
		claim_active = is_claim_active(task.flags.partition)
	except:
		print(frappe.get_traceback(), file=sys.stderr)
		raise ActiveCheckFailed()

	if not claim_active:
		raise RebalancedException()

def kafkarunner(consumer, partition, partition_queue):
	latte.init(site='')
	queue_name = get_kafka_queue_name(RUNNER_QUEUE_NAME)
	partitition_lock = acquire_partition_lock(partition)
	tp = TopicPartition(queue_name, partition)
	try:
		for task, msg in partition_queue:
			# if partition == 1:
			# print('Kafkarunner', partition, msg.offset, len(partition_queue))
			if not is_claim_active(partition):
				print('Clearing queue, lost partition', partition)
				partition_queue.clear()
				return

			try:
				fastrunner(
					task,
					before_commit=before_commit,
				)

			except RebalancedException:
				print('Commit Failed, Clearing queue, lost partition', partition)
				partition_queue.clear()
				return

			COMMIT_LOCK.acquire()
			try:
				consumer.commit({
					tp: OffsetAndMetadata(msg.offset + 1, None),
				})
				perf_log()

			except CommitFailedError:
				print('Rebalanced, Clearing partition queue', partition)
				partition_queue.clear()
				return

			finally:
				COMMIT_LOCK.release()

		COMMIT_LOCK.acquire()
		try:
			consumer.resume(tp)
		finally:
			COMMIT_LOCK.release()

	except Exception as e:
		handle_error(consumer, e)

	finally:
		partitition_lock.release()

cntr = 1
from time import perf_counter
init = perf_counter()

def perf_log():
	global cntr
	global init
	cntr += 1
	if cntr == 1000:
		print(perf_counter() - init)
		init = perf_counter()
		cntr = 0

def handle_error(consumer, e):
	print('Exception while processing', e)
	import traceback
	traceback.print_exc()
	try:
		consumer and consumer.close()
	except Exception as e:
		print('Failed to close consumer with error', e)

	print('###########################Exiting with error code#############', file=sys.stderr)
	sys.exit(1)

def create_consumer():
	latte.init(site='')
	DEFAULT = {
		'fetch_max_bytes': 1024 * 1024,
		'fetch_max_wait_ms': 20 * 1000,
		'max_partition_fetch_bytes': 50 * 1024,
		'enable_auto_commit': False,
		'session_timeout_ms': 30 * 1000,
		'api_version_auto_timeout_ms': 10 * 1000,
	}
	conf = frappe.local.conf.kafka_queue
	DEFAULT.update(conf)
	DEFAULT.pop('queue_prefix')
	consumer = KafkaConsumer(**DEFAULT)
	# consumer.subscribe(QUEUE_TOPIC_NAME, listener=RebalanceListener())
	return consumer

def get_member_set_name():
	return f'KafkaQueueConsumers:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}'

def get_leader_claim_key():
	return f'KafkaQueueLeader:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}'

# assigns topics for consumer
def refresh_assignments(consumer, old_assigner=None):
	try:
		old_assigner = refresh_assignments_wrapped(consumer, old_assigner)
	except ConnectionError as e:
		handle_error(consumer, e)
	except Exception:
		print(frappe.get_traceback())
	gevent.sleep(5)
	gevent.spawn(refresh_assignments, consumer=consumer, old_assigner=old_assigner)

def refresh_assignments_wrapped(consumer, old_assigner):
	cache = get_persistent_cache()
	leader_claim_key = get_leader_claim_key()

	# if claim is set, leadership is established
	am_i_leader = cache.set(leader_claim_key, PARTITION_CLAIM_ID, ex=CLAIM_EXPIRY, nx=True)

	# fetch the claim again in case leadership was not set
	if not am_i_leader:
		leader_claim = str(cache.get(leader_claim_key), 'utf-8')

		# If claim was previously set by this runtime, this runtime is still leading
		if leader_claim == PARTITION_CLAIM_ID:
			am_i_leader = True
	else:
		leader_claim = PARTITION_CLAIM_ID

	# Refresh leadership. Ensure it's not expired.
	if am_i_leader and not cache.expire(leader_claim_key, CLAIM_EXPIRY):
		# if expired, another leader will pick this task
		return

	# Spawn self topic assigner if old one is dead/not present
	if ((not old_assigner) or old_assigner.dead):
		assigner = gevent.spawn(wait_for_assignment, consumer, leader_claim, cache)
	else:
		# print('Old Assigner Alive')
		assigner = old_assigner

	# if leader, spawn assigner to assign topics to rest of the workers
	if am_i_leader:
		print('I am leader', PARTITION_CLAIM_ID)
		gevent.sleep(5)
		assign_partitions(cache)

	return assigner

def wait_for_assignment(consumer, leader_claim, cache):
	cache = get_persistent_cache()

	# tell leader i'm alive
	cache.sadd(get_member_set_name(), PARTITION_CLAIM_ID)

	# Set probe in redis so that leader can verify liveness
	cache.set(f'KafkaQueueConsumerProbe:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}:{PARTITION_CLAIM_ID}', 1, ex=CLAIM_EXPIRY)

	# Get leader claim
	leader_claim = str(cache.get(get_leader_claim_key()), 'utf-8')

	# wait for leader to push assignment and rebalances to corresponding redis lists
	ASSIGNMENT_KEY = f'KafkaQueuePartitionAssignment:{leader_claim}:{PARTITION_CLAIM_ID}'
	REBALANCE_KEY = f'KafkaQueuePartitionRebalance:{leader_claim}:{PARTITION_CLAIM_ID}'
	new_assignments = set()
	new_claims_partitions = {}
	to_remove_partitions = set()
	while True:
		next_assignment = cache.blpop([ASSIGNMENT_KEY, REBALANCE_KEY], timeout=10)
		if not next_assignment:
			break

		key = str(next_assignment[0], 'utf-8')
		value = str(next_assignment[1], 'utf-8')

		# End of assignment
		if value == 'END_OF_ASSIGNMENT':
			break


		if key == ASSIGNMENT_KEY:
			print('Got Partition', value)
			new_assignments.add(int(value))

		elif key == REBALANCE_KEY:
			# Prepare topics to send to new worker
			print('Rebalance', value)
			partition, new_claim = value.split(':')
			try:
				new_claims_partitions[new_claim].append(partition)
			except KeyError:
				new_claims_partitions[new_claim] = [partition]

			# and remove from own runtime
			to_remove_partitions.add(int(partition))

	# Rebalance this worker based on updated meta
	rebalance(consumer, cache, new_assignments, to_remove_partitions.union(set_my_partitions(consumer, cache)))

	# Assign removed partitions to new worker's list
	for new_claim, partitions in new_claims_partitions.items():
		for partition in partitions:
			cache.rpush(
				f'KafkaQueuePartitionAssignment:{leader_claim}:{new_claim}',
				partition,
			)
		cache.rpush(
			f'KafkaQueuePartitionAssignment:{leader_claim}:{new_claim}',
			'END_OF_ASSIGNMENT',
		)

'''
Checks if all partitions assigned to consumer are still valid as per leader's assignment
'''
def set_my_partitions(consumer, cache):
	to_remove = set()
	assignments = consumer.assignment()

	partition_claim_keys = [
		f'KafkaQueuePartititionClaim:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}:{tp.partition}'
		for tp in assignments
	]
	claims = partition_claim_keys and [
		partition_claim and str(partition_claim, 'utf-8')
		for partition_claim in cache.mget(partition_claim_keys)
	]

	to_expire = []
	for idx, tp in enumerate(assignments):
		if claims[idx] == PARTITION_CLAIM_ID:
			to_expire.append(partition_claim_keys[idx])
		else:
			print('Lost partition', tp.partition)
			to_remove.add(tp.partition)

	if to_expire:
		pipeline = cache.pipeline()
		for partition_claim_key in to_expire:
			pipeline.expire(partition_claim_key, CLAIM_EXPIRY)
		pipeline.execute()

	# for tp in consumer.assignment():
	# 	partition_claim_key = f'KafkaQueuePartititionClaim:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}:{tp.partition}'
	# 	partition_claim = cache.get(partition_claim_key)
	# 	partition_claim = partition_claim and str(partition_claim, 'utf-8')
	# 	if partition_claim == PARTITION_CLAIM_ID:
	# 		# Refresh expiry and claim
	# 		cache.expire(partition_claim_key, CLAIM_EXPIRY)
	# 	else:
	# 		print('Lost partition', tp.partition)
	# 		to_remove.add(tp.partition)

	return to_remove

def rebalance(consumer, cache, to_add=None, to_remove=None):
	to_add = to_add or set()
	to_remove = to_remove or set()
	assignments = {tp.partition for tp in consumer.assignment()}

	for partition in to_remove:
		# Remove all runners processing lost topics
		if runner := PROCESSING_MAP.pop(partition, None):
			lock = acquire_partition_lock(partition)
			runner.clear()
			lock.release()

	queue_name = get_kafka_queue_name(RUNNER_QUEUE_NAME)
	if to_add or to_remove:
		assignments = (assignments.union(to_add)) - to_remove
		print('To add', to_add)
		print('To remove', to_remove)

		consumer.assign([
			TopicPartition(topic=queue_name, partition=int(partition))
			for partition in assignments
		])

	if assignments:
		pipeline = cache.pipeline()
		for partition in assignments:
			partition_claim_key = f'KafkaQueuePartititionClaim:{queue_name}:{partition}'
			pipeline.set(partition_claim_key, PARTITION_CLAIM_ID, ex=CLAIM_EXPIRY)
		pipeline.execute()

def assign_partitions(cache):
	# Leader only execution, assigns partitions to other workers
	consumer = create_consumer()
	partitions = consumer.partitions_for_topic(get_kafka_queue_name(RUNNER_QUEUE_NAME))
	consumer.close()
	if not partitions:
		return

	member_set_name = get_member_set_name()
	consumers = cache.smembers(member_set_name)
	active_consumer_claims = []
	for claim in consumers:
		claim_id = str(claim, "utf-8")
		claim_alive = cache.get(f'KafkaQueueConsumerProbe:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}:{claim_id}')
		if claim_alive:
			active_consumer_claims.append(claim_id)
		else:
			cache.srem(member_set_name, claim_id)

	# print('Active Consumers', active_consumer_claims)

	partitions_to_assign = {
		partition for partition in partitions if
		cache.set(
			f'KafkaQueuePartititionClaim:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}:{partition}',
			'PendingAssignment',
			nx=True,
			ex=CLAIM_EXPIRY,
		)
	}
	# print('Partitions to assign', partitions_to_assign)

	assigned_partitions = list(partitions - partitions_to_assign)

	claim_partition_map = {}
	if assigned_partitions:
		assigned_partitions_keys = [
			f'KafkaQueuePartititionClaim:{get_kafka_queue_name(RUNNER_QUEUE_NAME)}:{partition}'
			for partition in assigned_partitions
		]
		for idx, claim in enumerate(cache.mget(list(assigned_partitions_keys))):
			claim = str(claim, 'utf-8')
			try:
				claim_partition_map[claim].append(assigned_partitions[idx])
			except KeyError:
				claim_partition_map[claim] = [assigned_partitions[idx]]

	total_consumers = len(active_consumer_claims)
	if not total_consumers:
		gevent.sleep(5)
		return
	ideal_length = ceil(len(partitions) / total_consumers)

	# print('Ideal Length', ideal_length)

	partitions_to_assign = list(partitions_to_assign)
	assigned_partitions_to_assign = {}

	active_consumer_claims.sort(
		key=lambda claim: len(claim_partition_map.get(claim, [])),
		reverse=True,
	)
	modified_claims = set()
	for idx, claim in enumerate(active_consumer_claims):
		try:
			claimed = claim_partition_map[claim]
		except KeyError:
			claimed = []

		while len(claimed) > ideal_length:
			partition = claimed.pop()
			assigned_partitions_to_assign[partition] = claim

		while (partitions_to_assign or assigned_partitions_to_assign):
			if idx < (len(active_consumer_claims) - 1) and len(claimed) >= ideal_length:
				break

			if partitions_to_assign:
				last_partition = partitions_to_assign.pop()
				print('Assign', last_partition, 'To', claim)
				cache.rpush(
					f'KafkaQueuePartitionAssignment:{PARTITION_CLAIM_ID}:{claim}',
					last_partition,
				)
				claimed.append(last_partition)
				modified_claims.add(claim)


			elif assigned_partitions_to_assign:
				last_partition, old_claim = assigned_partitions_to_assign.popitem()
				print('Rebalance', last_partition, 'From', old_claim, 'To', claim)
				cache.rpush(
					f'KafkaQueuePartitionRebalance:{PARTITION_CLAIM_ID}:{old_claim}',
					f'{last_partition}:{claim}',
				)

				claimed.append(last_partition)
				modified_claims.add(old_claim)

	for claim in modified_claims:
		cache.rpush(f'KafkaQueuePartitionAssignment:{PARTITION_CLAIM_ID}:{claim}', 'END_OF_ASSIGNMENT')

def get_persistent_cache():
	latte.init(site='')
	conf = frappe.local.conf
	persistent_cache_url = conf.persistent_redis_cache or conf.redis_cache or 'redis://localhost:13000'
	return StrictRedis.from_url(persistent_cache_url)
