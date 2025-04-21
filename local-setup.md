# 🛠 Local Development Setup Guide

This document explains how to set up and activate the local Python environment for the **Invoice Extraction LLM** project using Poetry (v2+).

---

## 📦 Prerequisites

- Python 3.9 – 3.12 installed
- [Poetry 2.x](https://python-poetry.org/docs/#installation) installed

Check versions:

```bash
python --version
poetry --version
```

---

## 🚀 Project Setup Steps

### 1. Clone the repository

```bash
git clone https://github.com/RishiMahamuni/DOEXT.git
cd invoice-extraction-llm
```

### 2. Install dependencies

This will create a virtual environment and install all required packages.

```bash
poetry install
```

---

## ⚙️ Activating the Virtual Environment


### Option B: (Optional) Use `poetry shell` (Requires plugin)

```bash
poetry self add poetry-plugin-shell
poetry shell
```

---

## 🧪 Jupyter Notebook Support

To use this environment in Jupyter:

```bash
poetry run python -m ipykernel install --user --name=invoice-llm-env
```

You can now select `invoice-llm-env` as a kernel in Jupyter or VS Code.

---

## 🧼 Deactivating

To exit the virtual environment:

```bash
deactivate
```

---

## ✅ Helpful Commands

```bash
poetry add <package-name>           # Add package to pyproject.toml
poetry update                       # Update all packages
poetry run <command>                # Run a command in the virtualenv
poetry env list                     # Show all Poetry-managed environments
```

---
