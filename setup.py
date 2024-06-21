import os
from setuptools import setup, find_packages


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname),
                'r', encoding='utf-8').read()


def read_for_pypi(fname):
    """Read a file and replace relative image URLs with absolute URLs."""
    content = read(fname)
    # Replace relative image URLs with absolute URLs
    # Adjust the base URL to where your images are actually hosted
    base_url = "https://raw.githubusercontent.com/ndsev/zs_yaml/main/"
    content = content.replace("](images/", f"]({base_url}images/")
    return content


def read_requirements(fname):
    return [line.strip() for line in read(fname).splitlines() if line.strip() and not line.startswith('#')]


setup(
    name='zs_yaml',
    version='0.1.0',
    author="Navigation Data Standard e.V.",
    author_email="support@nds-association.org",
    description='A package that allows using yaml to define zserio objects.',
    long_description=read_for_pypi('README.md'),
    long_description_content_type="text/markdown",
    url="https://github.com/ndsev/zs_yaml",
    packages=find_packages(),
    install_requires=read_requirements('requirements.txt'),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
    entry_points={
        'console_scripts': [
            'zs-yaml=zs_yaml.main:main'
        ],
    },
    include_package_data=True,
    package_data={
        'zs_yaml': ['images/*'],
    },
    ext_modules=[],
    cmdclass={}
)
