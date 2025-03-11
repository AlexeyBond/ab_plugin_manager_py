from setuptools import setup, find_packages

setup(
    name="ab_plugin_manager",
    version="0.1.1",

    author="Alexey Bondarenko",
    author_email="alexey.bond.94.55@gmail.com",

    packages=find_packages(where=".", exclude=["*.tests"]),

    url="https://github.com/AlexeyBond/ab_plugin_manager_py",

    license="MIT",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries",
    ],
)
