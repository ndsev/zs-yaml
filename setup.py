import os
from setuptools import setup, find_packages
import subprocess


# Utility function to read file content into a string
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname),
                'r', encoding='utf-8').read()

# DOCUMENTATION
def read_for_pypi(fname):
    """Read a file and replace relative image URLs with absolute URLs."""
    content = read(fname)
    # Replace relative image URLs with absolute URLs
    # Adjust the base URL to where your images are actually hosted
    base_url = "https://raw.githubusercontent.com/ndsev/zs_yaml/main/"
    content = content.replace("](images/", f"]({base_url}images/")
    return content


# REQUIREMENTS
def read_requirements(fname):
    return [line.strip() for line in read(fname).splitlines() if line.strip() and not line.startswith('#')]

# VERSION INFO
def get_version_info():
    version_file = os.path.join(os.path.dirname(__file__), 'zs_yaml', '_version.py')
    version_info = {}
    with open(version_file, 'r', encoding='utf-8') as f:
        exec(f.read(), version_info)

    # Get the Git commit ID if possible
    try:
        commit_id = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode('ascii').strip()
        version_info['__commit_id__'] = commit_id
    except:
        pass  # If Git is not available or not a Git repository, use the default "unknown"

    return version_info

version_info = get_version_info()

# Write the updated version info back to the file
with open(os.path.join('zs_yaml', '_version.py'), 'w', encoding='utf-8') as f:
    f.write(f"__version__ = '{version_info['__version__']}'\n")
    f.write(f"__commit_id__ = '{version_info['__commit_id__']}'\n")


setup(
    name='zs-yaml',
    version=version_info['__version__'],
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
