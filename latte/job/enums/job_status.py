from enum import Enum

class Job_status(Enum):
	PENDING = "Pending"
	PROCESSING = "Processing"
	SUCCESS = "Success"
	FAILURE = "Failure"
