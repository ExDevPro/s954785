#!/usr/bin/env python3
"""
Setup script for Bulk Email Sender application.
"""

from setuptools import setup, find_packages
import os

# Read the contents of README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# Read requirements
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
    name="bulk-email-sender",
    version="2.0.0",
    description="Professional bulk email sender with modular architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ExDevPro",
    author_email="",
    url="https://github.com/ExDevPro/s954785",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    python_requires=">=3.8",
    entry_points={
        'console_scripts': [
            'bulk-email-sender=main:main',
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Communications :: Email",
        "Topic :: Office/Business",
    ],
    package_data={
        '': ['*.json', '*.qss', '*.png', '*.ico', '*.ttf', '*.otf'],
        'assets': ['**/*'],
        'config': ['*.json'],
    },
    options={
        'build_exe': {
            'packages': ['PyQt6', 'email', 'smtplib', 'ssl'],
            'includes': ['PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
            'include_files': [
                ('assets/', 'assets/'),
                ('config/', 'config/'),
            ],
        },
    },
)