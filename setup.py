#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


deps = {
    'eth': [
        "cryptography>=2.0.3,<3.0.0",
        "cytoolz>=0.9.0,<1.0.0",
        "eth-bloom>=1.0.0,<2.0.0",
        "eth-keys>=0.2.0b3,<1.0.0",
        "eth-typing>=1.1.0,<2.0.0",
        "eth-utils>=1.0.1,<2.0.0",
        "lru-dict>=1.1.6",
        "py-ecc>=1.4.2,<2.0.0",
        "pyethash>=0.1.27,<1.0.0",
        "rlp>=1.0.1,<2.0.0",
        "trie>=1.3.5,<2.0.0",
    ],
    # The eth-extra sections is for libraries that the evm does not
    # explicitly need to function and hence should not depend on.
    # Installing these libraries may make the evm perform better than
    # using the default fallbacks though.
    'eth-extra': [
        "coincurve>=8.0.0,<9.0.0",
        "eth-hash[pysha3];implementation_name=='cpython'",
        "eth-hash[pycryptodome];implementation_name=='pypy'",
        "plyvel==1.0.5",
    ],
    'p2p': [
        "asyncio-cancel-token==0.1.0a2",
        "async_lru>=0.1.0,<1.0.0",
        "eth-hash>=0.1.4,<1",
        "netifaces>=0.10.7<1",
        "pysha3>=1.0.0,<2.0.0",
        "upnpclient>=0.0.8,<1",
    ],
    'trinity': [
        "bloom-filter==1.3",
        "cachetools>=2.1.0,<3.0.0",
        "coincurve>=8.0.0,<9.0.0",
        "ipython>=6.2.1,<7.0.0",
        "plyvel==1.0.5",
        "web3==4.4.1",
    ],
    'test': [
        "hypothesis==3.44.26",
        # pinned to <3.7 until async fixtures work again
        # https://github.com/pytest-dev/pytest-asyncio/issues/89
        "pytest>=3.6,<3.7",
        "pytest-asyncio==0.8.0",
        "pytest-cov==2.5.1",
        "pytest-watch>=4.1.0,<5",
        "pytest-xdist==1.18.1",
        # only needed for p2p
        "pytest-asyncio-network-simulator==0.1.0a2;python_version>='3.6'",
    ],
    'lint': [
        "flake8==3.5.0",
        "mypy==0.620",
    ],
    'benchmark': [
        "termcolor>=1.1.0,<2.0.0",
        "web3>=4.1.0,<5.0.0",
    ],
    'doc': [
        "py-evm>=0.2.0-alpha.14",
        "pytest~=3.2",
        "Sphinx>=1.5.5,<2.0.0",
        "sphinx_rtd_theme>=0.1.9",
        "sphinxcontrib-asyncio>=0.2.0",
    ],
    'dev': [
        "bumpversion>=0.5.3,<1",
        "wheel",
        "tox==2.7.0",
        "twine",
    ],
}


deps['dev'] = (
    deps['dev'] +
    deps['eth'] +
    deps['eth-extra'] +
    deps['p2p'] +
    deps['trinity'] +
    deps['test'] +
    deps['doc'] +
    deps['lint']
)

# As long as eth, p2p and trinity are managed together in the py-evm
# package, someone running a `pip install py-evm` should expect all
# dependencies for eth, p2p and trinity to get installed.
install_requires = deps['eth'] + deps['p2p'] + deps['trinity']

setup(
    name='py-evm',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.2.0-alpha.30',
    description='Python implementation of the Ethereum Virtual Machine',
    long_description_markdown_filename='README.md',
    author='Ethereum Foundation',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/py-evm',
    include_package_data=True,
    py_modules=['eth', 'trinity', 'p2p'],
    install_requires=install_requires,
    extras_require=deps,
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
        'Programming Language :: Python :: 3.6',
    ],
    # trinity
    entry_points={
        'console_scripts': ['trinity=trinity:main'],
    },
)
