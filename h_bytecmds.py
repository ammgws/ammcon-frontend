# Define byte commands used to communicate commands to microcontroller
# [INIT] [TYPE] [CMD] [END]
# TYPE':AC = aircon
#  Bx = lighting
#  C1 = TV
#  FF = temp sensor

micro_commands = {  'AC off':b'\xCE\xAC\x00\x7F',
                    'AC sleep':b'\xCE\xAC\x01\x7F',
                    'AC check':b'\xCE\xAC\x02\x7F',
                    'temp':b'\xCE\xFF\xFF\x7F',
                    
                    'bedroom off':b'\xCE\xB1\x00\x7F',
                    'bedroom on':b'\xCE\xB1\x01\x7F',
                    'bedroom down':b'\xCE\xB1\x02\x7F',
                    'bedroom up':b'\xCE\xB1\x03\x7F',
                    'bedroom full':b'\xCE\xB1\x04\x7F',
                    'bedroom night':b'\xCE\xB1\x05\x7F',

                    'myroom off':b'\xCE\xB2\x00\x7F',
                    'myroom on':b'\xCE\xB2\x01\x7F',
                    'myroom down':b'\xCE\xB2\x02\x7F',
                    'myroom up':b'\xCE\xB2\x03\x7F',
                    'myroom full':b'\xCE\xB2\x04\x7F',
                    'myroom night':b'\xCE\xB2\x05\x7F',

                    'kayoroom off':b'\xCE\xB3\x00\x7F',
                    'kayoroom on':b'\xCE\xB3\x01\x7F',
                    'kayoroom down':b'\xCE\xB3\x02\x7F',
                    'kayoroom up':b'\xCE\xB3\x03\x7F',
                    'kayoroom full':b'\xCE\xB3\x04\x7F',
                    'kayoroom night':b'\xCE\xB3\x05\x7F',

                    # Living room light no.1 (older one)
                    'living1 off':b'\xCE\xB4\x00\x7F',
                    'living1 on':b'\xCE\xB4\x01\x7F',
                    'living1 low':b'\xCE\xB4\x02\x7F',
                    'living1 mix':b'\xCE\xB4\x03\x7F',
                    'living1 yellow':b'\xCE\xB4\x04\x7F',
                    'living1 night':b'\xCE\xB4\x05\x7F',
                    'living1 blue':b'\xCE\xB4\x06\x7F',

                    # Living room light no.2 (new). Controls older light as well with its IR signal
                    'living off':b'\xCE\xB5\x00\x7F',
                    'living on':b'\xCE\xB5\x01\x7F',

                    'tv on':b'\xCE\xC1\x00\x7F',
                    'tv off':b'\xCE\xC1\x00\x7F',
                    'tv mute':b'\xCE\xC1\x01\x7F',
                    'tv switch':b'\xCE\xC1\x02\x7F'
                }