#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


deps = {
    'eth': [
        "cached-property>=1.5.1,<2",
        "eth-bloom>=1.0.3,<2.0.0",
        "eth-keys>=0.3.4,<0.4.0",
        "eth-typing>=2.3.0,<3.0.0",
        "eth-utils>=1.9.4,<2.0.0",
        "lru-dict>=1.1.6",
        "mypy_extensions>=0.4.1,<1.0.0",
        "py-ecc>=1.4.7,<6.0.0",
        "pyethash>=0.1.27,<1.0.0",
        "rlp>=2,<3",
        "trie==2.0.0-alpha.5",
    ],
    # The eth-extra sections is for libraries that the evm does not
    # explicitly need to function and hence should not depend on.
    # Installing these libraries may make the evm perform better than
    # using the default fallbacks though.
    'eth-extra': [
        "blake2b-py>=0.1.4,<0.2",
        "coincurve>=13.0.0,<14.0.0",
        "eth-hash[pysha3];implementation_name=='cpython'",
        "eth-hash[pycryptodome];implementation_name=='pypy'",
        "plyvel>=1.2.0,<2",
    ],
    'test': [
        "factory-boy==2.11.1",
        "hypothesis>=5,<6",
        "pexpect>=4.6, <5",
        "pytest>=6.2.4,<7",
        "pytest-asyncio>=0.10.0,<0.11",
        "pytest-cov==2.5.1",
        "pytest-timeout>=1.4.2,<2",
        "pytest-watch>=4.1.0,<5",
        "pytest-xdist==2.3.0",
    ],
    'lint': [
        "flake8==3.8.2",
        "flake8-bugbear==20.1.4",
        "mypy==0.782",
    ],
    'benchmark': [
        "termcolor>=1.1.0,<2.0.0",
        "web3>=4.1.0,<5.0.0",
    ],
    'doc': [
        "py-evm>=0.2.0-alpha.14",
        # We need to have pysha for autodoc to be able to extract API docs
        "pysha3>=1.0.0,<2.0.0",
        # Sphinx pined to `<1.8.0`: https://github.com/sphinx-doc/sphinx/issues/3494
        "Sphinx>=1.5.5,<1.8.0",
        "sphinx_rtd_theme>=0.1.9",
        "sphinxcontrib-asyncio>=0.2.0,<0.3",
        "towncrier>=19.2.0, <20",
    ],
    'dev': [
        "bumpversion>=0.5.3,<1",
        "wheel",
        "setuptools>=36.2.0",

        # Fixing this dependency due to: requests 2.20.1 has requirement
        # idna<2.8,>=2.5, but you'll have idna 2.8 which is incompatible.
        "idna==2.7",
        # idna 2.7 is not supported by requests 2.18
        "requests>=2.20,<3",
        "tox==2.7.0",
        "twine",
    ],
}


deps['dev'] = (
    deps['dev'] +
    deps['eth'] +
    deps['test'] +
    deps['doc'] +
    deps['lint']
)


install_requires = deps['eth']

with open('README.md') as readme_file:
    long_description = readme_file.read()

setup(
    name='py-evm',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.5.0-alpha.3',
    description='Python implementation of the Ethereum Virtual Machine',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Ethereum Foundation',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/py-evm',
    include_package_data=True,
    py_modules=['eth'],
    install_requires=install_requires,
    extras_require=deps,
    license='MIT',
    zip_safe=False,
    keywords='ethereum blockchain evm',
    packages=find_packages(exclude=["tests", "tests.*"]),
    package_data={'eth': ['py.typed']},
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
