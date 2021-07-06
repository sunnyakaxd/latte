import frappe
from latte.job.enums.job_status import Job_status

class Helper(object):

    # @staticmethod
    # def get_day_old_time():
    #     return frappe.utils.data.add_to_date(frappe.utils.data.nowtime(),days=-1,as_datetime=True)

    @staticmethod
    def get_all_last_one_day_processing_jobs():
        return frappe.get_all("Job", filters=[
            ["status", "=", Job_status.PROCESSING.value],
            # ["modified", ">=", Helper.get_day_old_time()],
        ])

    @staticmethod
    def check_and_update_back_to_pending(job):
        try:
            processing_job = frappe.get_doc("Job", job.name)
            processing_job.lock_for_update()
            if processing_job.retry_count == processing_job.max_retries:
                processing_job.update_status(Job_status.FAILURE.value)
            else:
                processing_job.update_status(Job_status.PENDING.value)
        except:
            pass

def fix_stuck_jobs():
    if frappe.local.conf.disable_fix_stuck_jobs:
        return

    processing_jobs = Helper.get_all_last_one_day_processing_jobs()
    for processing_job in processing_jobs:
        Helper.check_and_update_back_to_pending(processing_job)
