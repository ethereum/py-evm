#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup


setup(
    name='trinity',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    # NOT CURRENTLY APPLICABLE. VERSION BUMPS MANUAL FOR NOW
    version='0.1.0-alpha.19',
    description='The Trinity Ethereum Client',
    author='Ethereum Foundation',
    author_email='piper@pipermerriam.com',
    url='https://github.com/ethereum/py-evm',
    include_package_data=True,
    py_modules=[],
    install_requires=[
        # DON'T FORGET TO BUMP THIS TOOOOOO!!!!!!!
        'py-evm[trinity,p2p]==0.2.0a35',
    ],
    license='MIT',
    zip_safe=False,
    keywords='ethereum blockchain evm trinity',
    packages=[],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    python_requires=">=3.6,<4",
    # trinity
    entry_points={
        'console_scripts': [
            'trinity=trinity:main',
            'trinity-beacon=trinity:main_beacon'
        ],
    },
)
