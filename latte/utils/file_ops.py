import os
import os

def write(path, data):
    with open(os.path.abspath(path), 'w') as f:
        f.write(data)

def read(path):
    with open(os.path.abspath(path)) as f:
        return f.read()