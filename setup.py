# noinspection Mypy
from setuptools import setup, find_packages
from os import path, getcwd

# from https://packaging.python.org/tutorials/packaging-projects/

# noinspection SpellCheckingInspection
package_name = "patient_matching"

with open("README.md", "r") as fh:
    long_description = fh.read()

try:
    with open(path.join(getcwd(), "VERSION")) as version_file:
        version = version_file.read().strip()
except IOError:
    raise


# classifiers list is here: https://pypi.org/classifiers/

# create the package setup
setup(
    name=package_name,
    version=version,
    author="icanbwell",
    author_email="",
    description="CMS Patient Matching Implementation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/icanbwell/patient-matching-reference-implementation",
    packages=find_packages(),
    install_requires=[],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    dependency_links=[],
    include_package_data=True,
    zip_safe=False,
    package_data={"patient_matching": ["py.typed"]},
)
