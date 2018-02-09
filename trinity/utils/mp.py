import multiprocessing
import os


MP_CONTEXT = os.environ.get('TRINITY_MP_CONTEXT', 'spawn')


# sets the type of process that multiprocessing will create.
ctx = multiprocessing.get_context(MP_CONTEXT)
