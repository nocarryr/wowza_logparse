from NetlinxDMX import NetlinxDMX
from usb_pro import USBProIO
from artnet.manager import ArtnetManager

class olaLoader(type):
    ui_name = 'OLA (Open Lighting Architecture)'
    def __new__(self, *args, **kwargs):
        from dmx.OSCtoOLA import OSCtoOLAHost
        return OSCtoOLAHost(*args, **kwargs)

IO_LOADER = {'NetlinxDMX':NetlinxDMX,
             'ola_IO':olaLoader,
             'USBPro':USBProIO,
             'Artnet':ArtnetManager}
