# Release provenance

This is a clean public snapshot of Sany Alam's DAAI Console project, derived
from source commit `48a7be8` (14 August 2026). The original private repository
and history remain private. The commit history here starts at this source
release; it does not recreate the original development history.

The release includes the API, SQL migrations, dashboard, embedded Python SDK,
tests, architecture notes, a safe demo, and the static project showcase.
Local credentials, environment files, private operational notes, old deployment
inventory, unrelated assets, and uncommitted work are excluded. Defaults that
targeted retired services were changed to localhost. Public CI only tests and
builds; it does not deploy to the former infrastructure.
The release updates Next.js to its patched 15.x line using the official request
API codemod and updates PostCSS. The SDK now requires an explicit boolean
execution permission; missing or malformed permission never enables execution.

The original commit records identify Sany Alam / sanyAlam as the project's
contributor. Project-owned source is licensed under MIT starting with this
public snapshot. Dependencies retain their own licenses and are installed
from their registries rather than bundled. The small DAAI icon is from the
original project; the demo screenshot is captured from synthetic local output.

The companion repository `sanyAlam/daai-console-python` retains its history and
package version `0.1.0a2`. Its MIT license applies from its source alignment
commit onward. Existing PyPI artifacts were not rebuilt or relicensed.
