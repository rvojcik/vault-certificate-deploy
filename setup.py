from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as fh:
    install_reqs = fh.read().split()

setup(
    name="vault-certificate-deploy",
    version="1.2.1",
    packages=find_packages(),
    install_requires=install_reqs,
    license="GPLv3",
    description="System for deploying certificates from Hashicorp Vault server",
    long_description=long_description,
    long_description_content_type="text/markdown",
    include_package_data=True,
    url="https://github.com/rvojcik/vault-certificate-deploy",
    author="Robert Vojcik",
    author_email="robert@vojcik.net",
    scripts=[
        "scripts/vault-certificate-deploy",
        "scripts/vault-certificate-issue-deploy"
    ],
    keywords=['vault_certificate_deploy', 'vault_cert_deploy', 'certificate', 'vault-certificate-deploy', 'vault-cert-deploy', 'hashicorp', 'certificates'],
    classifiers=[
            "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
            "Operating System :: POSIX",
            "Operating System :: Unix",
            "Operating System :: POSIX :: Linux",
            "Programming Language :: Python",
            "Programming Language :: Python :: 2.7",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.6",
            "Programming Language :: Python :: 3.8",
            "Topic :: System :: Systems Administration",
            "Topic :: Database",
            "Topic :: Security",
            "Topic :: Security :: Cryptography"
    ]
)

