# -*- coding: utf-8 -*-
# Copyright (c) 2020, Sachin Mane and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

from frappe import ValidationError
from latte.quartz.doctype.scheduler_event.scheduler_event import SchedulerEvent


class TestSchedulerEvent(unittest.TestCase):

    def setUp(self) -> None:
        frappe.local.valid_columns = {'Scheduler Event': ['disabled', 'is_standard', 'module', 'event_type',
                                                          'event_group', 'ref_doctype', 'ref_docname', 'event',
                                                          'handler']}
        frappe.local.response = {}
        frappe.flags = frappe._dict({'mute_messages': 0})
        frappe.message_log = []

    def test_validate_cron_noevent(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Cron'})

        with self.assertRaises(ValidationError):
            event.validate()

    def test_validate_cron_nohandler(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Cron',
                                'event': '* * * * *'})

        with self.assertRaises(ValidationError):
            event.validate()

    def test_validate_doctype_nodoctype(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Doctype'})

        with self.assertRaises(ValidationError):
            event.validate()

    def test_validate_doctype_noevent(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Doctype',
                                'ref_doctype': 'User'})

        with self.assertRaises(ValidationError):
            event.validate()

    def test_validate_doctype_nohandler(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Doctype',
                                'ref_doctype': 'User',
                                'event': 'on_update'})

        with self.assertRaises(ValidationError):
            event.validate()

    def test_validate_custom_noeventgroup(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Custom'
                                })

        with self.assertRaises(ValidationError):
            event.validate()

    def test_validate_custom_noevent(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Custom',
                                'event_group': 'kredit_events'
                                })

        with self.assertRaises(ValidationError):
            event.validate()

    def test_validate_custom_nohandler(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Custom',
                                'event_group': 'kredit_events',
                                'event': 'on_update'
                                })

        with self.assertRaises(ValidationError):
            event.validate()

    def test_validate_custom_valid(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Custom',
                                'event_group': 'kredit_events',
                                'event': 'on_update',
                                'handler': 'dummyhandler'
                                })

        event.validate()
        self.assertTrue(1 == 1)

    def test_validate_cron_valid(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Cron',
                                'event': '* * * * *',
                                'handler': 'dummyhandler'
                                })

        event.validate()
        self.assertTrue(1 == 1)

    def test_validate_doctype_valid(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 0,
                                'is_standard': 0,
                                'event_type': 'Doctype',
                                'ref_doctype': 'User',
                                'event': 'on_update',
                                'handler': 'dummyhandler'
                                })

        event.validate()
        self.assertTrue(1 == 1)

    def test_validate_disabled(self):
        event = SchedulerEvent({'doctype': "Scheduler Event",
                                'disabled': 1,
                                'is_standard': 0,
                                'event_type': 'Cron',
                                'event': '* * * * *'})
        event.validate()
        self.assertTrue(1 == 1)
