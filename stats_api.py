"""Module with Classes to handle statistics api."""
import json
from abc import ABCMeta, abstractmethod
from random import randint

from flask import Response, request
from kytos.core import log

from napps.kytos.of_stats.stats import FlowStats, PortStats
from napps.kytos.of_stats.user_speed import UserSpeed


class StatsAPI(metaclass=ABCMeta):
    """Class to answer REST API requests."""

    _rrd = None
    controller = None

    def __init__(self):
        """Initialize instance attributes."""
        self._stats = {}

    def get_points(self, index, n_points=30):
        """Return Flask response for port stats."""
        try:
            data = self._get_points_data(index, n_points)
        except FileNotFoundError as e:
            data = self._get_rrd_not_found_error(e)
        return self._get_response(data)

    def _get_points_data(self, index, n_points):
        start = request.args.get('start')
        end = request.args.get('end')
        return self._fetch(index, start, end, n_points)

    def get_latest(self, fn_items):
        """Return latest stats for items obtained in a switch."""
        switch = self._get_switch()
        if switch is None:
            data = []
        else:
            items = fn_items(switch)
            data = list(self._get_latest_stats(items))
        return self._get_response({'data': data})

    @abstractmethod
    def _get_latest_stats(self, items):
        pass

    def _fetch(self, index, start, end, n_points):
        tstamps, cols, rows = self._rrd.fetch(index, start, end, n_points)
        self._stats = {col: [] for col in cols}
        self._stats['timestamps'] = list(tstamps)
        for row in rows:
            for col, value in zip(cols, row):
                self._stats[col].append(value)
        self._remove_null()
        return {'data': self._stats}

    def _get_switch(self):
        switch = self.controller.get_switch_by_dpid(self._dpid)
        if switch is None:
            log.warning('Switch %s not found in controller', self._dpid[-3:])
        return switch

    def _remove_null(self):
        """Remove a row if all its values are null."""
        nullable_cols = list(self._stats.keys())
        nullable_cols.remove('timestamps')
        n_elements = len(self._stats['timestamps'])

        # Check elements backwards for safe removal
        for i in range(n_elements - 1, -1, -1):
            for col in nullable_cols:
                # Stop if a non-null element is found in the row.
                if self._stats[col][i] is not None:
                    break
            if self._stats[col][i] is not None:
                # Keep current row and check the next one.
                continue
            # Remove the current row from every list
            for lst in self._stats.values():
                lst.pop(i)

    @staticmethod
    def _get_response(dct):
        json_ = json.dumps(dct, sort_keys=True, indent=4)
        # It should be application/vnd.api+json because it follows
        # http://jsonapi.org/format/. However, Firefox doesn't display it and
        # show a download window.
        return Response(json_, mimetype='application/json')

    @staticmethod
    def _get_rrd_not_found_error(exception):
        return {'errors': {
            'status': '404',
            'title': 'Database not found.',
            'detail': str(exception)}}


