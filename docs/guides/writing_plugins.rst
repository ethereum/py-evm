Writing Plugins
===============

Trinity aims to be a highly flexible Ethereum node to support lots of different use cases
beyond just participating in the regular networking traffic.

To support this goal, Trinity allows developers to create plugins that hook into the system to
extend its functionality. In fact, Trinity dogfoods its Plugin API in the sense that several
built-in features are written as plugins that just happen to be shipped among the rest of the core
modules. For instance, the JSON-RPC API, the Transaction Pool as well as the ``trinity attach``
command that provides an interactive REPL with `Web3` integration are all built as plugins.

Trinity tries to follow the practice: If something can be written as a plugin, it should be written
as a plugin.


What can plugins do?
~~~~~~~~~~~~~~~~~~~~

Plugin support in Trinity is still very new and the API hasn't stabilized yet. That said, plugins
are already pretty powerful and are only becoming more so as the APIs of the underlying services
improve over time.

Here's a list of functionality that is currently provided by plugins:

- JSON-RPC API
- Transaction Pool
- EthStats Reporting
- Interactive REPL with Web3 integration
- Crash Recovery Command


Understanding the different plugin categories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are currently three different types of plugins that we'll all cover in this guide.

- Plugins that overtake and redefine the entire ``trinity`` command
- Plugins that spawn their own new isolated process
- Plugins that run in the shared `networking` process



Plugins that redefine the Trinity process
-----------------------------------------

This is the simplest category of plugins as it doesn't really *hook* into the Trinity process but 
hijacks it entirely instead. We may be left wonderering: Why would one want to do that?

The only reason to write such a plugin is to execute some code that we want to group under the
``trinity`` command. A great example for such a plugin is the ``trinity attach`` command that gives
us a REPL attached to a running Trinity instance. This plugin could have easily be written as a
standalone program and associated with a command such as ``trinity-attach``. However, using a
subcommand ``attach`` is the more idiomatic approach and this type of plugin gives us simple way
to develop exactly that.

We build this kind of plugin by subclassing from
:class:`~trinity.extensibility.plugin.BaseMainProcessPlugin`. A detailed example will follow soon.


Plugins that spawn their own new isolated process
-------------------------------------------------

Of course, if all what plugins could do is to hijack the `trinity` command, there wouldn't be
much room to actually extend the *runtime functionality* of Trinity. If we want to create plugins
that boot with and run alongside the main node activity, we need to write a different kind of
plugin. These type of plugins can respond to events such as a peers connecting/disconnecting and
can access information that is only available within the running application.

The JSON-RPC API is a great example as it exposes information such as the current count
of connected peers which is live information that can only be accessed by talking to other parts
of the application at runtime.

This is the default type of plugin we want to build if:

- we want to execute logic **together** with the command that boots Trinity (as opposed
  to executing it in a separate command)
- we want to execute logic that integrates with parts of Trinity that can only be accessed at
  runtime (as opposed to e.g. just reading things from the database)

We build this kind of plugin subclassing from
:class:`~trinity.extensibility.asyncio.AsyncioIsolatedPlugin`.  A detailed example will follow soon.


The plugin lifecycle
~~~~~~~~~~~~~~~~~~~~

Plugins can be in one of the following status at a time:

- ``NOT_READY``
- ``READY``
- ``STARTED``
- ``STOPPED``

The current status of a plugin is also reflected in the
:meth:`~trinity.extensibility.plugin.BasePlugin.status` property.

.. note::

  Strictly speaking, there's also a special state that only applies to the
  :class:`~trinity.extensibility.plugin.BaseMainProcessPlugin` which comes into effect when such a
  plugin hijacks the Trinity process entirely. That being said, in that case, the resulting process
  is in fact something entirely different than Trinity and the whole plugin infrastruture doesn't
  even continue to exist from the moment on where that plugin takes over the Trinity process. This
  is why we do not list it as an actual state of the regular plugin lifecycle.

Plugin state: ``NOT_READY``
---------------------------

Every plugin starts out being in the ``NOT_READY`` state. This state begins with the instantiation
of the plugin and lasts until the :meth:`~trinity.extensibility.plugin.BasePlugin.on_ready` hook
was called which happens as soon as the core infrastructure of Trinity is ready.

Plugin state: ``READY``
-----------------------

