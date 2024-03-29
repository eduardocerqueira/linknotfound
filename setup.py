import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="linknotfound",
    version="0.0.4",
    author="Eduardo Cerqueira",
    author_email="eduardomcerqueira@gmail.com",
    description="cli tool to find broken links in applications source code",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/eduardocerqueira/linknotfound",
    project_urls={
        "Bug Tracker": "https://github.com/eduardocerqueira/linknotfound/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Linux",
    ],
    packages=setuptools.find_packages(include=["linknotfound", "linknotfound.*"]),
    install_requires=[
        "boto3==1.26.48",
        "click==8.1.3",
        "Flask==2.2.2",
        "gevent==22.10.2",
        "GitPython==3.1.27",
        "PyGithub==1.55",
        "requests==2.28.1",
        "retry==0.9.2",
    ],
    py_modules=["linknotfound"],
    entry_points={
        "console_scripts": [
            "linknotfound = linknotfound.main:cli",
        ],
    },
)
