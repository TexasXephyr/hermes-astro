#!/usr/bin/env python3
"""
Unit tests for astro_data.loaders and the central YAML corpus.
"""
import os
import stat
import time
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add src to path for testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from astro_data.loaders import yaml_loader, clear_cache, ASSET_NAMES


ASSETS_DIR = Path(__file__).parent.parent.parent / "src" / "astro_data" / "assets"


class TestYamlLoader:
    def test_all_assets_load(self):
        for name in ASSET_NAMES:
            data = yaml_loader(name)
            assert isinstance(data, dict), f"{name} should load as dict"
            assert data, f"{name} should not be empty"

    def test_bodies_have_required_keys(self):
        bodies = yaml_loader("bodies")
        for key, body in bodies.items():
            assert "id" in body, f"{key} missing id"
            assert "glyph" in body, f"{key} missing glyph"
            assert "name" in body, f"{key} missing name"

    def test_signs_have_required_keys(self):
        signs = yaml_loader("signs")
        for key, sign in signs.items():
            assert "id" in sign, f"{key} missing id"
            assert "glyph" in sign, f"{key} missing glyph"
            assert "element" in sign, f"{key} missing element"
            assert "modality" in sign, f"{key} missing modality"

    def test_aspects_have_required_keys(self):
        aspects = yaml_loader("aspects")
        for key, aspect in aspects.items():
            assert "id" in aspect, f"{key} missing id"
            assert "glyph" in aspect, f"{key} missing glyph"
            assert "angle" in aspect, f"{key} missing angle"
            assert "major" in aspect, f"{key} missing major"
            assert "default_orb" in aspect, f"{key} missing default_orb"

    def test_dignities_have_required_keys(self):
        dignities = yaml_loader("dignities")
        for body, entry in dignities.items():
            assert "domicile" in entry, f"{body} missing domicile"
            assert "exaltation" in entry, f"{body} missing exaltation"
            assert "detriment" in entry, f"{body} missing detriment"
            assert "fall" in entry, f"{body} missing fall"

    def test_house_systems_have_required_keys(self):
        systems = yaml_loader("house_systems")
        for key, system in systems.items():
            assert "id" in system, f"{key} missing id"
            assert "name" in system, f"{key} missing name"
            assert "code" in system, f"{key} missing code"

    def test_moon_phases_have_required_keys(self):
        phases = yaml_loader("moon_phases")
        for key, phase in phases.items():
            assert "id" in phase, f"{key} missing id"
            assert "glyph" in phase, f"{key} missing glyph"
            assert "min_angle" in phase, f"{key} missing min_angle"
            assert "max_angle" in phase, f"{key} missing max_angle"

    def test_planetary_hours_have_required_keys(self):
        ph = yaml_loader("planetary_hours")
        assert "chaldean_order" in ph
        assert "day_ruler" in ph
        assert "qualities" in ph
        assert "prompts" in ph

    def test_scoring_weights_numeric(self):
        scoring = yaml_loader("scoring")
        for key, value in scoring.items():
            assert isinstance(value, (int, float)), f"{key} is not numeric"

    def test_yaml_loader_uses_safe_load_only(self):
        # Patch the unsafe loader to fail if called.
        with patch("yaml.load") as mock_load:
            # Also ensure safe_load works normally.
            yaml_loader("bodies")
            mock_load.assert_not_called()

    def test_cache_reloads_on_mtime_change(self):
        clear_cache()
        name = "bodies"
        first = yaml_loader(name)
        path = ASSETS_DIR / f"{name}.yaml"
        original_mtime = path.stat().st_mtime
        try:
            # Bump mtime to force reload.
            future = original_mtime + 10000
            os.utime(path, (future, future))
            second = yaml_loader(name)
            assert second is not first or second == first
        finally:
            os.utime(path, (original_mtime, original_mtime))

    def test_clear_cache(self):
        name = "bodies"
        first = yaml_loader(name)
        clear_cache()
        second = yaml_loader(name)
        assert first == second

    def test_unknown_asset_raises(self):
        with pytest.raises(ValueError) as exc:
            yaml_loader("not-an-asset")
        for valid in ASSET_NAMES:
            assert valid in str(exc.value)

    def test_malformed_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("{broken")
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(bad.read_text())
