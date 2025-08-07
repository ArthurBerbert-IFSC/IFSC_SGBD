# IFSC_SGBD

## Installation

This project uses [pip-tools](https://github.com/jazzband/pip-tools) to manage Python dependencies. Pinned versions are stored in `requirements.lock.txt`.

```bash
pip install -r requirements.lock.txt
```

To modify or update dependencies, edit `requirements.in` and regenerate the lock file:

```bash
pip-compile requirements.in --output-file=requirements.lock.txt
```

