# Process-launch test arrangement

These are test-owned fixtures. Select the project's Python with pytest and the checkout src on PYTHONPATH. Binary probe/log cases use their own files and independent hex payloads; compare complete stream bytes after the completion marker. Input fixtures never auto-update.

The remaining visible-worker case in test_process_launch.py uses an owned Xephyr server, Ubuntu X11, Zutty, DejaVuSansMono, libX11, ImageMagick import/identify, xwininfo and setxkbmap. ENV2_XEPHYR_ROOT selects the prepared root containing usr/bin/Xephyr and usr/lib/x86_64-linux-gnu. This is a prerequisite for that additional GUI scenario, not for every process test.

The owned visible server and workers are closed by their fixture. A missing prepared GUI prerequisite is an arrangement failure, not product RED or a passing check. The bounded named run/stop Zutty lifecycle cases live in test_run_stop.py and use the actual selected host DISPLAY without requiring Xephyr. Follow the [development verification contract](../../../docs/development.md#проверки) for targeted selection and final maintained smoke.
