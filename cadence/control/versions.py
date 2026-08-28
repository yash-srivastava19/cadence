"""Reading a manifest written for an older cadence.

The api_version field has been required since the first release for exactly
this: a convert function needs something to switch on. This is that function.

A converter takes the document as written and returns it as the next version
would have been written. They chain, so a v1alpha1 file is brought up one
version at a time rather than by a table of every pair.
"""

from collections.abc import Callable, Mapping
from typing import Any

from cadence.errors import ManifestError

__all__ = ["CURRENT", "READABLE", "convert", "version_of"]

CURRENT = "cadence/v1alpha2"
READABLE = ("cadence/v1alpha1", CURRENT)

Document = Mapping[str, Any]

# v1alpha1 spelled it apiVersion, the one camelCase key in the file. Both
# spellings are looked for so that a document can be read before it is known
# which version wrote it.
VERSION_KEYS = ("api_version", "apiVersion")


def version_of(document: Document) -> str | None:
    for key in VERSION_KEYS:
        if key in document:
            value = document[key]
            return value if isinstance(value, str) else None
    return None


def _v1alpha1_to_v1alpha2(document: Document) -> Document:
    """apiVersion becomes api_version. Nothing else moved."""
    converted = {key: value for key, value in document.items() if key != "apiVersion"}
    converted["api_version"] = CURRENT
    return converted


CONVERTERS: Mapping[str, Callable[[Document], Document]] = {
    "cadence/v1alpha1": _v1alpha1_to_v1alpha2,
}


def convert(document: Document) -> Document:
    """Bring a manifest up to the version this cadence understands."""
    version = version_of(document)
    if version is None:
        return document  # let the model report the missing field
    seen: set[str] = set()
    while (converter := CONVERTERS.get(version)) is not None:
        if version in seen:  # pragma: no cover - a converter cycle is a bug
            raise ManifestError(f"converting {version} does not terminate")
        seen.add(version)
        document = converter(document)
        version = version_of(document)
        if version is None:  # pragma: no cover - a converter must set one
            raise ManifestError("a converted manifest has no api_version")
    if version != CURRENT:
        raise ManifestError(
            f"api_version {version!r} is not supported by this version of"
            f" cadence; readable versions: {', '.join(READABLE)}"
        )
    return document
