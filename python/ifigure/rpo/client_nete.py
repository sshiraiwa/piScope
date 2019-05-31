#
#  example program to connect proxy_efit
#
import sys
import Pyro4
import Pyro4.util

sys.excepthook = Pyro4.util.excepthook

nshost = 'cmodws30.psfc.mit.edu'
nameserver = Pyro4.locateNS(host=nshost)
uri = nameserver.lookup("proxy_nete")
proxy = Pyro4.Proxy(uri)
print((proxy.run_idl(shot=1120710012, time=1.)))
