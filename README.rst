########
Overview
########
In order to manage a network, an administrator must have updated and reliable
statistics about it, in several levels of deepness, from a
switch port inbound and outbound traffic to the traffic of different connected
networks.

To achieve that, this Network Application collects statistical data provided by
the switches connected to the controller. We *do not use SNMP protocol* because
the OpenFlow protocol already provide this data. The data is stored to be
provided later through a REST API. This API can supply instant data,
historical data, and also some calculated information.

The provided statistics, per switch, are:

* **Ports/Interfaces**: bytes/sec, utilization, dropped packets/sec and
  errors/sec split into transmission and reception; interface name, MAC address
  and link speed (bps);
* **Flows**: packets/sec, bytes/sec;

##########
Installing
##########

************
RRDTool
************
.. note:: We currently use rrd to keep persistence in data, but future
    versions of this napp will allow you to choose what kind of backend you
    want to use.

==============
Linux packages
==============
Currently, this NApp uses `rrdtool <http://www.rrdtool.org>`__ and its Python
wrapper needs several packages to be installed and run. In Ubuntu, you can
install them by:

.. code-block:: shell

   apt install rrdtool python3.6-dev librrd-dev

===============
Python packages
===============
With the Linux packages above installed, just run:

.. code-block:: shell

   pip install rrdtool

*****************
NApp installation
*****************
All of the Kytos Network Applications are located in the online NApps
repository. To install this NApp, run:

.. code-block:: shell

   kytos napps install kytos/of_stats


.. code:: shell

   kytos napps install kytos/topology

**********
Developers
**********
To run the NApp from the source code, install the requirements and run:

.. code-block:: shell

   git clone https://github.com/kytos/of_stats.git
   cd of_stats
   kytos napps install kytos/of_stats

With the setup above, ``git pull`` will update NApp.

###########
Configuring
###########
There's no need to configure anything for this NApp to run. Read the sections
below if you need to change of_stats behavior or just want to know more details
on how it works.

*************
Settings file
*************
You can customize settings like how long to wait before asking the switches
for more statistics, as well as rrdtool-related configuration in the file
``settings.py``.

****************
Custom bandwidth
****************
Sometimes, the link speed is wrongly reported by the switch or there's no such
speed in the protocol specification. In these cases, you can manually define the
speeds in the file ``user_speed.json``. Changes to this file will be loaded
automatically without the need to restart the controller.

Setting the interface speeds manually is quite easy. Create ``user_speed.json``
following the provided ``user_speed.example.json`` file. Let's see what the
example means:

.. code-block:: json

   {
     "default": 100,
     "00:00:00:00:00:00:00:01":
     {
       "default": 10,
       "4": 1
     }
   }

The speed is specified in Gbps (not necessarily integers). The first line has
an optional *default* value that specify the speed of any interface that is not
found in this file. The switch whose dpid is *00:...:00:01* also has an
optional *default* value of 10 Gbps for all its ports except the number 4 that
is 1 Gbps. If there is no *default* value and the dpid or port is not
specified, the speed will be taken following the OpenFlow specifications.
To make it clear, find below the speed of some interfaces when
``user_speed.json`` has the content above:

+-------------------------+------+--------------+
|          DPID 1         | Port | Speed (Gbps) |
+=========================+======+==============+
| 00:00:00:00:00:00:00:01 |  4   |        1     |
+-------------------------+------+--------------+
| 00:00:00:00:00:00:00:01 |  2   |       10     |
+-------------------------+------+--------------+
| 00:00:00:00:00:00:00:02 |  4   |      100     |
+-------------------------+------+--------------+
| 00:00:00:00:00:00:00:02 |  2   |      100     |
+-------------------------+------+--------------+

######
Events
######

********
Listened
********

================================================
kytos/of_core.v0x01.messages.in.ofpt_stats_reply
================================================
This event contains the statistics to be processed.

Content
-------
A KytosEvent object containing:

- message: a `StatsReply` object;
- source: contains the switch datapath ID in ``source.switch.dpid``.

########
Rest API
########
You can find a list of the available endpoints and example input/output in the
'REST API' tab in this NApp's webpage in the `Kytos NApps Server
<https://napps.kytos.io/kytos/of_stats>`_.

###############
Troubleshooting
###############
.. attention:: The filenames below are relative to this NApp's folder.
   If you run Kytos as root, it is ``/var/lib/kytos/napps/kytos/of_stats`` or,
   if using virtualenv, ``$VIRTUAL_ENV/var/lib/kytos/napps/kytos/of_stats``.

**********************
Wrong link utilization
**********************
Check whether the link bandwidth is correct. If it is not, set the correct
bandwidth by following the instructions in *Configuring*, *Custom bandwidth*.

****************************
New settings are not applied
****************************
Some changes in ``settings.py`` require recreating the database. Check the
section ``Deleting the database`` below.

*********************
Deleting the database
*********************
You don't have to stop the controller to delete the databases. This NApp will
recreate them as needed after you run:

.. code-block:: shell

   rm -rf rrd/flows rrd/ports

