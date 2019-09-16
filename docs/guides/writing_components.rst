Writing Components
==================

Trinity aims to be a highly flexible Ethereum node to support lots of different use cases
beyond just participating in the regular networking traffic.

To support this goal, Trinity allows developers to create components that hook into the system to
extend its functionality. In fact, Trinity dogfoods its Component API in the sense that several
built-in features are written as components that just happen to be shipped among the rest of the core
modules. For instance, the JSON-RPC API, the Transaction Pool as well as the ``trinity attach``
command that provides an interactive REPL with `Web3` integration are all built as components.

Trinity tries to follow the practice: If something can be written as a component, it should be written
as a component.


What can components do?
~~~~~~~~~~~~~~~~~~~~~~~

Component support in Trinity is still very new and the API hasn't stabilized yet. That said, components
are already pretty powerful and are only becoming more so as the APIs of the underlying services
improve over time.

Here's a list of functionality that is currently provided by components:

- JSON-RPC API
- Transaction Pool
- EthStats Reporting
- Interactive REPL with Web3 integration
- Crash Recovery Command


Understanding the different component categories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are currently three different types of components that we'll all cover in this guide.

- Components that overtake and redefine the entire ``trinity`` command
- Components that spawn their own new isolated process
- Components that run in the shared `networking` process



Components that redefine the Trinity process
--------------------------------------------

This is the simplest category of components as it doesn't really *hook* into the Trinity process but 
hijacks it entirely instead. We may be left wonderering: Why would one want to do that?

The only reason to write such a component is to execute some code that we want to group under the
``trinity`` command. A great example for such a component is the ``trinity attach`` command that gives
us a REPL attached to a running Trinity instance. This component could have easily be written as a
standalone program and associated with a command such as ``trinity-attach``. However, using a
subcommand ``attach`` is the more idiomatic approach and this type of component gives us simple way
to develop exactly that.

We build this kind of component by subclassing from
:class:`~trinity.extensibility.component.BaseMainProcessComponent`. A detailed example will follow soon.


Components that spawn their own new isolated process
----------------------------------------------------

Of course, if all what components could do is to hijack the `trinity` command, there wouldn't be
much room to actually extend the *runtime functionality* of Trinity. If we want to create components
that boot with and run alongside the main node activity, we need to write a different kind of
component. These type of components can respond to events such as a peers connecting/disconnecting and
can access information that is only available within the running application.

The JSON-RPC API is a great example as it exposes information such as the current count
of connected peers which is live information that can only be accessed by talking to other parts
of the application at runtime.

This is the default type of component we want to build if:

- we want to execute logic **together** with the command that boots Trinity (as opposed
  to executing it in a separate command)
- we want to execute logic that integrates with parts of Trinity that can only be accessed at
  runtime (as opposed to e.g. just reading things from the database)

We build this kind of component subclassing from
:class:`~trinity.extensibility.asyncio.AsyncioIsolatedComponent`.  A detailed example will follow soon.


The component lifecycle
~~~~~~~~~~~~~~~~~~~~~~~

Components can be in one of the following status at a time:

- ``NOT_READY``
- ``READY``
- ``STARTED``
- ``STOPPED``

The current status of a component is also reflected in the
:meth:`~trinity.extensibility.component.BaseComponent.status` property.

.. note::

  Strictly speaking, there's also a special state that only applies to the
  :class:`~trinity.extensibility.component.BaseMainProcessComponent` which comes into effect when such a
  component hijacks the Trinity process entirely. That being said, in that case, the resulting process
  is in fact something entirely different than Trinity and the whole component infrastruture doesn't
  even continue to exist from the moment on where that component takes over the Trinity process. This
  is why we do not list it as an actual state of the regular component lifecycle.

Component state: ``NOT_READY``
------------------------------

Every component starts out being in the ``NOT_READY`` state. This state begins with the instantiation
of the component and lasts until the :meth:`~trinity.extensibility.component.BaseComponent.on_ready` hook
was called which happens as soon as the core infrastructure of Trinity is ready.

Component state: ``READY``
--------------------------

