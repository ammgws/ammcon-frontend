# Define byte commands used to communicate commands to microcontroller
# [INIT] [TYPE] [CMD] [END]
# TYPE: AC = aircon
#       Bx = lighting
#       C1 = TV
#       FF = temp sensor

ACoff   = b'\xCE\xAC\x00\x7F'
ACsleep = b'\xCE\xAC\x01\x7F'
ACcheck = b'\xCE\xAC\x02\x7F'

temp    = b'\xCE\xFF\xFF\x7F'

bedroom_lights_off   = b'\xCE\xB1\x00\x7F'
bedroom_lights_on    = b'\xCE\xB1\x01\x7F'
bedroom_lights_down  = b'\xCE\xB1\x02\x7F'
bedroom_lights_up    = b'\xCE\xB1\x03\x7F'
bedroom_lights_full  = b'\xCE\xB1\x04\x7F'
bedroom_lights_night = b'\xCE\xB1\x05\x7F'

myroom_lights_off   = b'\xCE\xB2\x00\x7F'
myroom_lights_on    = b'\xCE\xB2\x01\x7F'
myroom_lights_down  = b'\xCE\xB2\x02\x7F'
myroom_lights_up    = b'\xCE\xB2\x03\x7F'
myroom_lights_full  = b'\xCE\xB2\x04\x7F'
myroom_lights_night = b'\xCE\xB2\x05\x7F'

kayoroom_lights_off   = b'\xCE\xB3\x00\x7F'
kayoroom_lights_on    = b'\xCE\xB3\x01\x7F'
kayoroom_lights_down  = b'\xCE\xB3\x02\x7F'
kayoroom_lights_up    = b'\xCE\xB3\x03\x7F'
kayoroom_lights_full  = b'\xCE\xB3\x04\x7F'
kayoroom_lights_night = b'\xCE\xB3\x05\x7F'

living_lights_off     = b'\xCE\xB4\x00\x7F'
living_lights_on      = b'\xCE\xB4\x01\x7F'
living_lights_low     = b'\xCE\xB4\x02\x7F'
living_lights_chuukan = b'\xCE\xB4\x03\x7F'
living_lights_yellow  = b'\xCE\xB4\x04\x7F'
living_lights_night   = b'\xCE\xB4\x05\x7F'
living_lights_blue    = b'\xCE\xB4\x06\x7F'

living_lights_new_off = b'\xCE\xB5\x00\x7F'
living_lights_new_on  = b'\xCE\xB5\x01\x7F'

living_lights_all_off = b'\xCE\xB6\x00\x7F'
living_lights_all_on  = b'\xCE\xB6\x01\x7F'

tv_pwr    = b'\xCE\xC1\x00\x7F'
tv_mute   = b'\xCE\xC1\x01\x7F'
tv_switch = b'\xCE\xC1\x02\x7F'