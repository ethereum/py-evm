Quickstart
==========

Installation
~~~~~~~~~~~~

This guide teaches how to use Py-EVM as a library. For contributors, please check out the
:doc:`Contributing Guide </contributing>` which explains how to set everything up for development.


Installing Python on Ubuntu
---------------------------

Py-EVM requires Python 3.6 as well as some tools to compile its dependencies. On Ubuntu, the
``python3.6-dev`` package contains everything we need. Run the following command to install it.

.. code:: sh

  apt-get install python3.6-dev

Py-EVM is installed through the pip package manager, if pip isn't available on the system already,
we need to install the ``python3-pip`` package through the following command.

.. code:: sh

  apt-get install python3-pip


Installing Python on macOS
--------------------------

First, install Python 3 with brew:

.. code:: sh

  brew install python3

Installing py-evm
-----------------

.. note::
  .. include:: /fragments/virtualenv_explainer.rst

Then, make sure to have the latest version of ``pip`` so that all dependencies can be installed correctly:

.. code:: sh

  pip3 install -U pip

Finally, install the ``py-evm`` package via pip:

.. code:: sh

  pip3 install -U py-evm


.. hint::

  :doc:`Build a first app </guides/building_an_app_that_uses_pyevm>` on top of Py-EVM in under
  5 minutes


