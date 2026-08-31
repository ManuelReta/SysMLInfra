# SysML Dependency Resolver

A lightweight package manager and build utility for SysML projects.

The resolver manages project dependencies defined in a `sysml-project.yml` manifest, recursively resolves transitive dependencies, generates a lockfile for reproducible builds, and packages the complete project into a distributable artifact.

---

## Overview

The resolver performs four primary tasks:

1. Reads the project manifest (`sysml-project.yml`)
2. Resolves all project dependencies
3. Generates a lockfile (`sysml-lock.yml`)
4. Builds a packaged project folder containing all project artifacts and dependencies

---

## Supported Dependency Types

### Git Dependencies

Dependencies can be fetched directly from a Git repository.

```yaml
dependencies:
  - name: sysml-library
    source: git
    url: https://github.com/org/sysml-library.git
    version: main
```

During resolution, the resolver:

- Clones the repository
- Checks out the requested version, branch, or tag
- Records the exact commit hash in the lockfile

---

### Local Path Dependencies

Dependencies may also reference a local project.

```yaml
dependencies:
  - name: marine-library
    source: path
    path: ../marine-library
```

The dependency is copied into the local `deps` directory and becomes part of the build package.

---

## Expected Project Structure

```text
project/
│
├── sysml-project.yml
├── requirements.sysml
├── architecture.sysml
├── behavior.sysml
│
├── deps/
│
└── build/
```

---

## Manifest Format

Example:

```yaml
name: layered_simple_pump
version: 1.0.0

layers:
  - requirements.sysml
  - architecture.sysml
  - behavior.sysml

dependencies:
  - name: common-library
    source: git
    url: https://github.com/example/common-library.git
    version: main

  - name: marine-library
    source: path
    path: ../marine-library
```

---

## Dependency Resolution

Dependencies are resolved recursively.

If a dependency contains its own:

```text
sysml-project.yml
```

the resolver automatically resolves any nested dependencies.

Example:

```text
Pump Project
│
├── Common Library
│   └── Units Library
│
└── Marine Library
```

The resulting dependency tree is fully resolved before packaging.

---

## Lockfile Generation

After successful resolution, a lockfile is generated:

```text
sysml-lock.yml
```

Example:

```yaml
dependencies:
  common-library:
    version: main
    resolved: 456df85b547f2241f184bb4e95c3379f8a0f8e29

  marine-library:
    version: null
    resolved: null
```

The lockfile ensures reproducible builds by recording the exact commit used for every Git dependency.

---

## Build Output

The build process creates a packaged project under:

```text
build/
```

Example:

```text
build/
└── layered_simple_pump_1.0.0/
    ├── requirements.sysml
    ├── architecture.sysml
    ├── behavior.sysml
    ├── deps/
    ├── sysml-project.yml
    └── sysml-lock.yml
```

The package contains:

- Project layers
- Resolved dependencies
- Project manifest
- Lockfile

---

## Usage

```python
from pathlib import Path

project_dir = Path("/path/to/project")

resolver = Resolver(project_dir)
resolver()
```

Equivalent workflow:

```python
resolver = Resolver(project_dir)

resolver.resolve_project(...)
resolver.write_lockfile(...)
resolver.build_package_folder(...)
```

---

## Resolution Workflow

```text
sysml-project.yml
        │
        ▼
 Resolve Dependencies
        │
        ▼
   Clone / Copy
        │
        ▼
 Resolve Nested Dependencies
        │
        ▼
 Generate Lockfile
        │
        ▼
 Build Package
        │
        ▼
 build/<name>_<version>/
```

---

## Components

### Resolver

Core dependency management engine.

Responsibilities:

- Project resolution
- Dependency traversal
- Git cloning
- Local dependency import
- Lockfile generation
- Package construction

---

### PackageStructure

Defines the expected project layout.

Properties:

```python
MANIFEST
DEPS_DIR
```

Used to standardize project discovery and package creation.

---

## Requirements

Install Python dependencies:

```bash
pip install pyyaml
```

System requirements:

```bash
git --version
python --version
```

Recommended:

```text
Python 3.10+
Git 2.x+
```

---

## Current Limitations

- Dependency conflicts are not detected.
- Multiple versions of the same dependency are not supported.
- Existing path dependencies are not automatically refreshed.
- Existing Git repositories are not automatically updated using `git pull`.

---

## Future Improvements

- Semantic versioning support
- Dependency conflict detection
- Package registry support
- Dependency graph visualization
- Incremental builds
- Checksum verification
- SysML package publishing
- Digital twin package metadata support
- Remote artifact repositories

---

## Example

```bash
project/
│
├── sysml-project.yml
├── requirements.sysml
├── architecture.sysml
│
└── deps/
    ├── common-library/
    └── marine-library/
```

Run:

```bash
python resolver.py
```

Result:

```bash
build/layered_simple_pump_1.0.0/
```

containing the complete, reproducible SysML package.