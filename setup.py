from setuptools import setup, find_packages

setup(
    name='flask-mini-api',
    version='0.1.1',
    description='A lightweight wrapper around Flask with built-in Cloudflare tunneling and colored logging.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Gryldicek',
    packages=find_packages(),
    install_requires=[
        'Flask>=2.0.0',

    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
