try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

config = {
    'description': 'Ammcon server',
    'author': 'ammgws',
    'url': 'https://github.com/ammgws/ammcon',
    'download_url': 'https://github.com/ammgws/ammcon',
    'author_email': 'ammgws@users.noreply.github.com',
    'version': '1.0',
    'install_requires': ['nose'],
    'packages': ['NAME'],
    'scripts': [],
    'name': 'ammcon'
}

setup(**config)
