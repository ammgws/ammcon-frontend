from jinja2 import Markup

# TODO: need to figure out how to keep both jquery oriented version and standard JS version

class momentjs(object):
    def __init__(self, timestamp, attrid):
        self.timestamp = timestamp
        self.attrid = attrid

    def render(self, fmt):
        return Markup("<script>\n$(\"#%s\").html(moment(\"%s\").%s);\n</script>" % (self.attrid, self.timestamp.strftime("%Y-%m-%dT%H:%M:%S Z"), fmt))

    def render_std(self, fmt):
        return Markup("<script>\ndocument.write(moment(\"%s\").%s);\n</script>" % (self.timestamp.strftime("%Y-%m-%dT%H:%M:%S Z"), fmt))

    def format(self, fmt):
        return self.render("format(\"%s\")" % fmt)

    def calendar(self):
        return self.render("calendar()")

    def fromNow(self):
        return self.render("fromNow()")
