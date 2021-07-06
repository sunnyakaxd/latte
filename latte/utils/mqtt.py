from frappe import local
from paho.mqtt.publish import single as publish_single_mqtt_message

def publish_mqtt(topic, payload):
	mqtt_conf = local.conf.mqtt_conf
	broker_host = mqtt_conf['broker']
	broker_port = mqtt_conf['port']

	publish_single_mqtt_message(
		topic,
		payload,
		hostname=broker_host,
		port=broker_port,
	)
