import socket
from eltakobus.util import b2s
from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo

class MyListener:
    def add_service(self, zeroconf: Zeroconf, type, name):
        out = f"Service {name}, Type: {type}"
        try:
            info:ServiceInfo = zeroconf.get_service_info(type, name)
            out += f"    address: {socket.inet_ntoa(info.addresses[0])}, port: {info.port}, hostname: {info.server}"
        except:
            pass
        # print(f"TXT Records: {info.properties}")
        print(out)

    def remove_service(self, zeroconf, type, name):
        print(f"Service {name} removed")

    def update_service(self, zeroconf, type, name):
        print(f"Service {name} updated")


zeroconf = Zeroconf()
listener = MyListener()
browser = ServiceBrowser(zeroconf, "_services._dns-sd._udp.local.", listener)


# browser = ServiceBrowser(zeroconf, "_tcp.local.", listener)
browser = ServiceBrowser(zeroconf, "_bsc-sc-socket._tcp.local.", listener)
# browser = ServiceBrowser(zeroconf, "_home-assistant._tcp.local.", listener)
# browser = ServiceBrowser(zeroconf, "_virtual-network-gateway-adapter._bsc-sc-socket._tcp.local.", listener)





try:
    input("Press enter to exit...\n\n")
finally:
    zeroconf.close()
