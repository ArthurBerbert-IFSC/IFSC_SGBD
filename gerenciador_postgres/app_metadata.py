from dataclasses import dataclass


@dataclass(frozen=True)
class AppMetadata:
    name: str = "Usuários GeoIFSC"
    version: str = "V0.0.3 - Beta"
    release_date: str = "2025-08-11"
    license: str = "MIT"
    maintainer: str = "Arthur Berbert"
    contact_email: str = "arthur.berbert@ifsc.edu.br"
    github_url: str = "https://github.com/ArthurBerbert-IFSC/IFSC_SGBD"
