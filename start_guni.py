# -*- coding: utf-8 -*-
from gevent import monkey, spawn
monkey.patch_all()
import sys
from gunicorn.app.wsgiapp import run
from latte.commands.utils import patch_all
patch_all()
from latte.utils.background.gevent_worker import start

sys.argv += [
	'-t', '120',
]
print(sys.argv)
if __name__ == '__main__':
	sys.exit(run())
