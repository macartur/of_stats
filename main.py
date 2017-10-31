"""Statistics application."""
from kytos.core import KytosNApp, log, rest
from kytos.core.helpers import listen_to
from pyof.v0x01.controller2switch.stats_request import StatsTypes

from napps.kytos.of_stats import settings
from napps.kytos.of_stats.stats import FlowStats, PortStats
from napps.kytos.of_stats.stats_api import FlowStatsAPI, PortStatsAPI, StatsAPI


class Main(KytosNApp):
    """Main class for statistics application."""

    def setup(self):
        """Initialize all statistics and set their loop interval."""
        self.execute_as_loop(settings.STATS_INTERVAL)

        # Initialize statistics
        msg_out = self.controller.buffers.msg_out
        self._stats = {StatsTypes.OFPST_PORT.value: PortStats(msg_out),
                       StatsTypes.OFPST_FLOW.value: FlowStats(msg_out)}

        StatsAPI.controller = self.controller

    def execute(self):
        """Query all switches sequentially and then sleep before repeating."""
        switches = list(self.controller.switches.values())
        for switch in switches:
            if not (switch.is_connected() and
                    switch.connection.protocol.version == 0x01):
                continue
            self._update_stats(switch)

    def shutdown(self):
        """End of the application."""
        log.debug('Shutting down...')

    def _update_stats(self, switch):
        for stats in self._stats.values():
            if switch.connection is not None:
                stats.request(switch.connection)

    @listen_to('kytos/of_core.v0x01.messages.in.ofpt_stats_reply')
    def listen_v0x01(self, event):
        """Detect the message body type."""
        stats_reply = event.content['message']
        stats_type = stats_reply.body_type
        self._listen(event, stats_type)

    @listen_to('kytos/of_core.v0x04.messages.in.ofpt_multipart_reply')
    def listen_v0x04(self, event):
        """Detect the message body type."""
        multipart_reply = event.content['message']
        stats_type = multipart_reply.multipart_type
        self._listen(event, stats_type)

    def _listen(self, event, stats_type):
        """Listen to all stats reply we deal with.

        Note: v0x01 ``body_type`` and v0x04 ``multipart_type`` have the same
        values.  Besides, both ``msg.body`` have the fields/attributes we use.
        Thus, we can treat them the same way and reuse the code.
        """
        msg = event.content['message']
        if stats_type.value in self._stats:
            stats = self._stats[stats_type.value]
            stats_list = msg.body
            stats.listen(event.source.switch, stats_list)
        else:
            log.debug('No listener for %s in %s.', msg.body_type.value,
                      list(self._stats.keys()))

    # REST API

    @rest('v1/<dpid>/ports/<int:port>')
    @staticmethod
    def get_port_stats(dpid, port):
        """Return statistics for ``dpid`` and ``port``."""
        return PortStatsAPI.get_port_stats(dpid, port)

    @rest('v1/<dpid>/ports')
    @staticmethod
    def get_ports_list(dpid):
        """Return ports of ``dpid``."""
        return PortStatsAPI.get_ports_list(dpid)

    @rest('v1/<dpid>/flows/<flow_hash>')
    @staticmethod
    def get_flow_stats(dpid, flow_hash):
        """Return statistics of a flow in ``dpid``."""
        return FlowStatsAPI.get_flow_stats(dpid, flow_hash)

    @rest('v1/<dpid>/flows')
    @staticmethod
    def get_flow_list(dpid):
        """Return all flows of ``dpid``."""
        return FlowStatsAPI.get_flow_list(dpid)

    @rest('v1/<dpid>/ports/<int:port>/random')
    @staticmethod
    def get_random_interface_stats(dpid, port):
        """Fake data for testing."""
        # Ignore dpid and port
        # pylint: disable=unused-argument
        return PortStatsAPI.get_random_port_stats()
