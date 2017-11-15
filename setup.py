from setuptools import find_packages, setup

setup(
    name='kube-exec',
    packages=find_packages(),
    entry_points={'console_scripts': [
        'kube-exec = kube_exec.__main__:main',
    ]},
    install_requires=['kubernetes'],
)
