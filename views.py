from ammcon_webui import app

@app.route('/')
def index():
    return 'Hello World!'