Introduction
============

Trinity & Py-EVM
~~~~~~~~~~~~~~~~

Py-EVM is a new implementation of the Ethereum Virtual Machine (EVM) written in Python. Trinity is
the client software that connects to the Ethereum network and runs on top of Py-EVM.

Trinity and Py-EVM aim to replace existing Python Ethereum implementations to eventually become the
defacto standard for the Python ecosystem.

If none of this makes sense to you yet we recommend to checkout the
`Ethereum <https://ethereum.org>`_ website as well as a
`higher level description <http://www.ethdocs.org/en/latest/introduction/what-is-ethereum.html>`_
of the Ethereum project.

Py-EVM goals
------------

The main focus is to enrich the Ethereum ecosystem with a Python implementation that:

* Supports Ethereum 1.0 as well as 2.0 / Serenity
* Is well documented
* Is easy to understand
* Has clear APIs
* Runs fast and resource friendly
* Is highly flexible to support:

  * Public chains
  * Private chains
  * Consortium chains
  * Advanced research

Trinity goals
-------------

While Py-EVM provides the low level APIs of the Ethereum protocol, it does not aim to implement a
full or light node directly.

Trinity is a refernece implementation on top of Py-EVM that aims to:

* Provide a reference implementation for an Ethereum 1.0 node (alpha)
* Support "full" and "light" modes
* Fully support mainnet as well as several testnets
* Provide a reference implementation of an Ethereum 2.0 / Serenity beacon node (pre-alpha)
* Provide a reference implementation of an Ethereum 2.0 / Sereneity validator node (pre-alpha)


.. note::

  Trinity is currently in **public alpha** and can connect and sync to the main ethereum network.
  While it isn't meant for production use yet, we encourage the adventurous to try it out.
  Follow along the :doc:`Quickstart </guides/quickstart>` to get things going.

Further reading
---------------

Here are a couple more useful links to check out.

* :doc:`Quickstart </guides/quickstart>`
* `Source Code on GitHub <https://github.com/ethereum/py-evm>`_
* `Public Gitter Chat <https://gitter.im/ethereum/py-evm>`_
* :doc:`Get involved </contributing>`