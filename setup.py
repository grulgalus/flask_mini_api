from setuptools import setup, find_packages

setup(
    name='flask-mini-api',       
    version='0.1.2',             
    description='A lightweight wrapper around Flask with built-in Cloudflare tunneling and colored logging.',
    long_description=open('README.md', encoding='utf-8').read(),
    long_description_content_type='text/markdown',
    author=['Gryldicek', 'dragprog'],        
    packages=find_packages(),    
    install_requires=[           
        'Flask>=2.0.0',
        'pycloudflared>=0.2.0',  # <-- TADY JE PŘIDANÝ CLOUDFLARE
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
    ],
)
