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
:class:`~trinity.extensibility.plugin.BaseIsolatedPlugin`.  A detailed example will follow soon.


Plugins that run inside the networking process
----------------------------------------------

If the previous category sounded as if it could handle every possible use case, it's because it's
actually meant to. In reality though, not all internal APIs yet work well across process
boundaries. In practice, this means that sometimes we want to make sure that a plugin runs in the
same process as the rest of the networking code.

.. warning::
  The need to run plugins in the networking process is declining as the internals of Trinity become
  more and more multi-process friendly over time. While it isn't entirely clear yet, there's a fair
  chance this type of plugin will become obsolete at some point and may eventually be removed.

  We should only choose this type of plugin category if what we are trying to build cannot be built
  with a :class:`~trinity.extensibility.plugin.BaseIsolatedPlugin`.

We build this kind of plugin subclassing from
:class:`~trinity.extensibility.plugin.BaseAsyncStopPlugin`.  A detailed example will follow soon.


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
was called which happens as soon the core infrastructure of Trinity is ready.

Plugin state: ``READY``
-----------------------

After Trinity has finished setting up the core infrastructure, every plugin has its
:class:`~trinity.extensibility.plugin.PluginContext` set and
:meth:`~trinity.extensibility.plugin.BasePlugin.on_ready` is called. At this point the plugin has
access to important information such as the parsed arguments or the 
:class:`~trinity.config.TrinityConfig`. It also has access to the central event bus via its
:meth:`~trinity.extensibility.plugin.BasePlugin.event_bus` property which enables the plugin to
communicate with other parts of the application including other plugins.

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
:class:`~trinity.extensibility.plugin.BaseMainProcessPlugin`,
:class:`~trinity.extensibility.plugin.BaseIsolatedPlugin` or 
:class:`~trinity.extensibility.plugin.BaseAsyncStopPlugin` depending on the kind of plugin that we
intend to write. For now, we'll stick to :class:`~trinity.extensibility.plugin.BaseIsolatedPlugin`
which is the most commonly used plugin category.

Every plugin needs to overwrite ``name`` so voilà, here's our first plugin!

.. literalinclude:: ../../../trinity/plugins/examples/peer_count_reporter/plugin.py
   :language: python
   :start-after: --START CLASS--
   :end-before: def configure_parser

Of course that doesn't do anything useful yet, bear with us.

Configuring Command Line Arguments
----------------------------------

More often than not we want to have control over if or when a plugin should start. Adding
command-line arguments that are specific to such a plugin, which we then check, validate, and act
on, is a good way to deal with that. Implementing
:meth:`~trinity.extensibility.plugin.BasePlugin.configure_parser` enables us to do exactly that.

This method is called when Trinity starts and bootstraps the plugin system, in other words,
**before** the start of any plugin. It is passed a :class:`~argparse.ArgumentParser` as well as a
:class:`~argparse._SubParsersAction` which allows it to amend the configuration of Trinity's
command line arguments in many different ways.

For example, here we are adding a boolean flag ``--report-peer-count`` to Trinity.

.. literalinclude:: ../../../trinity/plugins/examples/peer_count_reporter/plugin.py
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

Causing a plugin to start
-------------------------

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
``READY`` state.

Communication pattern
~~~~~~~~~~~~~~~~~~~~~

Coming soon: Spoiler: Plugins can communicate with other parts of the application or even other
plugins via the central event bus.

Making plugins discoverable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Coming soon.

.. warning::
  **Wait?! This is it? No! This is draft version of the plugin guide as small DEVCON IV gitft.
  This will turn into a much more detailed guide shortly after the devcon craze is over.**
