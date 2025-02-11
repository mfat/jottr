from setuptools import setup, find_packages
import os

# Read requirements from requirements.txt
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

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