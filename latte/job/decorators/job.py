import frappe
from latte.job.doctype.job.job import Job_status
from functools import wraps

def job(max_retries=5):
    def wrap(fn):

        @wraps(fn)
        def wrapper(self, *args, __job__=True, **kwargs):
            if not __job__:
                fn(self)
            else:
                job_doc = frappe.get_doc({
                    "doctype": "Job",
                    "ref_doctype": self.doctype,
                    "ref_docname": self.name,
                    "method": fn.__name__,
                    "max_retries": max_retries,
                    "started_on": frappe.utils.now_datetime()
                })
                job_doc.insert(ignore_permissions = True)
                job_doc.update_status(Job_status.PROCESSING.value)
                job_doc.execute()
        return wrapper
    return wrap