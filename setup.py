#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


deps = {
    'p2p': [
        "asyncio-cancel-token==0.1.0a2",
        "async_lru>=0.1.0,<1.0.0",
        "eth-hash>=0.1.4,<1",
        "netifaces>=0.10.7<1",
        "pysha3>=1.0.0,<2.0.0",
        "upnpclient>=0.0.8,<1",
        "python-snappy>=0.5.3",
    ],
    'trinity': [
        "async-generator==1.10",
        "bloom-filter==1.3",
        "cachetools>=2.1.0,<3.0.0",
        "coincurve>=10.0.0,<11.0.0",
        "eth-utils>=1.3.0,<2",
        "ipython>=6.2.1,<7.0.0",
        "plyvel==1.0.5",
        "py-evm==0.2.0a40",
        "web3==4.4.1",
        "lahja==0.10.2",
        "termcolor>=1.1.0,<2.0.0",
        "uvloop==0.11.2;platform_system=='Linux' or platform_system=='Darwin' or platform_system=='FreeBSD'",
        "websockets==5.0.1",
        "jsonschema==2.6.0",
    ],
    'test': [
        "hypothesis==3.69.5",
        "pexpect>=4.6, <5",
        # pinned to <3.7 until async fixtures work again
        # https://github.com/pytest-dev/pytest-asyncio/issues/89
        "pytest>=3.6,<3.7",
        "pytest-asyncio==0.9.0",
        "pytest-cov==2.5.1",
        "pytest-watch>=4.1.0,<5",
        "pytest-xdist==1.18.1",
        # only needed for p2p
        "pytest-asyncio-network-simulator==0.1.0a2;python_version>='3.6'",
    ],
    'lint': [
        "flake8==3.5.0",
        "mypy==0.641",
    ],
    'doc': [
        "pytest~=3.2",
        # Sphinx pined to `<1.8.0`: https://github.com/sphinx-doc/sphinx/issues/3494
        "Sphinx>=1.5.5,<1.8.0",
        "sphinx_rtd_theme>=0.1.9",
        "sphinxcontrib-asyncio>=0.2.0",
    ],
    'dev': [
        "bumpversion>=0.5.3,<1",
        "wheel",
        "setuptools>=36.2.0",
        # Fixing this dependency due to: pytest 3.6.4 has requirement pluggy<0.8,>=0.5, but you'll have pluggy 0.8.0 which is incompatible.
        "pluggy==0.7.1",
        # Fixing this dependency due to: requests 2.20.1 has requirement idna<2.8,>=2.5, but you'll have idna 2.8 which is incompatible.
        "idna==2.7",
        # idna 2.7 is not supported by requests 2.18
        "requests>=2.20,<3",
        "tox==2.7.0",
        "twine",
    ],
    'eth2': [
        "cytoolz>=0.9.0,<1.0.0",
        "eth-typing>=2.0.0,<3.0.0",
        "eth-utils>=1.3.0b0,<2.0.0",
        "lru-dict>=1.1.6",
        "mypy_extensions>=0.4.1,<1.0.0",
        "py-ecc>=1.4.7,<2.0.0",
        "rlp>=1.1.0,<2.0.0",
        "py-evm>=0.2.0a38",
    ],
}


deps['dev'] = (
    deps['dev'] +
    deps['p2p'] +
    deps['trinity'] +
    deps['test'] +
    deps['doc'] +
    deps['lint'] +
    deps['eth2']
)


install_requires = deps['trinity'] + deps['p2p']

setup(
    name='trinity',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.1.0-alpha.22',
    description='The Trinity client for the Ethereum network',
    long_description_markdown_filename='README.md',
    author='Ethereum Foundation',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/trinity',
    include_package_data=True,
    py_modules=['trinity', 'p2p', 'eth2'],
    python_requires=">=3.6,<4",
    install_requires=install_requires,
    extras_require=deps,
    setup_requires=['setuptools-markdown'],
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
