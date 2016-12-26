from setuptools import setup

setup(
    name='AmmCon',
    version='0.2',
    long_description=__doc__,
    url='http://github.com/ammgws/ammcon',
    packages=['ammcon'],
    include_package_data=True,
    zip_safe=False,
    install_requires=['configparser',
                      'crccheck>=0.6',
                      'Flask>=0.11.1',
                      'Flask-Login>=0.3.2',
                      'gunicorn',
                      'pyserial>=3.1.1',
                      'rauth>=0.7.2',
                      'requests',
                      'simplejson',
                      'SQLAlchemy',
                      'pyzmq']
)
