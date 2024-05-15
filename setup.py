from setuptools import setup, find_packages

setup(
    name='zs_yaml',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'PyYAML',
        'zserio'
    ],
    entry_points={
        'console_scripts': [
                'zs-yaml=main:main'
        ],
    },
)
