#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='trinity_test_plugin',
    py_modules=['trinity_test_plugin'],
    entry_points={'trinity.plugins': 'trinity_test_plugin=trinity_test_plugin:TestPlugin'},
)
