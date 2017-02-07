from setuptools import find_packages, setup

with open('README.md') as f:
    readme_text = f.read()

with open('LICENSE') as f:
    license_text = f.read()

setup(
    name='ammcon_frontend',
    version='0.2.3',
    long_description=readme_text,
    url='http://github.com/ammgws/ammcon-frontend',
    packages=find_packages(exclude=('tests', 'docs')),
    include_package_data=True,
    license=license_text,
    zip_safe=False,
    install_requires=[
        'Flask>=0.11.1',
        'Flask-Admin>=1.4.2',
        'Flask-Security>=1.7.5',
        'Flask-SQLAlchemy>=2.1',
        'gunicorn',
        'marshmallow',
        'marshmallow_sqlalchemy',
        'pyserial>=3.1.1',
        'rauth>=0.7.2',
        'requests',
        'simplejson',
        'SQLAlchemy',
        'sqlalchemy_utils',
        'zmq',
    ],
)
