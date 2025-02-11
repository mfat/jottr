from setuptools import setup, find_packages

setup(
    name="jottr",
    version="0.0.0",  # This will be replaced during build
    packages=find_packages(),
    install_requires=[
        "PyQt5",
        "PyQtWebEngine",
        "feedparser",
    ],
    entry_points={
        'console_scripts': [
            'jottr=jottr.main:main',
        ],
    },
    package_data={
        'jottr': ['help/*'],
    },
) 