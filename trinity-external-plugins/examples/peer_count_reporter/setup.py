#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup

entry_point = 'peer_count_reporter_plugin=peer_count_reporter_plugin:PeerCountReporterPlugin'

setup(
    name='trinity-peer-count-reporter-plugin',
    py_modules=['peer_count_reporter_plugin'],
    entry_points={
        'trinity.plugins': entry_point,
    },
)
