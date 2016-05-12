# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

# distutils setup script.
# users should install with: `$ pip3 install muck`
# developers can make a local install with: `$ pip3 install -e .`
# upload to pypi test server with: `$ py3 setup.py sdist upload -r pypitest`
# upload to pypi prod server with: `$ py3 setup.py sdist upload`

from setuptools import setup


long_description = '''\
Muck is a build tool; given a target (a file to be built), it looks in the current directory for a source file with a matching name, determines its dependencies, recursively builds those, and then finally builds the target. Unlike traditional build systems such as Make, Muck determines the dependencies of a given file by analyzing the file source; there is no 'makefile'. This means that Muck is limited to source languages that it understands, and to source code written using Muck conventions. Muck also provides conventional functions that imply data dependencies, allowing data transformation projects to be organized as a series of dependent steps. See readme.wu for documentation.
'''

setup(
  name='muck',
  license='CC0',
  version='0.0.0',
  author='George King',
  author_email='george.w.king@gmail.com',
  url='https://github.com/gwk/muck',
  description='Muck is a build tool that automatically calculates dependencies.',
  long_description=long_description,
  install_requires=['pithy', 'writeup-tool'],
  py_modules=['muck'],
  entry_points = { 'console_scripts': [
    'muck=muck:main',
  ]},
  keywords=['documentation', 'markup'],
  classifiers=[ # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    'Development Status :: 3 - Alpha',
    'Environment :: Console',
    'Intended Audience :: Developers',
    'Intended Audience :: Education',
    'Intended Audience :: Information Technology',
    'Intended Audience :: Science/Research',
    'License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication',
    'Programming Language :: Python :: 3 :: Only',
    'Topic :: Documentation',
    'Topic :: Education',
    'Topic :: Internet',
    'Topic :: Multimedia',
    'Topic :: Software Development',
    'Topic :: Software Development :: Build Tools',
    'Topic :: Software Development :: Documentation',
    'Topic :: Text Processing',
    'Topic :: Text Processing :: Markup',
    'Topic :: Text Processing :: Markup :: HTML',
  ],
)