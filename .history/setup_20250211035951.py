from setuptools import setup, find_packages

setup(
    name="jottr",
    version="1.0",
    description="Modern text editor for writers and journalists",
    author="mFat",
    author_email="newmfat@gmail.com",
    url="https://github.com/mfat/jottr",
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
) 