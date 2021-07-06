import frappe
from latte.json import loads, dumps
import math
from RestrictedPython import compile_restricted, safe_globals
from latte.utils.logger import get_logger

COMPILED_FILTER = {}


def get_fn(cache_key, function_name, function_args, function_string,
           default_return_val=None, addl_context: dict = None):
    logger = get_logger()
    # If already cached, use cached value
    try:
        return COMPILED_FILTER[cache_key]
    except KeyError:
        pass
    fn_name_str = f'def {function_name}({",".join(function_args)}):'
    # If no function string is provided, create a default function
    if not function_string:
        if 'default_return_val' not in function_args:
            function_args.append('default_return_val')
            fn_name_str = f'def {function_name}({",".join(function_args)}):'
        # if cached value is not available, create a default function
        function_string = f"""
{fn_name_str}
    return default_return_val
"""

    function_str = function_string.strip()
    if fn_name_str not in function_str:
        parsed_filter_string = f'''
{fn_name_str}
    return {function_string}
'''
    else:
        parsed_filter_string = function_string

    local_dict = {}
    patched_safe_globals = dict(safe_globals)
    patched_safe_globals.update(get_context())
    if addl_context:
        patched_safe_globals.update(addl_context)

    builtins_dict = patched_safe_globals.get("__builtins__")
    builtins_dict['log_debug'] = lambda *_: logger.debug(*_)
    builtins_dict['log_info'] = lambda *_: logger.info(*_)
    builtins_dict['log_error'] = lambda *_: logger.error(*_)
    patched_safe_globals.update({'__builtins__': builtins_dict})
    logger.debug(f"Compiling function string {parsed_filter_string}")
    byte_code = compile_restricted(parsed_filter_string, '<inline>', 'exec')
    exec(byte_code, patched_safe_globals, local_dict)
    fn = local_dict[function_name]

    COMPILED_FILTER[cache_key] = fn
    return fn


def get_context():
    return frappe._dict({
        '_write_': lambda x: x,
        '_getitem_': lambda o, a: o[a],
        '_getattr_': getattr,
        '_getiter_': iter,
        'any': any,
        'all': all,
        'math': math,
        'frappe': frappe._dict({
            'loads': loads,
            'dumps': dumps,
            'get_doc': frappe.get_doc,
            'get_cached_doc': frappe.get_cached_doc,
            'get_cached_value': frappe.get_cached_value,
            'db': frappe._dict({
                'get_value': lambda *args, **kwargs: frappe.local.db.get_value(*args, **kwargs),
            }),
            'get_all': frappe.get_all,
            "get_url": frappe.utils.get_url,
            'format': frappe.format_value,
            "format_value": frappe.format_value,
            "get_meta": frappe.get_meta,
            'get_system_settings': frappe.get_system_settings,
            "utils": frappe.utils.data,
            "render_template": frappe.render_template,
            'session': {
                'user': frappe.session.user,
            },
            "socketio_port": frappe.conf.socketio_port,
        }),
    })
