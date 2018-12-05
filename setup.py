from setuptools import setup, find_packages

package = 'pynd'
version = '0.0.9000'

setup(name=package,
      version=version,
      packages=find_packages(),
      install_requires=[
          'pandas',
      ],
      description="Calculate sign neighborhood density",
      url='url')
