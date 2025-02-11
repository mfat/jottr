from setuptools import setup, find_packages
import os

# Default requirements if requirements.txt is not found
default_requires = [
    "PyQt5>=5.15.0",
    "PyQtWebEngine>=5.15.0",
    "pyspellchecker>=0.7.2",
    "feedparser>=6.0.0",
    "requests>=2.31.0",
]

# Try to read requirements.txt, fall back to defaults if not found
try:
    with open('requirements.txt') as f:
        requirements = f.read().splitlines()
except FileNotFoundError:
    requirements = default_requires

setup(
    name="jottr",
    version="1.0",
    description="Modern text editor for writers and journalists",
    long_description="""Jottr is a feature-rich text editor designed specifically
for writers and journalists, with features like smart
completion, snippets, and integrated web browsing.""",
    author="mFat",
    author_email="newmfat@gmail.com",
    url="https://github.com/mfat/jottr",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'jottr=jottr.main:main',
        ],
    },
    data_files=[
        ('share/applications', ['packaging/debian/jottr.desktop']),
        ('share/icons/hicolor/128x128/apps', ['jottr/icons/jottr.png']),
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: X11 Applications :: Qt',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: GPL-3.0+',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Topic :: Text Editors',
    ],
) 