#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from setuptools import setup, find_packages

PYEVM_DEPENDENCY = "py-evm==0.3.0a1"


deps = {
    'p2p': [
        "async-generator==1.10",
        "asyncio-cancel-token==0.1.0a2",
        "async_lru>=0.1.0,<1.0.0",
        "cached-property>=1.5.1,<2",
        # cryptography does not use semver and allows breaking changes within `0.3` version bumps.
        "cryptography>=2.5,<2.7",
        "eth-hash>=0.1.4,<1",
        "eth-keys>=0.2.4,<0.3.0",
        "netifaces>=0.10.7<1",
        "pysha3>=1.0.0,<2.0.0",
        "SQLAlchemy>=1.3.3,<2",
        'trio==0.11.0,<0.12',
        'trio-typing>=0.2.0,<0.3',
        "upnpclient>=0.0.8,<1",
    ],
    'trinity': [
        "bloom-filter==1.3",
        "cachetools>=3.1.0,<4.0.0",
        "coincurve>=10.0.0,<11.0.0",
        "dataclasses>=0.6, <1;python_version<'3.7'",
        "eth-utils>=1.5.1,<2",
        "ipython>=6.2.1,<7.0.0",
        "plyvel==1.0.5",
        PYEVM_DEPENDENCY,
        "web3==4.4.1",
        "lahja>=0.14.0,<0.15.0",
        "termcolor>=1.1.0,<2.0.0",
        "uvloop==0.11.2;platform_system=='Linux' or platform_system=='Darwin' or platform_system=='FreeBSD'",  # noqa: E501
        "websockets==5.0.1",
        "jsonschema==3.0.1",
        "mypy_extensions>=0.4.1,<1.0.0",
        "typing_extensions>=3.7.2,<4.0.0",
        "ruamel.yaml==0.15.98",
        "argcomplete>=1.10.0,<2",
    ],
    'test': [
        "hypothesis>=4.24.3,<5",
        "pexpect>=4.6, <5",
        "factory-boy==2.11.1",
        # pinned to <3.7 until async fixtures work again
        # https://github.com/pytest-dev/pytest-asyncio/issues/89
        "pytest>=3.6,<3.7",
        # only needed for p2p
        "pytest-asyncio-network-simulator==0.1.0a2;python_version>='3.6'",
        "pytest-cov==2.5.1",
        "pytest-watch>=4.1.0,<5",
        "pytest-xdist==1.18.1",
        "pytest-mock==1.10.4",
        # only for eth2
        "ruamel.yaml==0.15.98",
    ],
    # We have to keep some separation between trio and asyncio based tests
    # because `pytest-asyncio` is greedy and tries to run all asyncio fixtures.
    # See: https://github.com/ethereum/trinity/pull/790
    'test-asyncio': [
        "pytest-asyncio>=0.10.0,<0.11",
    ],
    'test-trio': [
        'pytest-trio==0.5.2',
    ],
    'lint': [
        "flake8==3.5.0",
        "flake8-bugbear==18.8.0",
        "mypy==0.701",
        "sqlalchemy-stubs==0.1",
    ],
    'doc': [
        "pytest~=3.2",
        # Sphinx pined to `<1.8.0`: https://github.com/sphinx-doc/sphinx/issues/3494
        "Sphinx>=1.5.5,<1.8.0",
        "sphinx_rtd_theme>=0.1.9",
        "sphinxcontrib-asyncio>=0.2.0",
        "towncrier>=19.2.0, <20",
    ],
    'dev': [
        "bumpversion>=0.5.3,<1",
        "wheel",
        "setuptools>=36.2.0",
        # Fixing this dependency due to: pytest 3.6.4 has requirement
        # pluggy<0.8,>=0.5, but you'll have pluggy 0.8.0 which is incompatible.
        "pluggy==0.7.1",
        # Fixing this dependency due to: requests 2.20.1 has requirement
        # idna<2.8,>=2.5, but you'll have idna 2.8 which is incompatible.
        "idna==2.7",
        # idna 2.7 is not supported by requests 2.18
        "requests>=2.20,<3",
        "tox==2.7.0",
        "twine",
    ],
    'eth2': [
        "cytoolz>=0.9.0,<1.0.0",
        "eth-typing>=2.1.0,<3.0.0",
        "eth-utils>=1.3.0b0,<2.0.0",
        "lru-dict>=1.1.6",
        "py-ecc==1.6.0",
        "rlp>=1.1.0,<2.0.0",
        PYEVM_DEPENDENCY,
        "ssz==0.1.0a10",
    ],
    'libp2p': [
        "base58>=1.0.3",
        "multiaddr>=0.0.8,<0.1.0",
        "protobuf>=3.6.1",
        "pymultihash>=0.8.2",
    ],
    'bls-bindings': [
        "blspy>=0.1.8,<1",  # for `bls_chia`
    ],
}

# NOTE: Snappy breaks RTD builds. Until we have a more mature solution
# we conditionally add python-snappy based on the presence of an env var
rtd_build_env = os.environ.get('READTHEDOCS', False)
if not rtd_build_env:
    deps['p2p'].append("python-snappy>=0.5.3")

deps['dev'] = (
    deps['dev'] +
    deps['p2p'] +
    deps['trinity'] +
    deps['test'] +
    deps['doc'] +
    deps['lint'] +
    deps['eth2'] +
    deps['libp2p']
)


install_requires = deps['trinity'] + deps['p2p'] + deps['eth2']


with open('./README.md') as readme:
    long_description = readme.read()


setup(
    name='trinity',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.1.0-alpha.27',
    description='The Trinity client for the Ethereum network',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Ethereum Foundation',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/trinity',
    include_package_data=True,
    py_modules=['trinity', 'p2p', 'eth2'],
    python_requires=">=3.6,<4",
    install_requires=install_requires,
    extras_require=deps,
    license='MIT',
    zip_safe=False,
    keywords='ethereum blockchain evm trinity',
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
    ],
    # trinity
    entry_points={
        'console_scripts': [
            'trinity=trinity:main',
            'trinity-beacon=trinity:main_beacon'
        ],
    },
)
