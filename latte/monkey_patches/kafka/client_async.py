from time import time
from kafka.client_async import KafkaClient

oldcheck_version = KafkaClient.check_version

def check_version(self, node_id=None, timeout=None, strict=False):
    if timeout is None:
        timeout = self.config['api_version_auto_timeout_ms'] / 1000
    return oldcheck_version(self, node_id=node_id, timeout=timeout, strict=strict)


KafkaClient.check_version = check_version