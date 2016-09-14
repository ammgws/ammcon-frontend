# Serial framing control bytes
hdr = b'\x3C'
end = b'\x3E'
esc = b'\x7C'
ack = b'\x06'
nak = b'\x15'

# CRC bytes
poly = 0xE7
init = 0x5A

# Define byte commands used to communicate commands to microcontroller
#  AC = aircon
#  Bx = lighting
#  C1 = TV
#  Dx = temp sensor
micro_commands = {'living AC off': b'\xAC\x00',
                  'living AC auto': b'\xAC\x01',

                  'bedroom2 AC off': b'\xAD\x01',
                  'bedroom2 AC auto': b'\xAD\x01',

                  'bedroom3 AC off': b'\xAE\x01',
                  'bedroom3 AC auto': b'\xAE\x01',
                  
                  'temp': b'\xD1',
                  'templiving': b'\xD1',
                  'tempbedroom2': b'\xD1\x01',
                  'tempbedroom3': b'\xD1\x02',

                  'bedroom off': b'\xB1\x00',
                  'bedroom on': b'\xB1\x01',
                  'bedroom down': b'\xB1\x02',
                  'bedroom up': b'\xB1\x03',
                  'bedroom full': b'\xB1\x04',
                  'bedroom night': b'\xB1\x05',

                  'myroom off': b'\xB2\x00',
                  'myroom on': b'\xB2\x01',
                  'myroom down': b'\xB2\x02',
                  'myroom up': b'\xB2\x03',
                  'myroom full': b'\xB2\x04',
                  'myroom night': b'\xB2\x05',

                  'kayoroom off': b'\xB3\x00',
                  'kayoroom on': b'\xB3\x01',
                  'kayoroom down': b'\xB3\x02',
                  'kayoroom up': b'\xB3\x03',
                  'kayoroom full': b'\xB3\x04',
                  'kayoroom night': b'\xB3\x05',

                  # Living room light no.1 (newer one)
                  'living1 off': b'\xB4\x00',
                  'living1 on': b'\xB4\x01',
                  'living1 low': b'\xB4\x02',
                  'living1 night': b'\xB4\x05',

                  # Living room light no.2
                  'living2 off': b'\xB5\x00',
                  'living2 on': b'\xB5\x01',
                  'living2 low': b'\xB5\x02',
                  'living2 mix': b'\xB5\x03',
                  'living2 yellow': b'\xB5\x04',
                  'living2 night': b'\xB5\x05',
                  'living2 blue': b'\xB5\x06',
                  
                  # Living room (both).
                  'living off': b'\xB6\x00',
                  'living on': b'\xB6\x01',                  

                  'tv on': b'\xC1\x00',
                  'tv off': b'\xC1\x00',
                  'tv mute': b'\xC1\x01',
                  'tv switch': b'\xC1\x02'
                  }
