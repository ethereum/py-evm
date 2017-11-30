#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


setup(
    name='py-evm',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.2.0-alpha.7',
    description='Python implementation of the Ethereum Virtual Machine',
    long_description_markdown_filename='README.md',
    author='Piper Merriam',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/py-evm',
    include_package_data=True,
    py_modules=['evm'],
    install_requires=[
        "aiohttp==2.3.1",
        "async_lru>=0.1.0",
        "cryptography>=2.0.3",
        "cytoolz==0.8.2",
        "eth-bloom>=0.5.2",
        "eth-utils>=0.7.1",
        "pyethash>=0.1.27",
        "py-ecc==1.4.2",
        "rlp==0.4.7",
        "eth-keys==0.1.0b3",
        "trie>=0.3.1",
    ],
    extra_require={
        'leveldb': [
            "leveldb>=0.194",
        ]
    },
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
)
