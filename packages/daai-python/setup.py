from setuptools import find_packages, setup


setup(
    name="daai-python",
    version="0.1.0",
    description="DAAI Console Python SDK",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "httpx>=0.28.0,<1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.4.0,<9.0.0",
        ]
    },
)
