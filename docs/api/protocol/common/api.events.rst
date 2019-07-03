Events
======

Common Protocol Events
----------------------

Common events used for all peer protocols. These events derive from :class:`~lahja.BaseEvent` and
can thus be consumed through the event bus.

.. autoclass:: trinity.protocol.common.events.ConnectToNodeCommand
  :members:

.. autoclass:: trinity.protocol.common.events.PeerCountRequest
  :members:

.. autoclass:: trinity.protocol.common.events.PeerCountResponse
  :members:

.. autoclass:: trinity.protocol.common.events.DisconnectPeerEvent
  :members:

.. autoclass:: trinity.protocol.common.events.PeerJoinedEvent
  :members:

.. autoclass:: trinity.protocol.common.events.PeerLeftEvent
  :members:

.. autoclass:: trinity.protocol.common.events.GetConnectedPeersRequest
  :members:

.. autoclass:: trinity.protocol.common.events.GetConnectedPeersResponse
  :members:

.. autoclass:: trinity.protocol.common.events.PeerPoolMessageEvent
  :members:
