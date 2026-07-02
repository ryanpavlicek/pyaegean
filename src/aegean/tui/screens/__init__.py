"""The TUI screens (one `textual.screen.Screen` subclass per module).

Each screen is a thin view over :mod:`aegean.tui.data` and the shared widgets in
:mod:`aegean.tui.widgets`; none imports the pyaegean library directly. The app
(:mod:`aegean.tui.app`) registers them by name in its ``SCREENS`` map:

- ``home``    : :class:`aegean.tui.screens.home.HomeScreen`
- ``corpus``  : ``CorpusBrowserScreen`` (screens/corpus.py)
- ``greek``   : ``GreekWorkbenchScreen`` (screens/greek.py)
- ``data``    : ``DataStoreScreen`` (screens/data.py)

Each screen is a self-contained module registered by name in ``app.py``.
"""

from __future__ import annotations

__all__ = ["HomeScreen"]

from .home import HomeScreen
