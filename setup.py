#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os

from setuptools import setup, find_packages

DIR = os.path.dirname(os.path.abspath(__file__))


readme = open(os.path.join(DIR, 'README.md')).read()

# By definition, we can't depend on evm being installed yet,
# so pull this information in via read, not import.
about = {}
with open(os.path.join(DIR, 'evm', '__version__.py'), 'r') as f:
    exec(f.read(), about)

setup(
    name=about['__title__'],
    version=about['__version__'],
    description=about['__description__'],
    long_description=readme,
    author=about['__author__'],
    author_email=about['__author_email__'],
    url=about['__url__'],
    include_package_data=True,
    py_modules=['evm'],
    install_requires=[
        "aiohttp==2.3.1",
        "async_lru>=0.1.0",
        "cryptography>=2.0.3",
        "cytoolz==0.8.2",
        "ethereum-bloom>=0.4.0",
        "ethereum-utils>=0.2.0",
        "pyethash>=0.1.27",
        "py-ecc==1.4.2",
        "rlp==0.4.7",
        "ethereum-keys==0.1.0a7",
        "trie>=0.3.0",
    ],
    extra_require={
        'leveldb': [
            "leveldb>=0.194",
        ]
    },
    license=about['__license__'],
    zip_safe=False,
    keywords='ethereum blockchain evm',
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
)
