from dataclasses import dataclass


@dataclass(frozen=True)
class AppMetadata:
    name: str = "Gerenciador PostgreSQL"
    version: str = "1.4.3"
    release_date: str = "2025-08-11"
    license: str = "MIT"
    maintainer: str = "Equipe GeoIFSC"
    contact_email: str = "contato@exemplo.org"
    github_url: str = "https://github.com/..."
