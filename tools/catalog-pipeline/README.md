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

La etapa posterior de [matching de identidad offline](docs/identity-matching.md) consume únicamente
los artefactos locales de discovery y conserva EP como autoridad y GAM como complemento. No activa
transporte ni produce imports JEM.

Detailed local-snapshot extraction is documented in [offline-extraction.md](docs/offline-extraction.md). It is fixture-only and keeps EP/GAM live extraction fail-closed.

La etapa siguiente de [validación binaria offline](docs/offline-assets.md) vincula candidatos con
payloads locales explícitos, valida contenedores JPEG/PNG/WebP/PDF y genera objetos content-addressed,
relaciones, reviews y manifiestos. No descarga, no autoriza, no selecciona principales y no
materializa archivos públicos.

La [adquisición autorizada y reanudable](docs/authorized-acquisition.md) añade planificación
fail-closed, transporte de assets aislado, robots por host, redirects manuales, checkpoints,
receipts y entrega al mismo `payload-manifest`; EP/GAM permanecen estructuralmente bloqueados.
# Selección de assets

La selección y materialización determinista, estrictamente offline, se documenta en
[`docs/asset-selection-materialization.md`](docs/asset-selection-materialization.md). La CLI separada es
`catalog_select.py` y no contiene transporte ni comandos de aprobación.
