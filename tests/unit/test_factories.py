"""FactoryBot.lint, as a test.

A factory nobody has called since a field changed is a factory that fails in
whichever test reaches it first, with a message about that test.
"""

import pytest

from tests import factories

BUILDERS = sorted(
    name
    for name in factories.__all__
    if callable(getattr(factories, name)) and name.startswith(("a_", "an_", "some_"))
)


@pytest.mark.parametrize("name", BUILDERS)
def test_it_builds_with_no_arguments(name):
    assert getattr(factories, name)() is not None


def test_the_defaults_are_values_you_would_recognise_in_a_failure():
    assert factories.a_verdict().metrics == {"value": 45.0}
