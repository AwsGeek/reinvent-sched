import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="reInventSched",
    version="0.0.1",

    description="reInventSched",
    long_description=long_description,
    long_description_content_type="text/markdown",

    author="author",

    package_dir={"": "reInventSched"},
    packages=setuptools.find_packages(where="reInventSched"),

    install_requires=[
        "aws-cdk.core",
        "aws-cdk.aws_iam",
        "aws-cdk.aws_lambda",
        "aws-cdk.aws_events",
        "aws-cdk.aws_stepfunctions",
        "aws-cdk.aws_secretsmanager",
        "aws-cdk.aws_stepfunctions_tasks"
    ],

    python_requires=">=3.6",

    classifiers=[
        "Development Status :: 4 - Beta",

        "Intended Audience :: Developers",

        "License :: OSI Approved :: Apache Software License",

        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",

        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",

        "Typing :: Typed",
    ],
)
