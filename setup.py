#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


setup(
    name='py-evm',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.2.0-alpha.12',
    description='Python implementation of the Ethereum Virtual Machine',
    long_description_markdown_filename='README.md',
    author='Piper Merriam',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/py-evm',
    include_package_data=True,
    py_modules=['evm', 'trinity', 'p2p'],
    install_requires=[
        "aiohttp>=2.3.1,<3.0.0",
        "async_lru>=0.1.0,<1.0.0",
        "cryptography>=2.0.3,<3.0.0",
        "cytoolz>=0.9.0,<1.0.0",
        "eth-bloom>=1.0.0,<2.0.0",
        "eth-utils>=1.0.1,<2.0.0",
        "pyethash>=0.1.27,<1.0.0",
        "py-ecc>=1.4.2,<2.0.0",
        "rlp>=0.4.7,<1.0.0",
        "eth-keys>=0.2.0b3,<1.0.0",
        "trie>=1.3.0,<2.0.0",
        "eth-tester==0.1.0b21",
        "web3>=4.0.0b6,<5.0.0",
    ],
    extras_require={
        'coincurve': [
            "coincurve>=7.0.0,<8.0.0",
        ],
        'leveldb': [
            "leveldb>=0.194,<1.0.0",
        ],
        'trinity': [
            "leveldb>=0.194,<1.0.0",
            "coincurve>=7.0.0,<8.0.0",
            "eth-hash[pycryptodome]>=0.1.0a4,<1.0.0",
        ],
        'p2p': [
            "aiohttp>=2.3.1,<3.0.0",
            "async_lru>=0.1.0,<1.0.0",
        ],
    },
    setup_requires=['setuptools-markdown'],
    license='MIT',
    zip_safe=False,
    keywords='ethereum blockchain evm',
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
    ],
    # trinity
    entry_points={
        'console_scripts': ['trinity=trinity:main'],
    },
)
