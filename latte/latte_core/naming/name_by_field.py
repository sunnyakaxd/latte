import frappe

def get_next_name(doctype, value, field, with_spaces=True):
    '''
    Return next value of the entered field in the given doctype
    '''
    value = (value or '').strip()
    space = ' ' if with_spaces else ''
    length = 4 if with_spaces else 2
    max_number = frappe.db.sql(f'''
        SELECT
            max(
                cast(substr(`{field}` from %(len)s + {length}) as integer)
            ) as max_number,
            `{field}` as field
        from
            `tab{doctype}` dt
        where
            `{field}` like %(value_like)s
            and (
                (
                    `{field}` like %(value_numbered)s
                    and `{field}` regexp %(value_regexp)s
                )
                or `{field}` = %(value)s
            )
    ''', {
        'value': value,
        'value_like': f'{value}%',
        'value_numbered': f'{value}{space}-{space}%',
        'value_regexp': f'^{value}{space}-{space}[0-9]+',
        'len': len(value)
    }, as_dict=True)

    if max_number and max_number[0] and max_number[0].field:
        return f'{value}{space}-{space}{max_number[0].max_number + 1}'

    return value