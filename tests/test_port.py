"""Test port statistics."""
from unittest import TestCase
from unittest.mock import patch

from flask import Response

from stats_api import PortStatsAPI


class TestPort(TestCase):
    """Test switch ports."""

    def test_non_existent_port(self):
        """Should return 404."""
        api = PortStatsAPI('non-existent-switch', 123)
        with patch('stats_api.request'):
            response = api.get_stats()
            self.assertIsInstance(response, Response,
                                  'Should be a flask.Response object')
