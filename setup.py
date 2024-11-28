from setuptools import setup, find_packages

setup(
    name = 'leaps',
    version = '1.0.1',
    packages = find_packages(),
    install_requires = [
        "Flask==1.0",
        "Flask-Login==0.2.6",
        "Flask-WTF==0.8.4",
        "requests==1.1.0",
        "tinycss2==0.6.1",
        "cairocffi==0.5",
        "WeasyPrint==0.40",
        "Flask-WeasyPrint==0.4"
    ],
    url = 'http://cottagelabs.com/',
    author = 'Cottage Labs',
    author_email = 'us@cottagelabs.com',
    description = 'A web API layer over an ES backend, with various useful plugins',
    license = 'Copyheart',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: Copyheart',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
)
