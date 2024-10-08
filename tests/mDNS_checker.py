from zeroconf import Zeroconf, ServiceBrowser

class MyListener:
    def add_service(self, zeroconf, type, name):
        print(f"Service {name} added, type: {type}")

    def remove_service(self, zeroconf, type, name):
        print(f"Service {name} removed")

zeroconf = Zeroconf()
listener = MyListener()
browser = ServiceBrowser(zeroconf, "_http._tcp.local.", listener)

try:
    input("Press enter to exit...\n\n")
finally:
    zeroconf.close()
