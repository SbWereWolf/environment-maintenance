# Process-launch test arrangement

These are test-owned fixtures, not a replacement product launcher.
Use the selected project Python with pytest and the checkout's `src` on
`PYTHONPATH`. The three real-console cases require Ubuntu X11, Zutty,
DejaVuSansMono under `/usr/share/fonts/truetype/dejavu`, libX11, ImageMagick
`import`/`identify`, `xwininfo`, `setxkbmap`, and a prepared Xephyr executable.

Set `ENV2_XEPHYR_ROOT` to the prepared package root containing
`usr/bin/Xephyr` and `usr/lib/x86_64-linux-gnu`. The test loads only that
Xephyr's extra libraries through its subprocess environment. For an ordinary
distribution installation this root is `/`; a locally extracted Ubuntu package
set is also supported. Select the actual prepared root, not another test run.

Run the focused module from the checkout with the explicit environment:

```bash
ENV2_XEPHYR_ROOT=/absolute/prepared/xephyr-root \
PYTHONPATH=/absolute/checkout/src \
/absolute/prepared/python -B -m pytest -p no:cacheprovider -q \
  tests/test_process_launch.py
```

Xephyr creates a visible native host window. Its two real child terminal
windows remain simultaneously observable. Only this owned server's keyboard
map is set to US. Named and abstract local transports are disabled together;
clients select its own TCP display explicitly. The host desktop uses its
unchanged original display. Disabling MIT-SHM on the owned nested server lets
Mesa render correctly over this transport. No hidden virtual framebuffer
substitutes for the visible windows.

The driver addresses an observed owned window directly with standard X11
key events. Numeric input and Ctrl+C are handled by the terminal's real PTY,
not written into the worker's diagnostic files. Worker PID, parent, TTY,
window ID and input response establish actual relationships. An outer screenshot
and each window screenshot retain visibility; blank images fail explicitly.
After stopping one worker, the other must answer a new input before its own
stop. Finally handlers close the experiment's workers and visible server.

The byte probe writes independent hex fixture payloads to separate streams,
flushes both, and only then writes its completion marker. Compare complete
log bytes only after that marker. Existing prefixes, stream identity and
subsequent append are exact test-owned expectations.

Main and operation files are runtime test inputs; fixtures never auto-update.
Earlier accepted tests remain separate regression controls. Missing product
behavior is RED; a failure to prepare these real GUI prerequisites is an
arrangement error, never a passing test or an intended RED.
