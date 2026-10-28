# Laptop

- CPU: 11th Gen Intel Core i5-11300H @ 3.10GHz, 4 cores / 8 threads
- RAM: 8 GB (7.75 GB visible); GPU: GTX 1650 4 GB (unused)
- OS: Windows 11 Home Single Language 10.0.22621
- Python 3.11.9; `.venv` with `--system-site-packages` (PyPI file CDN ~17-25 kB/s on this network)
- Key packages: numpy 2.4.6, pandas 3.0.2, scikit-learn 1.7.2, scipy 1.15.3, river 0.26.1,
  streamlit 1.56.0, plotly 6.3.1, pyarrow 21.0.0, joblib 1.5.2, PyYAML 6.0.1, matplotlib 3.10.8, pytest 9.2.0
- Safe parallelism: `--workers 2` (4 workers + the dashboard exhausted RAM)