After Trinity has finished setting up the core infrastructure,
:meth:`~trinity.extensibility.component.BaseComponent.on_ready` is called on each component. At
this point the component has access to important information such as the parsed arguments or
the :class:`~trinity.config.TrinityConfig`. It also has access to the central event bus
via its :meth:`~trinity.extensibility.component.BaseComponent.event_bus` property which enables
the component to communicate with other parts of the application including other components.

Component state: ``STARTED``
----------------------------

A component is in the ``STARTED`` state after the
:meth:`~trinity.extensibility.component.BaseComponent.start` method was called. Components call this method
themselves whenever they want to start which may be based on some condition like Trinity being
started with certain parameters or some event being propagated on the central event bus.

.. note::
  Calling :meth:`~trinity.extensibility.component.BaseComponent.start` while the component is in the
  ``NOT_READY`` state or when it is already in ``STARTED`` will cause an exception to be raised.


Component state: ``STOPPED``
----------------------------

A component is in the ``STOPPED`` state after the 
:meth:`~trinity.extensibility.component.BaseComponent.stop` method was called and finished any tear down
work.

Defining components
~~~~~~~~~~~~~~~~~~~

We define a component by deriving from either
:class:`~trinity.extensibility.component.BaseMainProcessComponent` or
:class:`~trinity.extensibility.asyncio.AsyncioIsolatedComponent` depending on the kind of component that we
intend to write. For now, we'll stick to :class:`~trinity.extensibility.asyncio.AsyncioIsolatedComponent`
which is the most commonly used component category.

Every component needs to overwrite ``name`` so voilà, here's our first component!

.. literalinclude:: ../../trinity-external-components/examples/peer_count_reporter/peer_count_reporter_component/component.py
   :language: python
   :pyobject: PeerCountReporterComponent
   :end-before: def configure_parser

Of course that doesn't do anything useful yet, bear with us.

Configuring Command Line Arguments
----------------------------------

More often than not we want to have control over if or when a component should start. Adding
command-line arguments that are specific to such a component, which we then check, validate, and act
on, is a good way to deal with that. Implementing
:meth:`~trinity.extensibility.component.BaseComponent.configure_parser` enables us to do exactly that.

This method is called when Trinity starts and bootstraps the component system, in other words,
**before** the start of any component. It is passed an :class:`~argparse.ArgumentParser` as well as a
:class:`~argparse._SubParsersAction` which allows it to amend the configuration of Trinity's
command line arguments in many different ways.

For example, here we are adding a boolean flag ``--report-peer-count`` to Trinity.

.. literalinclude:: ../../trinity-external-components/examples/peer_count_reporter/peer_count_reporter_component/component.py
   :language: python
   :pyobject: PeerCountReporterComponent.configure_parser

To be clear, this does not yet cause our component to automatically start if ``--report-peer-count``
is passed, it simply changes the parser to be aware of such flag and hence allows us to check for
its existence later.

.. note::

  For a more advanced example, that also configures a subcommand, checkout the ``trinity attach``
  component.


Defining a components starting point
------------------------------------

Every component needs to have a well defined starting point. The exact mechanics slightly differ
in case of a :class:`~trinity.extensibility.component.BaseMainProcessComponent` but remain fairly similar
for the other types of components which we'll be focussing on for now.

Components need to implement the :meth:`~trinity.extensibility.component.BaseComponent.do_start` method
to define their own bootstrapping logic. This logic may involve setting up event listeners, running
code in a loop or any other kind of action.

.. warning::

  Technically, there's nothing preventing a component from performing starting logic in the
  :meth:`~trinity.extensibility.component.BaseComponent.on_ready` hook. However, doing that is an anti
  pattern as the component infrastructure won't know about the running component, can't propagate the
  :class:`~trinity.extensibility.events.ComponentStartedEvent` and the component won't be properly shut
  down with Trinity if the node closes.

Let's assume we want to create a component that simply periodically prints out the number of connected
peers.

While it is absolutely possible to put this logic right into the component, the preferred way is to
subclass :class:`~p2p.service.BaseService` and implement the core logic in such a standalone
service.

.. literalinclude:: ../../trinity-external-components/examples/peer_count_reporter/peer_count_reporter_component/component.py
   :language: python
   :pyobject: PeerCountReporter

