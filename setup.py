"""Setup script for post-genesis4 package."""

from setuptools import setup, find_packages
import os

# Read README if exists
readme_path = os.path.join(os.path.dirname(__file__), "README.md")
long_description = ""
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="post-genesis4",
    version="1.0.0",
    author="Haiyang Li",
    description="A PyQt5 GUI application for visualizing Genesis4 output files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mulingLHY/post-genesis4",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Visualization",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PyQt5>=5.15.0",
        "h5py>=3.0.0",
        "numpy>=1.20.0",
        "matplotlib>=3.4.0",
        "scipy>=1.7.0",
    ],
    entry_points={
        "gui_scripts": [
            "post-genesis4=post_genesis4.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
