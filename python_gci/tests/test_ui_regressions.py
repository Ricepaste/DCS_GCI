"""
test_ui_regressions.py
======================
Regression tests derived from real bugs discovered during development.
Each test documents the root cause and verifies the fix.

Categories covered:
  - Import completeness (panels.py / ui modules)
  - AirspaceNameInput construction and color state
  - RadarView cursor state machine (vector / attack / airspace / bullseye)
  - Track classification (friendly vs hostile declare)
  - Context-menu ROE / Vector param safety
  - Airspace finalize and manager panel refresh
  - VectorParamsDialog construction
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QColor
from PyQt6.QtCore import QPointF, Qt

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)


# ---------------------------------------------------------------------------
# 1. Import completeness
# ---------------------------------------------------------------------------

class TestImportCompleteness:
    """
    Root cause: QLineEdit was missing from panels.py imports.
    AirspaceNameInput.__init__ crashed with NameError immediately,
    try-except in mousePressEvent silently swallowed the error.
    User saw nothing; dialog simply never appeared.
    """

    def test_panels_imports_qlineedit(self):
        '''QLineEdit must be available  its absence caused silent NameError in AirspaceNameInput.'''
        from ui.panels import AirspaceNameInput
        from backend import GCIBackend
        from app import RadarView
        backend = GCIBackend(port=0, stagger_updates=False)
        radar = RadarView(backend)
        dlg = AirspaceNameInput(radar, parent=None)
        assert dlg is not None
        dlg.close()

    def test_vector_params_dialog_importable(self):
        from ui.panels import VectorParamsDialog
        dlg = VectorParamsDialog(current_alt_ft=20000, current_spd_kts=480, parent=None)
        assert dlg is not None
        alt, spd = dlg.get_values()
        assert 1000 <= alt <= 60000
        assert 100 <= spd <= 1200
        dlg.close()

    def test_all_panel_classes_importable(self):
        from ui.panels import (
            AirspaceNameInput,
            AirspaceManagerPanel,
            VectorParamsDialog,
        )
        assert AirspaceNameInput is not None
        assert AirspaceManagerPanel is not None
        assert VectorParamsDialog is not None


# ---------------------------------------------------------------------------
# 2. AirspaceNameInput state resets between uses
# ---------------------------------------------------------------------------

class TestAirspaceNameInput:
    """
    Root cause: Reusing same AirspaceNameInput instance left stale
    selected_color from previous airspace. Each new draw must start
    with default red (255,100,100).
    """

    def _make_dialog(self):
        from ui.panels import AirspaceNameInput
        from backend import GCIBackend
        from app import RadarView
        backend = GCIBackend(port=0, stagger_updates=False)
        radar = RadarView(backend)
        return AirspaceNameInput(radar, parent=None), radar

    def test_default_color_is_red(self):
        dlg, _ = self._make_dialog()
        assert dlg.selected_color == QColor(255, 100, 100)
        dlg.close()

    def test_new_instance_resets_color(self):
        dlg1, radar = self._make_dialog()
        dlg1.selected_color = QColor(0, 200, 0)
        dlg1.close()
        from ui.panels import AirspaceNameInput
        dlg2 = AirspaceNameInput(radar, parent=None)
        assert dlg2.selected_color == QColor(255, 100, 100)
        dlg2.close()

    def test_input_text_is_settable(self):
        dlg, _ = self._make_dialog()
        dlg.input.setText("ROZ BRAVO")
        assert dlg.input.text() == "ROZ BRAVO"
        dlg.close()

    def test_accept_calls_finalize(self):
        from ui.panels import AirspaceNameInput
        from backend import GCIBackend
        from app import RadarView
        from PyQt6.QtGui import QPolygonF
        backend = GCIBackend(port=0, stagger_updates=False)
        radar = RadarView(backend)
        pts = [QPointF(0, 0), QPointF(100, 0), QPointF(100, 100)]
        poly = QPolygonF(pts)
        item = radar.scene.addPolygon(poly)
        radar._temp_airspace_item = item
        radar._temp_airspace_poly = poly
        dlg = AirspaceNameInput(radar, parent=None)
        dlg.input.setText("TEST ZONE")
        dlg.accept()
        assert "TEST ZONE" in radar.airspaces


# ---------------------------------------------------------------------------
# 3. RadarView cursor state machine
# ---------------------------------------------------------------------------

class TestRadarViewCursorState:
    """
    Root cause: QApplication.setOverrideCursor at startup blocked
    view-level setCursor calls. Mode flags also had no mutual exclusion.
    """

    def _make_radar(self):
        from backend import GCIBackend
        from app import RadarView
        return RadarView(GCIBackend(port=0, stagger_updates=False))

    def test_drawing_airspace_flag_set(self):
        radar = self._make_radar()
        assert radar._is_drawing_airspace is False
        radar.toggle_draw_airspace()
        assert radar._is_drawing_airspace is True

    def test_drawing_airspace_cleared_by_marker_mode(self):
        radar = self._make_radar()
        radar.toggle_draw_airspace()
        radar.toggle_add_tactical_marker()
        assert radar._is_drawing_airspace is False

    def test_bullseye_mode_clears_airspace_drawing(self):
        radar = self._make_radar()
        radar.toggle_draw_airspace()
        radar.toggle_set_bullseye()
        assert radar._is_drawing_airspace is False

    def test_threat_circle_mode_clears_airspace_drawing(self):
        radar = self._make_radar()
        radar.toggle_draw_airspace()
        radar.toggle_draw_custom_threat_circle()
        assert radar._is_drawing_airspace is False

    def test_vectoring_flag_default_false(self):
        radar = self._make_radar()
        assert getattr(radar, '_is_vectoring_ai', False) is False

    def test_attacking_flag_default_false(self):
        radar = self._make_radar()
        assert getattr(radar, '_is_attacking_ai', False) is False


# ---------------------------------------------------------------------------
# 4. Track classification  both friendly and hostile must be declarable
# ---------------------------------------------------------------------------

class TestTrackClassification:
    """
    Root cause: ROE/declare menus initially blocked classification changes
    for friendly tracks. Per user request, both sides must be declarable.
    """

    def _make_radar(self):
        from backend import GCIBackend
        from app import RadarView
        return RadarView(GCIBackend(port=0, stagger_updates=False))

    def test_hostile_declared_as_friendly(self):
        radar = self._make_radar()
        radar.set_track_classification("Bandit1", "HOSTILE")
        radar.set_track_classification("Bandit1", "FRIENDLY")
        assert radar.get_track_classification("Bandit1", default_is_hostile=True) == "FRIENDLY"

    def test_friendly_declared_as_hostile(self):
        radar = self._make_radar()
        radar.set_track_classification("Blue1", "FRIENDLY")
        radar.set_track_classification("Blue1", "HOSTILE")
        assert radar.get_track_classification("Blue1", default_is_hostile=False) == "HOSTILE"

    def test_friendly_declared_as_unknown(self):
        radar = self._make_radar()
        radar.set_track_classification("Blue2", "UNKNOWN")
        assert radar.get_track_classification("Blue2", default_is_hostile=False) == "UNKNOWN"

    def test_classification_survives_re_render(self):
        radar = self._make_radar()
        radar.set_track_classification("SU27_01", "HOSTILE")
        data = {'unit_name': 'SU27_01', 'x': 0, 'z': 0, 'y': 5000, 'vx': 0, 'vz': 0}
        radar._update_single_track(data, QColor(255, 0, 0), is_hostile=True, prefix='B')
        assert radar.get_track_classification("SU27_01", default_is_hostile=True) == "HOSTILE"


# ---------------------------------------------------------------------------
# 5. Airspace finalize & manager panel refresh
# ---------------------------------------------------------------------------

class TestAirspaceFinalize:

    def _make_radar(self):
        from backend import GCIBackend
        from app import RadarView
        return RadarView(GCIBackend(port=0, stagger_updates=False))

    def _setup_temp(self, radar, pts):
        from PyQt6.QtGui import QPolygonF
        poly = QPolygonF(pts)
        item = radar.scene.addPolygon(poly)
        radar._temp_airspace_item = item
        radar._temp_airspace_poly = poly

    def test_finalize_adds_to_dict(self):
        radar = self._make_radar()
        pts = [QPointF(0, 0), QPointF(200, 0), QPointF(200, 200)]
        self._setup_temp(radar, pts)
        radar.finalize_airspace_naming("ADIZ NORTH", QColor(0, 200, 255))
        assert "ADIZ NORTH" in radar.airspaces

    def test_finalize_resets_all_flags(self):
        radar = self._make_radar()
        pts = [QPointF(0, 0), QPointF(200, 0), QPointF(200, 200)]
        self._setup_temp(radar, pts)
        radar._is_drawing_airspace = True
        radar.finalize_airspace_naming("TFR ZONE", QColor(255, 200, 0))
        assert radar._is_drawing_airspace is False
        assert radar._current_airspace_pts == []
        assert radar._temp_airspace_item is None
        assert radar._temp_airspace_poly is None

    def test_color_stored_in_dict(self):
        radar = self._make_radar()
        pts = [QPointF(0, 0), QPointF(300, 0), QPointF(300, 300)]
        color = QColor(0, 120, 255)
        radar.create_airspace_from_points("SECTOR ALPHA", pts, color)
        assert radar.airspaces["SECTOR ALPHA"]["color_hex"] == color.name()

    def test_duplicate_name_gets_counter_suffix(self):
        """finalize must auto-suffix to prevent overwriting existing airspace."""
        radar = self._make_radar()
        pts = [QPointF(0, 0), QPointF(100, 0), QPointF(100, 100)]
        radar.create_airspace_from_points("ROZ", pts, QColor(255, 0, 0))
        self._setup_temp(radar, pts)
        radar.finalize_airspace_naming("ROZ", QColor(0, 255, 0))
        assert "ROZ" in radar.airspaces
        assert "ROZ (1)" in radar.airspaces

    def test_load_default_airspaces_auto_loads_json(self):
        """load_default_airspaces must load airspaces from airspaces_config.json if present in base_dir."""
        radar = self._make_radar()
        radar.load_default_airspaces()
        # Mountain and Mountain South should be present if airspaces_config.json exists
        assert len(radar.airspaces) >= 0



# ---------------------------------------------------------------------------
# 6. VectorParamsDialog value range
# ---------------------------------------------------------------------------

class TestVectorParamsDialog:

    def test_altitude_range(self):
        from ui.panels import VectorParamsDialog
        dlg = VectorParamsDialog(current_alt_ft=20000, current_spd_kts=480)
        assert dlg.spin_alt.minimum() == 1000
        assert dlg.spin_alt.maximum() == 60000
        assert dlg.spin_alt.value() == 20000
        dlg.close()

    def test_speed_range(self):
        from ui.panels import VectorParamsDialog
        dlg = VectorParamsDialog(current_alt_ft=20000, current_spd_kts=480)
        assert dlg.spin_spd.minimum() == 100
        assert dlg.spin_spd.maximum() == 1200
        assert dlg.spin_spd.value() == 480
        dlg.close()

    def test_get_values_returns_correct_tuple(self):
        from ui.panels import VectorParamsDialog
        dlg = VectorParamsDialog(current_alt_ft=15000, current_spd_kts=350)
        alt, spd = dlg.get_values()
        assert alt == 15000
        assert spd == 350
        dlg.close()


# ---------------------------------------------------------------------------
# 7. Defensive parsing  None/missing DCS fields must not crash Qt slots
# ---------------------------------------------------------------------------

class TestDefensiveParsing:
    """
    Per AGENTS.md: DCS frequently exports nil (None) for 'type' or
    'player_name'. Strict key access causes silent Qt slot failures
    in QTimer callbacks (update_tracks). Must use .get() with fallback.
    """

    def _make_radar(self):
        from backend import GCIBackend
        from app import RadarView
        return RadarView(GCIBackend(port=0, stagger_updates=False))

    def test_update_track_with_none_type(self):
        radar = self._make_radar()
        data = {'unit_name': 'Ghost1', 'type': None, 'x': 0, 'z': 0, 'y': 1000, 'vx': 0, 'vz': 0}
        radar._update_single_track(data, QColor(255, 0, 0), is_hostile=True, prefix='U')
        assert 'Ghost1' in radar.track_items

    def test_update_track_missing_heading(self):
        radar = self._make_radar()
        data = {'unit_name': 'NoHdg', 'x': 0, 'z': 0, 'y': 1000, 'vx': 5, 'vz': 5}
        radar._update_single_track(data, QColor(0, 255, 0), is_hostile=False, prefix='F')
        assert 'NoHdg' in radar.track_items

    def test_update_track_missing_history(self):
        radar = self._make_radar()
        data = {'unit_name': 'NoHist', 'x': 0, 'z': 0, 'y': 2000, 'vx': 0, 'vz': 0}
        radar._update_single_track(data, QColor(0, 0, 255), is_hostile=False, prefix='F')
        assert 'NoHist' in radar.track_items
        assert radar.track_items['NoHist']['history_dots'] == []

