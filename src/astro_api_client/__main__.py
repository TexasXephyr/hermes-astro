"""
CLI entry point for astro_api_client.

Re-exports the argparse CLI from client.py so that
`python -m astro_api_client natal ...` works when the package is installed.
"""
from .client import main

if __name__ == "__main__":
    main()
