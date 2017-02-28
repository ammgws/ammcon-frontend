from jinja2 import Markup


class momentjs(object):
    def __init__(self, timestamp, attrid):
        self.timestamp = timestamp
        self.attrid = attrid

    def render(self, fmt):
        return Markup("<script>\n$(\"#%s\").append(moment(\"%s\").%s);\n</script>" % ( self.attrid, self.timestamp.strftime("%Y-%m-%dT%H:%M:%S Z"), fmt))

    def format(self, fmt):
        return self.render("format(\"%s\")" % fmt)

    def calendar(self):
        return self.render("calendar()")

    def fromNow(self):
        return self.render("fromNow()")