class PortStatsAPI(StatsAPI):
    """REST API for port statistics."""

    #: key is RRD column, value is a new column name for utilization
    #: percentage.
    _util_cols = {'rx_bytes': 'rx_util',
                  'tx_bytes': 'tx_util'}
    _rrd = PortStats.rrd

    def __init__(self, dpid, port=None):
        """Set dpid and port."""
        super().__init__()
        self._dpid = dpid
        self._port = port

    @classmethod
    def get_port_stats(cls, dpid, port):
        """Get up to 30 points of all statistics of PortStats.

        Includes start and end that are both optional and and must be submitted
        in the form "?start=x&end=y".

        Args:
            dpid (str): Switch dpid.
            port (str, int): Switch port number.
            start (int): Unix timestamp in seconds for the first stats.
                Defaults to the start parameter of the RRD creation.
            end (int): Unix timestamp in seconds for the last stats. Defaults
                to now.
            n_points (int): Return n_points. May return more if there is no
                matching resolution in the RRD file. Defaults to as many points
                as possible.
        """
        api = cls(dpid, port)
        return api.get_stats()

    @classmethod
    def get_ports_list(cls, dpid):
        """List all ports that have statistics and their latest stats.

        Include link utilization.

        Args:
            dpid (str): Switch dpid.
        """
        api = cls(dpid)
        return api.get_list()

    @staticmethod
    def get_random_port_stats():
        stats = {'data': {
            'timestamps': list(range(1508532494, 1508533094, 10)),
            'rx_bytes': [randint(100_000, 1_000_000) for _ in range(30)],
            'tx_bytes': [randint(100_000, 1_000_000) for _ in range(30)],
        }}
        return StatsAPI._get_response(stats)

    def get_list(self):
        """See :meth:`get_ports_list`."""
        return super().get_latest(lambda sw: (sw.interfaces[k]
                                              for k in sorted(sw.interfaces)))

    def _get_latest_stats(self, ifaces):
        for iface in ifaces:
            self._port = iface.port_number
            index = (self._dpid, self._port)
            row = self._rrd.fetch_latest(index)
            row['port'] = self._port
            row['name'] = iface.name
            row['mac'] = iface.address
            row['speed'] = self._get_speed(iface)
            yield self._add_utilization(row, iface)

    def get_stats(self):
        """See :meth:`get_port_stats`."""
        index = (self._dpid, self._port)
        return self.get_points(index)

    def _get_points_data(self, index, n_points):
        """Add port speed to rrd data."""
        response = super()._get_points_data(index, n_points)
        switch = self._get_switch()
        iface = switch.get_interface_by_port_no(self._port)
        response['data']['speed'] = self._get_speed(iface)
        return response

    def _get_speed(self, iface):
        """Update and return interface speed.

        Update controller's interface speed by reading user_speed.json file.
        """
        user = UserSpeed()
        user_speed = user.get_speed(self._dpid, iface.port_number)
        if user_speed != iface.get_custom_speed():
            iface.set_custom_speed(user_speed)
        return iface.speed

    def _add_utilization(self, row, iface):
        """Calculate utilization and also add port number."""
        speed = row['speed']
        if speed is None:
            for util_col in self._util_cols.values():
                row[util_col] = None
            # Shorten dpid for better log readability
            if len(self._dpid) >= 22:
                dpid = self._dpid[:3] + '...' + self._dpid[-3:]
            else:
                dpid = self._dpid
            log.warning('No speed, port %s, dpid %s', self._port, dpid)
        else:
            for bytes_col, util_col in self._util_cols.items():
                row[util_col] = row[bytes_col] / speed  # bytes/sec
        return row


class FlowStatsAPI(StatsAPI):
    """REST API for flow statistics."""

    _rrd = FlowStats.rrd

    def __init__(self, dpid, flow=None):
        """Set dpid and port."""
        super().__init__()
        self._dpid = dpid
        self._flow = flow

    @classmethod
    def get_flow_list(cls, dpid):
        """List all flows that have statistics and their latest stats.

        Args:
            dpid (str): Switch dpid.
        """
        api = cls(dpid)
        return api.get_list()

    @classmethod
    def get_flow_stats(cls, dpid, flow_hash):
        """Return flow statics by its hash.

        Includes start and end that are both optional and and must be submitted
        in the form "?start=x&end=y".

        Args:
            dpid (str): Switch dpid.
            flow_hash (str): Flow hash.
            start (int): Unix timestamp in seconds for the first stats.
                Defaults to the start parameter of the RRD creation.
            end (int): Unix timestamp in seconds for the last stats. Defaults
                to now.
        """
        api = cls(dpid, flow_hash)
        return api.get_stats()

    def get_list(self):
        """See :meth:`get_flow_list`."""
        return super().get_latest(lambda sw: sorted(sw.flows,
                                                    key=lambda f: f.id))

    def _get_latest_stats(self, flows):
        for flow in flows:
            index = (self._dpid, flow.id)
            rrd_data = self._rrd.fetch_latest(index)
            stats = {}
            stats['Bps'] = rrd_data.get('byte_count', 0)
            stats['pps'] = rrd_data.get('packet_count', 0)
            dct = flow.as_dict()
            # Make it JS friendly
            dct['id'] = dct.pop('id')
            dct['stats'] = stats
            yield dct

    def get_stats(self):
        """See :meth:`get_flow_stats`."""
        index = (self._dpid, self._flow)
        return super().get_points(index)
