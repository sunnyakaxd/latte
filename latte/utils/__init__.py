import traceback
from functools import wraps

from latte.utils.standard_creation_tools import export_to_files
from latte.utils.caching import cache_in_mem, cache_me_if_you_can, get_args_for
from sys import stderr
from frappe import local

def get_system_setting(key):
    return get_system_settings().get(key)

@cache_in_mem(key=lambda *_,**__: 'SYSTEM_SETTINGS', timeout=360)
@cache_me_if_you_can(expiry=360)
def get_system_settings():
    return local.db.get_singles_dict("System Settings")

def errprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)


def error_alert():
    def innerfn(fn):
        method_name = f'{fn.__module__}.{fn.__qualname__}'

        @wraps(fn)
        def decorated(*args, **kwargs):
            new_args, new_kwargs = get_args_for(fn, args, kwargs)
            try:
                return fn(*new_args, **new_kwargs)
            except Exception as e:
                orig_msg = traceback.format_exc()
                import frappe
                settings = frappe.get_single('Support Settings')
                if not settings.disabled:
                    try:
                        subject = frappe.render_template(settings.subject, {"exception": e})
                        msg = frappe.render_template(settings.message, {"traceback": orig_msg})
                        recipients = settings.recipients
                        if ',' in recipients:
                            recipients = recipients.split(',')
                        copied_to = settings.copy_to
                        if ',' in copied_to:
                            copied_to = copied_to.split(',')
                        frappe.sendmail(recipients=recipients, cc=copied_to,
                                        subject=subject, message=msg)
                    except:
                        print('Error occurred while sending error email to support.')
                        print(f'Original error in method {method_name} - \n{orig_msg}')
                raise e
        return decorated
    return innerfn
