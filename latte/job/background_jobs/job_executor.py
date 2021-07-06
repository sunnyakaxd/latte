import frappe
from latte.job.doctype.job.job import Job_status

def get_all_pending_jobs():
    pending_jobs = frappe.get_all("Job", fields={'name', "retry_count", "max_retries"}, filters = [["status","=","Pending"]])
    valid_jobs = [job.name for job in pending_jobs if job.retry_count < job.max_retries]
    return valid_jobs

def job_executor():
    pending_jobs = get_all_pending_jobs()
    for pending_job_name in pending_jobs:
        pending_job = frappe.get_doc("Job", pending_job_name)
        pending_job.update_status(Job_status.PROCESSING.value)
        pending_job.execute()
