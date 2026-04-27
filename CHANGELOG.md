# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-04-25

### Added
- Initial project setup
- Data synthesis framework for life benchmark generation
- Persona generation module
- Event generation and scheduling system
- Phone data generation
- QA generation with multiple reasoning types:
  - Single-hop reasoning
  - Multi-hop reasoning
  - Temporal reasoning
  - Knowledge updating reasoning
  - Pattern recognition
  - Conflict detection
  - Harmful memory detection
  - Hidden information detection
  - Causal reasoning
- Memory structure building with fuzzy matching
- Daily and monthly event refinement
- Evaluation modules (circle, relation)
- Template-based data editing system

### Project Structure
```
lifebench/
├── event/          # Event generation and processing
├── persona/        # Persona generation
├── utils/          # Utility functions
├── run/            # Run scripts
├── data/           # Input data
├── tests/          # Test files
├── README.md
├── LICENSE
├── requirements.txt
└── pyproject.toml
```
