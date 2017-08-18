import miniupnpc


def add_portmap(port, proto, label=''):
    u = miniupnpc.UPnP()
    u.discoverdelay = 200
    try:
        # select an igd
        u.selectigd()
        # find a free port for the redirection
        eport = port
        r = u.getspecificportmapping(eport, proto)
        while r is not None and eport < 65536:
            eport = eport + 1
            r = u.getspecificportmapping(eport, proto)
        b = u.addportmapping(eport, proto, u.lanaddr, port, label, '')
        if b:
            return u
        else:
            # TODO: log
            pass
    except Exception as e:
        # TODO: log
        pass


def remove_portmap(u, port, proto):
    if not u:
        return
    try:
        b = u.deleteportmapping(port, proto)
        if b:
            # TODO: log
            pass
        else:
            # TODO: log
            pass
    except Exception as e:
        # TODO: log
        pass
