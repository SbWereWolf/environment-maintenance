#!/bin/sh
printf 'unexpected pip call\n' > "${NPM_TEST_PIP_MARKER:?Test marker path required}"
exit 19
