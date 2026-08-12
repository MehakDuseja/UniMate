from setuptools import find_packages, setup

setup(
    name="unimate",
    version="0.1.0",
    description="University admissions scraping, ingestion, and RAG recommender agent for Pakistani universities.",
    author="UniMate Team",
    # src/ and agent/ are both real top-level packages at the repo root (each
    # has its own __init__.py there) - package_dir={"": "src"} previously
    # remapped the root to src/, which combined with find_packages(include=
    # ["src", "src.*"]) would have looked for src/src/__init__.py and broken
    # `pip install -e .`.
    packages=find_packages(include=["src", "src.*", "agent", "agent.*"]),
    install_requires=[
        "requests",
        "beautifulsoup4",
        "lxml",
        "tqdm",
        "pdfplumber",
        "PyMuPDF",
        "pandas",
        "pydantic",
        "chromadb",
        "google-genai",
        "sentence-transformers",
        "langgraph",
        "python-dotenv",
        "Flask",
        "gunicorn",
    ],
    python_requires=">=3.11",
    entry_points={
        "console_scripts": [
            "unimate-scrape=university_scraper:main",
            "unimate-ingest=src.ingest_and_vectorize:main",
            "unimate-agent=agent.cli:main",
        ]
    },
    include_package_data=True,
    zip_safe=False,
)
