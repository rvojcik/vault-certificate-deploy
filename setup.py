from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as fh:
    install_reqs = fh.read().split()

setup(
    name="vault-certificate-deploy",
    version="1.0.0",
    packages=["vault_certificate_deploy"],
    install_requires=install_reqs,
    license="GPLv3",
    description="System for deploying certificates from Hashicorp Vault server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rvojcik/vault-certificate-deploy",
    author="Robert Vojcik",
    author_email="robert@vojcik.net",
    scripts=[
        "scripts/vault-certificate-deploy"
    ],
    keywords=['vault_certificate_deploy', 'certificate', 'vault-certificate-deploy', 'vault-cert-deploy'],
    classifiers=[
            "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
            "Operating System :: POSIX",
            "Operating System :: Unix",
            "Programming Language :: Python",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3",
            "Topic :: Database"
    ]
)


