# Catalog Pipeline Foundation and Discovery

Fundación **offline**, Python 3/biblioteca estándar, separada en `catalog_acquisition` y
`jem_nexus_import`. El flujo conserva `raw -> source identity -> discovered entry -> canonical
candidate -> resolved canonical product -> normalized -> audit -> package`.
El importador solo podrá aceptar un paquete aprobado; adquisición no conoce JWT, API ni
endpoints, e importación no importa adaptadores. `schemas/v1` es el único límite compartido.
La identidad de registro de fuente y la identidad canónica aprobada son contratos diferentes,
vinculados de forma auditable mediante `identity-link.schema.json`.

Véanse [arquitectura y políticas](docs/architecture.md), [contrato JEM](docs/jem-nexus-contract.md)
y el contrato machine-readable `schemas/v1/jem-nexus-contract.json`. La etapa segura de
discovery EP/GAM, actualmente fail-closed hasta disponer de evidencia estructural verificable,
se documenta en [discovery-ep-gam.md](docs/discovery-ep-gam.md).

Validación posterior (no ejecutada durante Prompt 267):

```bash
cd tools/catalog-pipeline
python -m unittest discover -s tests -v
python -m unittest tests.test_schemas -v
cd ../..
git diff --check HEAD^ HEAD
```