After Trinity has finished setting up the core infrastructure,
:meth:`~trinity.extensibility.plugin.BasePlugin.on_ready` is called on each plugin. At
this point the plugin has access to important information such as the parsed arguments or
the :class:`~trinity.config.TrinityConfig`. It also has access to the central event bus
via its :meth:`~trinity.extensibility.plugin.BasePlugin.event_bus` property which enables
the plugin to communicate with other parts of the application including other plugins.

Plugin state: ``STARTED``
-------------------------

A plugin is in the ``STARTED`` state after the
:meth:`~trinity.extensibility.plugin.BasePlugin.start` method was called. Plugins call this method
themselves whenever they want to start which may be based on some condition like Trinity being
started with certain parameters or some event being propagated on the central event bus.

.. note::
  Calling :meth:`~trinity.extensibility.plugin.BasePlugin.start` while the plugin is in the
  ``NOT_READY`` state or when it is already in ``STARTED`` will cause an exception to be raised.


Plugin state: ``STOPPED``
-------------------------

A plugin is in the ``STOPPED`` state after the 
:meth:`~trinity.extensibility.plugin.BasePlugin.stop` method was called and finished any tear down
work.

Defining plugins
~~~~~~~~~~~~~~~~

We define a plugin by deriving from either
:class:`~trinity.extensibility.plugin.BaseMainProcessPlugin` or
:class:`~trinity.extensibility.asyncio.AsyncioIsolatedPlugin` depending on the kind of plugin that we
intend to write. For now, we'll stick to :class:`~trinity.extensibility.asyncio.AsyncioIsolatedPlugin`
which is the most commonly used plugin category.

Every plugin needs to overwrite ``name`` so voilà, here's our first plugin!

.. literalinclude:: ../../trinity-external-plugins/examples/peer_count_reporter/peer_count_reporter_plugin/plugin.py
   :language: python
   :pyobject: PeerCountReporterPlugin
   :end-before: def configure_parser

Of course that doesn't do anything useful yet, bear with us.

Configuring Command Line Arguments
----------------------------------

More often than not we want to have control over if or when a plugin should start. Adding
command-line arguments that are specific to such a plugin, which we then check, validate, and act
on, is a good way to deal with that. Implementing
:meth:`~trinity.extensibility.plugin.BasePlugin.configure_parser` enables us to do exactly that.

This method is called when Trinity starts and bootstraps the plugin system, in other words,
**before** the start of any plugin. It is passed an :class:`~argparse.ArgumentParser` as well as a
:class:`~argparse._SubParsersAction` which allows it to amend the configuration of Trinity's
command line arguments in many different ways.

For example, here we are adding a boolean flag ``--report-peer-count`` to Trinity.

.. literalinclude:: ../../trinity-external-plugins/examples/peer_count_reporter/peer_count_reporter_plugin/plugin.py
   :language: python
   :pyobject: PeerCountReporterPlugin.configure_parser

To be clear, this does not yet cause our plugin to automatically start if ``--report-peer-count``
is passed, it simply changes the parser to be aware of such flag and hence allows us to check for
its existence later.

.. note::

  For a more advanced example, that also configures a subcommand, checkout the ``trinity attach``
  plugin.


Defining a plugins starting point
---------------------------------

Every plugin needs to have a well defined starting point. The exact mechanics slightly differ
in case of a :class:`~trinity.extensibility.plugin.BaseMainProcessPlugin` but remain fairly similar
for the other types of plugins which we'll be focussing on for now.

Plugins need to implement the :meth:`~trinity.extensibility.plugin.BasePlugin.do_start` method
to define their own bootstrapping logic. This logic may involve setting up event listeners, running
code in a loop or any other kind of action.

.. warning::

  Technically, there's nothing preventing a plugin from performing starting logic in the
  :meth:`~trinity.extensibility.plugin.BasePlugin.on_ready` hook. However, doing that is an anti
  pattern as the plugin infrastructure won't know about the running plugin, can't propagate the
  :class:`~trinity.extensibility.events.PluginStartedEvent` and the plugin won't be properly shut
  down with Trinity if the node closes.

Let's assume we want to create a plugin that simply periodically prints out the number of connected
peers.

While it is absolutely possible to put this logic right into the plugin, the preferred way is to
subclass :class:`~p2p.service.BaseService` and implement the core logic in such a standalone
service.

.. literalinclude:: ../../trinity-external-plugins/examples/peer_count_reporter/peer_count_reporter_plugin/plugin.py
   :language: python
   :pyobject: PeerCountReporter

