from jinja2 import Markup


class momentJS(object):
    def __init__(self, timestamp, attr_id=None, script_type='jQuery'):
        self.timestamp = timestamp
        self.attr_id = attr_id
        self.script_type = script_type

    def render(self, fmt):
        if self.script_type == 'jQuery':
            return Markup("<script>\n$(\"#%s\").html(moment(\"%s\").%s);\n</script>" % (self.attr_id, self.timestamp.strftime("%Y-%m-%dT%H:%M:%S Z"), fmt))
        elif self.script_type == 'standard':
            return Markup("<script>\ndocument.write(moment(\"%s\").%s);\n</script>" % (self.timestamp.strftime("%Y-%m-%dT%H:%M:%S Z"), fmt))

    def format(self, fmt):
        return self.render("format(\"%s\")" % fmt)

    def calendar(self):
        return self.render("calendar()")

    def fromNow(self):
        return self.render("fromNow()")
