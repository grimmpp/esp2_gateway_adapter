import os
from setuptools import setup, find_packages
from distutils.core import setup



base_dir = os.path.dirname(__file__)

# with open(os.path.join(base_dir, 'README.md'), encoding="utf-8") as f:
with open('README.md', encoding="utf-8") as f:
    long_description = f.read()

# with open(os.path.join(base_dir, 'LICENSE'), encoding="utf-8") as f:
with open('LICENSE', encoding="utf-8") as f:
    license = f.read()

required = ['eltako14bus>=0.0.46', 'enocean>=0.60.1', 'pyserial', 'pyserial-asyncio', 'aiocoap', 'zeroconf>=0.132.2']



setup(
    name='esp2_gateway_adapter',
    version='0.2.14',
    package_dir={"esp2_gateway_adapter":'src'},
    package=[""],
    include_package_data=True,
    install_requires=required,
    author="Philipp Grimm",
    description="Protocol adapter from esp3 to esp2 for Home Assistant Eltako Integration",
    long_description=long_description,
    long_description_content_type='text/markdown',
    license=license,
    url="https://github.com/grimmpp/esp2_gateway_adapter",
    python_requires='>=3.7',
)

#.\.venv\Scripts\python.exe -m build --sdistx1xxx
#python setup.py bdist_wheel
