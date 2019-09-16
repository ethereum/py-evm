#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup

entry_point = 'peer_count_reporter_component=peer_count_reporter_component:PeerCountReporterComponent'

setup(
    name='trinity-peer-count-reporter-component',
    py_modules=['peer_count_reporter_component'],
    entry_points={
        'trinity.components': entry_point,
    },
)