Then, the implementation of :meth:`~trinity.extensibility.asyncio.AsyncioIsolatedComponent.do_start` is
only concerned about running the service on a fresh event loop.

.. literalinclude:: ../../trinity-external-components/examples/peer_count_reporter/peer_count_reporter_component/component.py
   :language: python
   :pyobject: PeerCountReporterComponent.do_start

If the example may seem unnecessarily complex, it should be noted that components can be implemented
in many different ways, but this example follows a pattern that is considered best practice within
the Trinity Code Base.

Starting a component
--------------------

As we've read in the previous section not all components should run at any point in time. In fact, the
circumstances under which we want a component to begin its work may vary from component to component.

We may want a component to only start running if:

- a certain (combination) of command line arguments was given
- another component or group of components started
- a certain number of connected peers was exceeded / undershot
- a certain block number was reached
- ...

Hence, to actually start a component, the component needs to invoke the
:meth:`~trinity.extensibility.component.BaseComponent.start` method at any moment when it is in its
``READY`` state. Let's assume a simple case in which we simply want to start the component if Trinity
is started with the ``--report-peer-count`` flag.

.. literalinclude:: ../../trinity-external-components/examples/peer_count_reporter/peer_count_reporter_component/component.py
   :language: python
   :pyobject: PeerCountReporterComponent.on_ready

In case of a :class:`~trinity.extensibility.asyncio.AsyncioIsolatedComponent`, this will cause the
:meth:`~trinity.extensibility.asyncio.AsyncioIsolatedComponent.do_start` method to run on an entirely
separated, new process. In other cases
:meth:`~trinity.extensibility.asyncio.AsyncioIsolatedComponent.do_start` will simply run in the same
process as the component manager that the component is controlled by.


Communication pattern
~~~~~~~~~~~~~~~~~~~~~

For most components to be useful they need to be able to communicate with the rest of the application
as well as other components. In addition to that, this kind of communication needs to work across
process boundaries as components will often operate in independent processes.

To achieve this, Trinity uses the
`Lahja project <https://github.com/ethereum/lahja>`_, which enables us to operate
a lightweight event bus that works across processes. An event bus is a software dedicated to the
transmission of events from a broadcaster to interested parties.

This kind of architecture allows for efficient and decoupled communication between different parts
of Trinity including components.

For instance, a component may be interested to perform some action every time that a new peer connects
to our node. These kind of events get exposed on the EventBus and hence allow a wide range of
components to make use of them.

For an event to be usable across processes it needs to be pickleable and in general should be a
shallow Data Transfer Object (`DTO <https://en.wikipedia.org/wiki/Data_transfer_object>`_)

Every component has access to the event bus via its
:meth:`~trinity.extensibility.component.BaseComponent.event_bus` property and in fact we have already
used it in the above example to get the current number of connected peers.

.. note::
  This guide will soon cover communication through the event bus in more detail. For now, the
  `Lahja documentation <https://github.com/ethereum/lahja/blob/master/README.md>`_ gives us some
  more information about the available APIs and how to use them.

Distributing components
~~~~~~~~~~~~~~~~~~~~~~~

Of course, components are more fun if we can share them and anyone can simply install them through
``pip``. The good news is, it's not hard at all!

In this guide, we won't go into details about how to create Python packages as this is already
`covered in the official Python docs <https://packaging.python.org/tutorials/packaging-projects/>`_
.

Once we have a ``setup.py`` file, all we have to do is to expose our component under
``trinity.components`` via the ``entry_points`` section.

.. literalinclude:: ../../trinity-external-components/examples/peer_count_reporter/setup.py
   :language: python

Check out the `official documentation on entry points <https://packaging.python.org/guides/creating-and-discovering-components/#using-package-metadata>`_
for a deeper explanation.

A component where the ``setup.py`` file is configured as described can be installed by
``pip install <package-name>`` and immediately becomes available as a component in Trinity.

.. note::

  Components installed from a local directory (instead of the pypi registry), such as the sample
  component described in this article, must be installed with the ``-e`` parameter (Example:
  ``pip install -e ./trinity-external-components/examples/peer_count_reporter``)