Then, the implementation of :meth:`~trinity.extensibility.asyncio.AsyncioIsolatedPlugin.do_start` is
only concerned about running the service on a fresh event loop.

.. literalinclude:: ../../trinity-external-plugins/examples/peer_count_reporter/peer_count_reporter_plugin/plugin.py
   :language: python
   :pyobject: PeerCountReporterPlugin.do_start

If the example may seem unnecessarily complex, it should be noted that plugins can be implemented
in many different ways, but this example follows a pattern that is considered best practice within
the Trinity Code Base.

Starting a plugin
-----------------

As we've read in the previous section not all plugins should run at any point in time. In fact, the
circumstances under which we want a plugin to begin its work may vary from plugin to plugin.

We may want a plugin to only start running if:

- a certain (combination) of command line arguments was given
- another plugin or group of plugins started
- a certain number of connected peers was exceeded / undershot
- a certain block number was reached
- ...

Hence, to actually start a plugin, the plugin needs to invoke the
:meth:`~trinity.extensibility.plugin.BasePlugin.start` method at any moment when it is in its
``READY`` state. Let's assume a simple case in which we simply want to start the plugin if Trinity
is started with the ``--report-peer-count`` flag.

.. literalinclude:: ../../trinity-external-plugins/examples/peer_count_reporter/peer_count_reporter_plugin/plugin.py
   :language: python
   :pyobject: PeerCountReporterPlugin.on_ready

In case of a :class:`~trinity.extensibility.asyncio.AsyncioIsolatedPlugin`, this will cause the
:meth:`~trinity.extensibility.asyncio.AsyncioIsolatedPlugin.do_start` method to run on an entirely
separated, new process. In other cases
:meth:`~trinity.extensibility.asyncio.AsyncioIsolatedPlugin.do_start` will simply run in the same
process as the plugin manager that the plugin is controlled by.


Communication pattern
~~~~~~~~~~~~~~~~~~~~~

For most plugins to be useful they need to be able to communicate with the rest of the application
as well as other plugins. In addition to that, this kind of communication needs to work across
process boundaries as plugins will often operate in independent processes.

To achieve this, Trinity uses the
`Lahja project <https://github.com/ethereum/lahja>`_, which enables us to operate
a lightweight event bus that works across processes. An event bus is a software dedicated to the
transmission of events from a broadcaster to interested parties.

This kind of architecture allows for efficient and decoupled communication between different parts
of Trinity including plugins.

For instance, a plugin may be interested to perform some action every time that a new peer connects
to our node. These kind of events get exposed on the EventBus and hence allow a wide range of
plugins to make use of them.

For an event to be usable across processes it needs to be pickleable and in general should be a
shallow Data Transfer Object (`DTO <https://en.wikipedia.org/wiki/Data_transfer_object>`_)

Every plugin has access to the event bus via its
:meth:`~trinity.extensibility.plugin.BasePlugin.event_bus` property and in fact we have already
used it in the above example to get the current number of connected peers.

.. note::
  This guide will soon cover communication through the event bus in more detail. For now, the
  `Lahja documentation <https://github.com/ethereum/lahja/blob/master/README.md>`_ gives us some
  more information about the available APIs and how to use them.

Distributing plugins
~~~~~~~~~~~~~~~~~~~~

Of course, plugins are more fun if we can share them and anyone can simply install them through
``pip``. The good news is, it's not hard at all!

In this guide, we won't go into details about how to create Python packages as this is already
`covered in the official Python docs <https://packaging.python.org/tutorials/packaging-projects/>`_
.

Once we have a ``setup.py`` file, all we have to do is to expose our plugin under
``trinity.plugins`` via the ``entry_points`` section.

.. literalinclude:: ../../trinity-external-plugins/examples/peer_count_reporter/setup.py
   :language: python

Check out the `official documentation on entry points <https://packaging.python.org/guides/creating-and-discovering-plugins/#using-package-metadata>`_
for a deeper explanation.

A plugin where the ``setup.py`` file is configured as described can be installed by
``pip install <package-name>`` and immediately becomes available as a plugin in Trinity.

.. note::

  Plugins installed from a local directory (instead of the pypi registry), such as the sample
  plugin described in this article, must be installed with the ``-e`` parameter (Example:
  ``pip install -e ./trinity-external-plugins/examples/peer_count_reporter``)
