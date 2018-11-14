#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup

setup(
    name='trinity-peer-count-reporter-plugin',
    py_modules=['peer_count_reporter_plugin'],
    entry_points={
        'trinity.plugins': 'peer_count_reporter_plugin=peer_count_reporter_plugin:PeerCountReporterPlugin',
    },
)
