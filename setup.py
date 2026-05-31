from setuptools import find_packages, setup

setup(
    name="jottr",
    version="2.2.0",
    description="Modern text editor for writers and journalists",
    author="mFat",
    author_email="newmfat@gmail.com",
    url="https://github.com/mfat/jottr",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    package_data={"jottr": ["vendor/*.js"]},
    include_package_data=True,
) 
