import frappe
from kafka import KafkaConsumer, TopicPartition
from kafka import KafkaAdminClient
from kafka.admin import NewPartitions
from latte.utils.caching import cache_me_if_you_can
from latte.utils.background.kafka_worker import (
	get_persistent_cache,
	get_kafka_queue_name
)

def get_consumer(bootstrap_server):
	conf = frappe.local.conf.kafka_queue

	client_id = conf['client_id']
	group_id = conf['group_id']

	consumer = KafkaConsumer(
		bootstrap_servers=bootstrap_server,
		client_id=f'{client_id}-monitor',
		group_id=f'{group_id}-monitor',
		enable_auto_commit=False,
		api_version_auto_timeout_ms=conf.get('api_version_auto_timeout_ms', 10000),
	)
	return consumer


def get_admin_client(bootstrap_server):
	conf = frappe.local.conf.kafka_queue
	client = KafkaAdminClient(
		bootstrap_servers=bootstrap_server,
		api_version_auto_timeout_ms=conf.get('api_version_auto_timeout_ms', 10000),
	)
	return client

@frappe.whitelist()
@cache_me_if_you_can(expiry=30)
def get_smembers():
	cache = get_persistent_cache()
	member_sets = [str(v, 'utf-8') for v in cache.keys('KafkaQueueConsumers:*')]
	leader_keys = [str(v, 'utf-8') for v in cache.keys('KafkaQueueLeader:*')]
	leaders = {
		str(value, 'utf-8'): leader_keys[idx]
		for idx, value in enumerate(cache.mget(leader_keys))
	} if leader_keys else {}

	retval = {}
	prefix = get_kafka_queue_name('')
	for member in member_sets:
		queue = member.split(prefix)[-1]
		for name in cache.smembers(member):
			name = str(name, 'utf-8')
			retval[name] = {
				'name': name,
				'leader': int(not not leaders.get(name)),
				'queue': queue,
			}
	return retval

@frappe.whitelist()
def get_consumer_meta(bootstrap_server, consumer_name):
	cache = get_persistent_cache()
	queue = get_smembers().get(consumer_name)['queue']
	partitions = [
		str(row, 'utf-8')
		for row in
		cache.keys(f'KafkaQueuePartititionClaim:{get_kafka_queue_name(queue)}:*')
	]
	my_partitions = partitions and {
		int(partitions[idx].rsplit(':', 1)[-1])
		for idx, row in
		enumerate(cache.mget(partitions))
		if row == consumer_name.encode()
	}

	consumer_group = frappe.local.conf.kafka_queue['group_id']
	return partitions and [row for row in get_consumer_group_meta(
		bootstrap_server,
		topic=get_kafka_queue_name(queue),
		cg=consumer_group,
	) if row['partition'] in my_partitions]

@frappe.whitelist()
def create_partitions(bootstrap_server, topic, total):
	frappe.only_for(['System Manager', 'Developer'])
	client = get_admin_client(bootstrap_server)
	new_partitions = NewPartitions(
		total_count=int(total),
	)
	client.create_partitions({
		topic: new_partitions
	})
	frappe.msgprint(f'Increasing partitions to {total} for topic {topic}')

@frappe.whitelist()
def get_consumer_groups(bootstrap_server):
	frappe.only_for(['System Manager', 'Developer'])
	return [cg[0] for cg in get_admin_client(bootstrap_server).list_consumer_groups() if 'latte' in cg[0]]

def get_consumer_group_meta_wrapped(bootstrap_server, cg, topic=None):
	# frappe.only_for(['System Manager', 'Developer'])
	consumer = get_consumer(bootstrap_server)

	tps = []
	if topic:
		partitions_for_topic = consumer.partitions_for_topic(topic)
		if not partitions_for_topic:
			return []

		tps = [
			TopicPartition(topic=topic, partition=partition)
			for partition in partitions_for_topic
		] if topic else []

	client = get_admin_client(bootstrap_server)
	topic_meta = {
		tp: {
			'topic': tp.topic,
			'partition': tp.partition,
			'cg_offset': meta.offset
		}
		for tp, meta in client.list_consumer_group_offsets(cg).items()
	}
	for tp in tps:
		if tp not in topic_meta:
			topic_meta[tp] = {
				'topic': tp.topic,
				'partition': tp.partition,
				'cg_offset': 0,
			}

	if not topic_meta:
		return []

	consumer.assign(list(topic_meta))
	consumer.seek_to_end(*list(topic_meta))
	for tp, meta in topic_meta.items():
		end = consumer.position(tp) or 0
		meta['offset'] = end
		meta['lag'] = end - meta['cg_offset']

	resp = list(topic_meta.values())
	return sorted(resp, key=lambda x:(x['topic'], x['partition']))

get_consumer_group_meta = frappe.whitelist()(
	cache_me_if_you_can(
		expiry=1,
		build_expiry=100
	)(get_consumer_group_meta_wrapped)
)

@frappe.whitelist()
def get_topics(bootstrap_server):
	frappe.only_for(['System Manager', 'Developer'])
	return [topic for topic in get_consumer(bootstrap_server).topics() if 'latte' in topic]

@frappe.whitelist()
@cache_me_if_you_can(expiry=1, build_expiry=100)
def get_topic_meta(bootstrap_server, topic, cg=None):
	frappe.only_for(['System Manager', 'Developer'])
	consumer = get_consumer(bootstrap_server)
	tps = {
		TopicPartition(topic=topic, partition=partition): None
		for partition in consumer.partitions_for_topic(topic)
	}
	consumer.assign(tps)
	consumer.seek_to_beginning(*tps)
	for tp in tps:
		tps[tp] = {
			'partition': tp.partition,
			'start': consumer.position(tp),
		}
	consumer.seek_to_end(*list(tps))
	for tp, meta in tps.items():
		end = consumer.position(tp)
		meta['end'] = end
		if not meta['start']:
			meta['total_messages'] = end
		else:
			meta['total_messages'] = end - meta['start'] + 1

	consumer.close()
	resp = list(tps.values())
	resp.append({
		'partition': f'Total: {len(resp)}',
		'total_messages': f'Total: {sum(i["total_messages"] for i in resp)}',
	})
	return resp

@frappe.whitelist()
def get_bootstrap_server():
	frappe.only_for(['System Manager', 'Developer'])
	if conf := frappe.local.conf.kafka_queue:
		return conf['bootstrap_servers']